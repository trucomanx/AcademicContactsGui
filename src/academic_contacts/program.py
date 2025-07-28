import os
import sys
import json
import signal
from PyQt5.QtWidgets import (
    QApplication, QWidget, QSizePolicy, QVBoxLayout, QHBoxLayout, QPushButton, QGroupBox,
    QLabel, QFileDialog, QLineEdit, QMessageBox, QScrollArea, QDialog, QTextEdit,  
    QFormLayout, QDialogButtonBox, QMainWindow, QAction, QToolBar, QMenu
)
from PyQt5.QtGui import QIcon, QDesktopServices, QClipboard
from PyQt5.QtCore import Qt, QPoint, QUrl


import academic_contacts.about as about
import academic_contacts.modules.configure as configure 

from academic_contacts.desktop import create_desktop_file, create_desktop_directory, create_desktop_menu
from academic_contacts.modules.wabout  import show_about_window

# Caminho para o arquivo de configuração
CONFIG_PATH = os.path.join(os.path.expanduser("~"),".config",about.__package__,"config.json")
configure.verify_default_config(CONFIG_PATH, default_content={"old_path":""})
CONFIG=configure.load_config(CONFIG_PATH)



class LatexDialog(QDialog):
    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Generated LaTeX Code")
        self.resize(600, 400)

        self.text = text

        layout = QVBoxLayout(self)

        # QTextEdit to display the code
        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(text)
        self.text_edit.setReadOnly(True)
        self.text_edit.setLineWrapMode(QTextEdit.NoWrap)
        layout.addWidget(self.text_edit)

        # Buttons layout
        btn_layout = QHBoxLayout()

        # Copy button
        self.copy_btn = QPushButton("Copy to Clipboard")
        self.copy_btn.setToolTip("Copy the LaTeX code to the system clipboard")
        self.copy_btn.clicked.connect(self.copy_to_clipboard)
        btn_layout.addWidget(self.copy_btn)

        # OK button
        self.ok_btn = QPushButton("OK")
        self.ok_btn.setToolTip("Close this window")
        self.ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.ok_btn)

        layout.addLayout(btn_layout)

    def copy_to_clipboard(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.text)

def show_latex_message(parent, text):
    dlg = LatexDialog(text, parent)
    dlg.exec_()

def latex_escape(text):
    replacements = {
        '\\': r'\textbackslash{}',
        '{': r'\{',
        '}': r'\}',
        '#': r'\#',
        '$': r'\$',
        '%': r'\%',
        '&': r'\&',
        '_': r'\_',
        '~': r'\textasciitilde{}',
        '^': r'\^{}',
    }
    for char, repl in replacements.items():
        text = text.replace(char, repl)
    return text


def export_elsevier_authors(data):
    # --- Tabelas para mapear afiliações ---
    affiliation_map = {}   # string da afiliação -> índice
    affiliations = []      # lista de afiliações únicas
    latex_lines = []

    if len(data)==0:
        return ""
    
    
    name = latex_escape(data[0]['name'].strip())
    latex_lines.append(f"\\cortext[cor1]{{{name}}}\n")

    for ID, entry in enumerate(data):
        # Verificar obrigatórios
        for key in ["name", "email", "organization"]:
            if key not in entry or not entry[key].strip():
                raise ValueError(f"O campo obrigatório '{key}' está ausente ou vazio para {entry.get('name','<desconhecido>')}")

        org = latex_escape(entry["organization"].strip())

        # Montar chave única da afiliação (string padronizada)
        parts = [f"organization={{{org}}}"]
        if entry.get("addressline"):
            parts.append(f"addressline={{{latex_escape(entry['addressline'].strip())}}}")
        if entry.get("city"):
            parts.append(f"city={{{latex_escape(entry['city'].strip())}}}")
        if entry.get("postcode"):
            parts.append(f"postcode={{{latex_escape(entry['postcode'].strip())}}}")
        if entry.get("state"):
            parts.append(f"state={{{latex_escape(entry['state'].strip())}}}")
        if entry.get("country"):
            parts.append(f"country={{{latex_escape(entry['country'].strip())}}}")

        aff_string = ",\n            ".join(parts)

        # Verificar se já existe, senão adicionar
        if aff_string not in affiliation_map:
            aff_index = len(affiliations) + 1
            affiliation_map[aff_string] = aff_index
            affiliations.append(aff_string)
        else:
            aff_index = affiliation_map[aff_string]

        # Adicionar autor
        name = latex_escape(entry['name'].strip())
        email = latex_escape(entry['email'].strip())

        if ID==0:
            latex_lines.append(f"\\author[{aff_index}]{{{name}\\corref{{cor1}}}}")
        else:
            latex_lines.append(f"\\author[{aff_index}]{{{name}}}")
        latex_lines.append(f"\\ead{{{email}}}")
        latex_lines.append("")

    # Adicionar blocos de afiliação no final
    for idx, aff in enumerate(affiliations, start=1):
        latex_lines.append(f"\\affiliation[{idx}]{{{aff}}}")
        latex_lines.append("")

    return "\n".join(latex_lines)



class ContactEditor(QDialog):
    def __init__(self, contact, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Contact")
        self.contact = contact.copy()

        layout = QFormLayout()
        self.fields = {}
        for key in contact:
            field = QLineEdit(contact[key])
            layout.addRow(key.capitalize(), field)
            self.fields[key] = field

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addWidget(buttons)
        self.setLayout(layout)

    def get_data(self):
        return {k: self.fields[k].text() for k in self.fields}


class AcademicContactsApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(about.__program_name__)
        self.setGeometry(200, 200, 700, 600)
        self.contacts = []
        self.current_file = ""
        
        ## Icon
        # Get base directory for icons
        self.base_dir_path = os.path.dirname(os.path.abspath(__file__))
        self.icon_path = os.path.join(self.base_dir_path, 'icons', 'logo.png')
        self.setWindowIcon(QIcon(self.icon_path)) 

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        self.init_toolbar()
        self.init_export_toolbar()
        self.generate_filepath()
        self.init_ui()
        
        if os.path.exists(CONFIG["old_path"]):
            self.load_file(CONFIG["old_path"])

    def generate_filepath(self):
        self.filcontainer = QWidget()
        self.hbox = QHBoxLayout(self.filcontainer)

        self.path_label = QLabel("<b>Filepath:</b>")
        self.hbox.addWidget(self.path_label)

        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("path/to/*.AcademicContacts.json")
        self.path_edit.setReadOnly(True)
        self.path_edit.setMinimumWidth(300)
        self.hbox.addWidget(self.path_edit)

        self.main_layout.addWidget(self.filcontainer)

    def init_toolbar(self):
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)
        toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)

        #
        open_action = QAction(QIcon.fromTheme("document-open"), "Open", self)
        open_action.setToolTip("Save a list card view")
        open_action.triggered.connect(lambda: self.load_file(""))
        toolbar.addAction(open_action)

        #
        save_action = QAction(QIcon.fromTheme("document-save"), "Save", self)
        save_action.setToolTip("Save a list card view")
        save_action.triggered.connect(self.save_file)
        toolbar.addAction(save_action)

        #
        save_as_action = QAction(QIcon.fromTheme("document-save-as"), "Save As", self)
        save_as_action.setToolTip("Save a new list card view")
        save_as_action.triggered.connect(self.save_as_file)
        toolbar.addAction(save_as_action)

        #
        new_file_action = QAction(QIcon.fromTheme("document-new"), "New File", self)
        new_file_action.setToolTip("Generate a new list card view")
        new_file_action.triggered.connect(self.new_file)
        toolbar.addAction(new_file_action)

        #
        new_card_action = QAction(QIcon.fromTheme("contact-new"), "Add Card", self)
        new_card_action.setToolTip("Add a new card to current view")
        new_card_action.triggered.connect(self.add_new_card)
        toolbar.addAction(new_card_action)
        
        # Separador expansível
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(spacer)
        
        # Coffee
        coffee_action = QAction(QIcon.fromTheme("emblem-favorite"), "Coffee", self)
        coffee_action.setToolTip("Buy me a coffee (TrucomanX)")
        coffee_action.triggered.connect(self.on_coffee_action_click)
        toolbar.addAction(coffee_action)
        
        # 
        about_action = QAction(QIcon.fromTheme("help-about"),"About", self)
        about_action.triggered.connect(self.open_about)
        about_action.setToolTip("Show the information of program.")
        toolbar.addAction(about_action)

    def init_ui(self):
        # Scroll area for cards
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.container = QWidget()
        self.vbox = QVBoxLayout(self.container)
        self.scroll.setWidget(self.container)
        self.main_layout.addWidget(self.scroll)

        # Filtro de busca
        filter_layout = QHBoxLayout()
        filter_label = QLabel("Filter:")
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Type to filter contacts...")
        self.filter_edit.textChanged.connect(self.refresh_cards)

        filter_layout.addWidget(filter_label)
        filter_layout.addWidget(self.filter_edit)
        self.main_layout.addLayout(filter_layout)


    def init_export_toolbar(self):
        export_toolbar = QToolBar("Export Toolbar")
        self.addToolBar(Qt.BottomToolBarArea, export_toolbar)
        export_toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)

        #
        elsevier_icon_path = os.path.join(self.base_dir_path, 'icons', 'elsevier.png')
        elsevier_action = QAction(QIcon(elsevier_icon_path), "Elsevier", self)
        elsevier_action.setToolTip("Export the author list in LaTeX to Elsevier template format.")
        elsevier_action.triggered.connect(self.show_latex_elsevier)
        export_toolbar.addAction(elsevier_action)



    def show_latex_elsevier(self):
        res=export_elsevier_authors(self.contacts)
        show_latex_message(self, res)

    def on_coffee_action_click(self):
        QDesktopServices.openUrl(QUrl("https://ko-fi.com/trucomanx"))

    def open_about(self):
        data={
            "version": about.__version__,
            "package": about.__package__,
            "program_name": about.__program_name__,
            "author": about.__author__,
            "email": about.__email__,
            "description": about.__description__,
            "url_source": about.__url_source__,
            "url_doc": about.__url_doc__,
            "url_funding": about.__url_funding__,
            "url_bugs": about.__url_bugs__
        }
        show_about_window(data,self.icon_path)

    def load_file(self, path=""):
        if os.path.exists(path)==False:
            path = QFileDialog.getOpenFileName(self, "Open AcademicContacts.json", "", "*.AcademicContacts.json")[0]
        
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.contacts = json.load(f)
                self.current_file = path
                self.path_edit.setText(path)
                self.refresh_cards()
                
                CONFIG["old_path"] = self.current_file
                configure.save_config(CONFIG_PATH, CONFIG)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load file:\n{e}")

    def save_file(self):
        if not self.current_file:
            self.save_as_file()
            return
        try:
            with open(self.current_file, "w", encoding="utf-8") as f:
                json.dump(self.contacts, f, indent=4, ensure_ascii=False)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save file:\n{e}")

    def save_as_file(self):
        path = QFileDialog.getSaveFileName(self, "Save As", "", "*.AcademicContacts.json")[0]
        if path:
            if not path.endswith(".AcademicContacts.json"):
                path += ".AcademicContacts.json"
            self.current_file = path
            self.path_edit.setText(path)
            self.save_file()
            
            CONFIG["old_path"] = self.current_file
            configure.save_config(CONFIG_PATH, CONFIG)

    def new_file(self):
        self.contacts = []
        self.current_file = ""
        self.path_edit.setText("")
        self.refresh_cards()

    def add_new_card(self):
        empty_contact = {
            "name": "",
            "email": "",
            "organization": "",
            "addressline": "",
            "city": "",
            "postcode": "",
            "state": "",
            "country": ""
        }
        dialog = ContactEditor(empty_contact, self)
        if dialog.exec_():
            self.contacts.append(dialog.get_data())
            self.refresh_cards()

    def refresh_cards(self):
        filter_text = self.filter_edit.text().lower().strip()

        # Limpa os widgets existentes
        while self.vbox.count():
            item = self.vbox.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)

        # Filtra contatos
        filtered_contacts = []
        for contact in self.contacts:
            if not filter_text:
                filtered_contacts.append(contact)
            else:
                combined_text = " ".join(contact.values()).lower()
                if filter_text in combined_text:
                    filtered_contacts.append(contact)

        # Renderiza os cards filtrados
        for index, contact in enumerate(filtered_contacts):
            card = QGroupBox(f"{index + 1}/{len(filtered_contacts)}")
            layout = QVBoxLayout()

            # Info display (text selectable)
            info = "<br>".join(f"<b>{k.capitalize()}</b>: {v}" for k, v in contact.items())
            label = QLabel(info)
            label.setTextInteractionFlags(Qt.TextSelectableByMouse)  # Make text selectable
            label.setWordWrap(True)
            label.setTextFormat(Qt.RichText)
            layout.addWidget(label)

            # Button to open context menu
            menu_btn = QPushButton("⋮")
            menu_btn.setFixedWidth(25)
            menu_btn.setToolTip("Card menu")
            menu_btn.setCursor(Qt.PointingHandCursor)
            menu_btn.setStyleSheet("QPushButton { border: none; font-weight: bold; }")
            menu_btn.clicked.connect(lambda _, i=self.contacts.index(contact), btn=menu_btn: self.show_card_menu(i, btn))

            # Top-right aligned row for the button
            top_row = QHBoxLayout()
            top_row.addStretch()
            top_row.addWidget(menu_btn)
            layout.insertLayout(0, top_row)

            card.setLayout(layout)
            self.vbox.addWidget(card)

        self.vbox.addStretch()

    def copy_card_as_dict(self, index: int):
        contact = self.contacts[index]
        dict_str = json.dumps(contact, indent=4, ensure_ascii=False)
        QApplication.clipboard().setText(dict_str)

    def show_card_menu(self, index: int, widget: QWidget):
        menu = QMenu()

        edit_action = QAction("Edit Card", self)
        edit_action.triggered.connect(lambda: self.edit_contact(index))
        menu.addAction(edit_action)

        delete_action = QAction("Delete Card", self)
        delete_action.triggered.connect(lambda: self.delete_contact(index))
        menu.addAction(delete_action)

        copy_action = QAction("Copy as dict", self)
        copy_action.triggered.connect(lambda: self.copy_card_as_dict(index))
        menu.addAction(copy_action)

        menu.exec_(widget.mapToGlobal(QPoint(0, widget.height())))

    def edit_contact(self, index):
        dialog = ContactEditor(self.contacts[index], self)
        if dialog.exec_():
            self.contacts[index] = dialog.get_data()
            self.refresh_cards()

    def delete_contact(self, index):
        del self.contacts[index]
        self.refresh_cards()

def main():
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    create_desktop_directory()    
    create_desktop_menu()
    create_desktop_file('~/.local/share/applications')
    
    for n in range(len(sys.argv)):
        if sys.argv[n] == "--autostart":
            create_desktop_directory(overwrite = True)
            create_desktop_menu(overwrite = True)
            create_desktop_file('~/.config/autostart', overwrite=True)
            return
        if sys.argv[n] == "--applications":
            create_desktop_directory(overwrite = True)
            create_desktop_menu(overwrite = True)
            create_desktop_file('~/.local/share/applications', overwrite=True)
            return
    
    app = QApplication(sys.argv)
    app.setApplicationName(about.__package__) 
    win = AcademicContactsApp()
    win.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
