import os
import sys
import json
from PyQt5.QtWidgets import (
    QApplication, QWidget, QSizePolicy, QVBoxLayout, QHBoxLayout, QPushButton, QGroupBox,
    QLabel, QFileDialog, QLineEdit, QMessageBox, QScrollArea, QDialog,
    QFormLayout, QDialogButtonBox, QMainWindow, QAction, QToolBar, QMenu
)
from PyQt5.QtGui import QIcon, QDesktopServices
from PyQt5.QtCore import Qt, QPoint, QUrl

import academic_contacts.about as about
import academic_contacts.modules.configure as configure 

from academic_contacts.desktop import create_desktop_file, create_desktop_directory, create_desktop_menu
from academic_contacts.modules.wabout  import show_about_window

# Caminho para o arquivo de configuração
CONFIG_PATH = os.path.join(os.path.expanduser("~"),".config",about.__package__,"config.json")
configure.verify_default_config(CONFIG_PATH, default_content={"old_path":""})
CONFIG=configure.load_config(CONFIG_PATH)


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
        self.setWindowTitle("Academic Contacts Editor")
        self.setGeometry(200, 200, 700, 600)
        self.contacts = []
        self.current_file = ""
        
        ## Icon
        # Get base directory for icons
        base_dir_path = os.path.dirname(os.path.abspath(__file__))
        self.icon_path = os.path.join(base_dir_path, 'icons', 'logo.png')
        self.setWindowIcon(QIcon(self.icon_path)) 

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        self.init_toolbar()
        self.generate_filepath()
        self.init_ui()

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
        open_action.triggered.connect(self.load_file)
        toolbar.addAction(open_action)

        #
        save_action = QAction(QIcon.fromTheme("document-save"), "Save", self)
        save_action.triggered.connect(self.save_file)
        toolbar.addAction(save_action)

        #
        save_as_action = QAction(QIcon.fromTheme("document-save-as"), "Save As", self)
        save_as_action.triggered.connect(self.save_as_file)
        toolbar.addAction(save_as_action)

        #
        new_file_action = QAction(QIcon.fromTheme("document-new"), "New File", self)
        new_file_action.triggered.connect(self.new_file)
        toolbar.addAction(new_file_action)

        #
        new_card_action = QAction(QIcon.fromTheme("contact-new"), "New Card", self)
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

    def load_file(self):
        path = QFileDialog.getOpenFileName(self, "Open AcademicContacts.json", "", "*.AcademicContacts.json")[0]
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.contacts = json.load(f)
                self.current_file = path
                self.path_edit.setText(path)
                self.refresh_cards()
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
    app = QApplication(sys.argv)
    win = AcademicContactsApp()
    win.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
