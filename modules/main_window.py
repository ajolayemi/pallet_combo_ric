#!/usr/bin/env python
import sys

from PyQt5.QtWidgets import (QApplication, QLabel,
                             QWidget, QFormLayout,
                             QMainWindow, QPushButton,
                             QComboBox, QLineEdit,
                             QVBoxLayout, QGridLayout,
                             QMessageBox)

from PyQt5.QtGui import QFont

# Self defined modules
from helper_modules import helper_functions
import settings

MSG_FONT = QFont('Italics', 13)
BUTTONS_FONT = QFont('Times', 13)

APP_INFO_JSON_CONTENTS = helper_functions.json_file_loader(
    file_name=settings.INFORMATION_JSON
)


class MainPage(QMainWindow):
    """" User GUI. """

    def __init__(self, parent=None):
        super(MainPage, self).__init__(parent)
        self.setWindowTitle(APP_INFO_JSON_CONTENTS.get('window_title'))
        self.resize(300, 120)
        self.central_wid = QWidget()

        self.win_layout = QVBoxLayout()

        self.central_wid.setLayout(self.win_layout)

        self.setCentralWidget(self.central_wid)

        self._add_wids()

        self._set_initial_state()
        self._connect_signals_slots()

        self.google_sheet_link = None

    def _connect_signals_slots(self):
        """ Connects widgets with their respective functions """
        self.g_sheet_link.textChanged.connect(self._link_label_responder)
        self.close_app_btn.clicked.connect(self._close_btn_responder)

    def _close_btn_responder(self):
        """ Responds to user's click on the button named 'Chiudi' """
        user_choice = helper_functions.ask_before_close(
            msg_box_font=MSG_FONT,
            window_tile=APP_INFO_JSON_CONTENTS.get('window_title'),
        )
        if user_choice == QMessageBox.Yes:
            self.close()
        else:
            pass

    def _link_label_responder(self):
        """ Keeps track of when user enter or does not enter a link
        in the line edit widget labeled 'Link' """
        if self.g_sheet_link.text():
            self.to_do_combo.setEnabled(True)
            self.combine_pallet_btn.setEnabled(True)
            self.google_sheet_link = self.g_sheet_link.text()
        else:
            self.to_do_combo.setEnabled(False)
            self.combine_pallet_btn.setEnabled(False)

    def _set_initial_state(self):
        """ Sets the initial state of the GUI by enabling some widgets. """
        self.combine_pallet_btn.setEnabled(False)
        self.to_do_combo.setEnabled(False)

    def _add_wids(self):
        username = helper_functions.get_user_name()
        self.greetings_lbl = QLabel(f'<h1> Ciao {username}.</h1>')
        self.win_layout.addWidget(self.greetings_lbl)

        self.btns_lbl = '<b> --- </b>'

        self.g_sheet_link_lbl = QLabel('Link : ')
        self.g_sheet_link = QLineEdit()
        self.g_sheet_link.setPlaceholderText(f'link {settings.GOOGLE_SHEET_WB_NAME}')
        self.g_sheet_link.setFont(QFont('Italics', 13))
        self.g_sheet_link_lbl.setFont(QFont('Italics', 16))

        self.to_do_combo = QComboBox()
        self.to_do_combo_lbl = QLabel('Nuovo ? ')
        self.to_do_combo.addItems(settings.TO_DO_COMBO_ITEMS)
        self.to_do_combo_lbl.setFont(QFont('Italics', 16))
        self.to_do_combo.setFont(MSG_FONT)

        self.combine_pallet_btn = QPushButton('Comporre Pedane')
        self.combine_pallet_btn.setFont(BUTTONS_FONT)
        self.combine_pallet_btn.setStyleSheet('color: blue')

        self.close_app_btn = QPushButton('Chiudi')
        self.close_app_btn.setFont(BUTTONS_FONT)
        self.close_app_btn.setStyleSheet('color: red')

        buttons_list = [self.combine_pallet_btn, self.close_app_btn]

        self.form_layout = QFormLayout()
        self.btn_layout = QGridLayout()

        self.form_layout.addRow(self.g_sheet_link_lbl, self.g_sheet_link)
        self.form_layout.addRow(self.to_do_combo_lbl, self.to_do_combo)

        for button in buttons_list:

            self.btn_layout.addWidget(button)

        self.win_layout.addLayout(self.form_layout)
        self.win_layout.addLayout(self.btn_layout)


def main():
    app = QApplication(sys.argv)
    win = MainPage()
    win.show()
    app.exec_()


if __name__ == '__main__':
    main()
