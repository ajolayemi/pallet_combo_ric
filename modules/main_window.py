#!/usr/bin/env python
import sys

from PyQt5.QtCore import QThread
from PyQt5.QtGui import QFont, QIntValidator
from PyQt5.QtWidgets import (QApplication, QLabel,
                             QWidget, QMainWindow, QPushButton,
                             QComboBox, QLineEdit, QGridLayout,
                             QMessageBox)
# Self defined modules
from helper_modules import helper_functions

import settings
from api_communicator import PedApi
from db_communicator import DatabaseCommunicator

MSG_FONT = QFont('Italics', 13)
BUTTONS_FONT = QFont('Times', 13)

APP_INFO_JSON_CONTENTS = helper_functions.json_file_loader(
    file_name=settings.INFORMATION_JSON
)


class MainPage(QMainWindow):
    """" User GUI. """

    def __init__(self, parent=None):
        super(MainPage, self).__init__(parent)
        self.setWindowTitle(settings.WINDOW_TITLE)
        self.resize(300, 120)
        self.central_wid = QWidget()

        self.win_layout = QGridLayout()

        self.central_wid.setLayout(self.win_layout)

        self.setCentralWidget(self.central_wid)

        self._add_wids()

        self._set_initial_state()
        self._connect_signals_slots()

        self.google_sheet_link = None
        self.overwrite_data_in_sheet = True
        # This controls whether user chose to enter a value for maximum
        # boxes on pallets or not
        self.user_want_max_boxes = False
        self.max_boxes = 0

    def _connect_signals_slots(self):
        """ Connects widgets with their respective functions """
        self.g_sheet_link.textChanged.connect(self._link_label_responder)
        self.to_do_combo.currentIndexChanged.connect(self._to_do_combo_item_getter)
        self.update_db_btn.clicked.connect(self._pallet_db_update)
        self.combine_pallet_btn.clicked.connect(self._pallet_combiner)
        self.close_app_btn.clicked.connect(self._close_btn_responder)

    def _pallet_combiner(self):
        """ Responds to user click on the button named Comporre Button. """
        if self.overwrite_data_in_sheet:
            warning_msg = 'Procedendo, questa operazione sovrascriverà i dati già esistenti in manuale.\n' \
                          'Se non vuoi procedere, clicca su "No" e selezionare "No" nella riga precedente.\n' \
                          'Clicca su "Yes" in caso volessi procedere. '
            ask_user = helper_functions.ask_for_overwrite(
                msg_box_font=MSG_FONT, window_tile=settings.WINDOW_TITLE,
                custom_msg=warning_msg
            )
        else:
            msg = "Sei sicuro di voler procedere ?"
            ask_user = helper_functions.ask_for_overwrite(
                msg_box_font=MSG_FONT, window_tile=settings.WINDOW_TITLE,
                custom_msg=msg
            )

        if ask_user == QMessageBox.Yes:
            self.pallet_thread = QThread()

            self.pallet_api_cls = PedApi(order_spreadsheet=self.google_sheet_link,
                                         for_pallets=True,
                                         overwrite_data=self.overwrite_data_in_sheet)

            # Move thread
            self.pallet_api_cls.moveToThread(self.pallet_thread)

            # Connect this thread and the function that constructs pallets
            self.pallet_thread.started.connect(
                self.pallet_api_cls.construct_pallets
            )

            # Update app's state
            self.pallet_api_cls.started.connect(self._update_while_busy)
            self.pallet_api_cls.finished.connect(self._update_after_done)
            self.pallet_api_cls.unfinished.connect(self._update_after_done)
            self.pallet_api_cls.empty_orders.connect(self._update_after_done)
            self.pallet_api_cls.empty_order_table.connect(self._update_after_done)
            self.pallet_api_cls.finished.connect(self._communicate_pallet_success_outcome)
            self.pallet_api_cls.unfinished.connect(self._communicate_pallet_error_outcome)
            self.pallet_api_cls.empty_orders.connect(self._communicate_pallet_error_outcome)
            self.pallet_api_cls.empty_order_table.connect(self._communicate_pallet_error_outcome)

            # Do clean up
            self.pallet_api_cls.finished.connect(self.pallet_thread.quit)
            self.pallet_api_cls.unfinished.connect(self.pallet_thread.quit)
            self.pallet_api_cls.empty_orders.connect(self.pallet_thread.quit)
            self.pallet_api_cls.empty_order_table.connect(self.pallet_thread.quit)
            self.pallet_api_cls.finished.connect(self.pallet_thread.deleteLater)
            self.pallet_api_cls.unfinished.connect(self.pallet_thread.deleteLater)
            self.pallet_api_cls.empty_orders.connect(self.pallet_thread.deleteLater)
            self.pallet_api_cls.empty_order_table.connect(self.pallet_thread.deleteLater)

            # Start thread
            self.pallet_thread.start()

    def _communicate_pallet_error_outcome(self, msg):
        helper_functions.output_communicator(
            msg_box_font=MSG_FONT, window_title=settings.WINDOW_TITLE,
            output_type=False, custom_msg=msg, button_pressed=self.combine_pallet_btn.text()
        )

    def _communicate_pallet_success_outcome(self, msg):
        helper_functions.output_communicator(
            msg_box_font=MSG_FONT, button_pressed=self.combine_pallet_btn.text(),
            output_type=True, window_title=settings.WINDOW_TITLE, custom_msg=msg
        )

    def _update_after_done(self):
        """ Updates app's state when it's done combining pallets. """
        self.g_sheet_link.clear()
        self.g_sheet_link.setEnabled(True)
        self.update_db_btn.setEnabled(True)
        self.close_app_btn.setEnabled(True)

    def _update_while_busy(self):
        """ Updated the GUI state while it's busy building pallets. """
        self.g_sheet_link.setEnabled(False)
        self.to_do_combo.setEnabled(False)
        self.update_db_btn.setEnabled(False)
        self.combine_pallet_btn.setEnabled(False)
        self.close_app_btn.setEnabled(False)

    def _pallet_db_update(self):
        """ Responds to user's click on the button called Aggiornare DB.
        It basically reads data from a Google Sheet and saves it in database (sqlite). """
        db_class = DatabaseCommunicator()
        check_pallet_table = db_class.check_table(settings.PALLET_INFO_TABLE)
        if check_pallet_table:
            custom_message = 'Sei sicuro di voler sovrascrivere i dati esistenti in database ? '
            ask_user = helper_functions.ask_for_overwrite(
                msg_box_font=MSG_FONT, window_tile=settings.WINDOW_TITLE,
                custom_msg=custom_message)
            # If user chooses to drop table
            if ask_user == QMessageBox.Yes:
                # Drop table
                db_class.drop_table(settings.PALLET_INFO_TABLE)

                db_update_class = PedApi()
                # Then update it with new data.
                update_req = db_update_class.get_pallet_range_data()
                print(update_req)
                self._db_result_communicator(result=update_req)

        else:
            db_update_class = PedApi()
            # Then update it with new data.
            update_result = db_update_class.get_pallet_range_data()
            self._db_result_communicator(result=update_result)

    def _db_result_communicator(self, result: bool):
        if result:
            msg = 'Database aggiornato con successo!'
            helper_functions.output_communicator(
                msg_box_font=MSG_FONT, window_title=settings.WINDOW_TITLE,
                custom_msg=msg, button_pressed=self.update_db_btn.text(),
                output_type=True
            )
        else:
            msg = 'Aggiornamento database non riuscito!'
            helper_functions.output_communicator(
                msg_box_font=MSG_FONT, window_title=settings.WINDOW_TITLE,
                custom_msg=msg, button_pressed=self.update_db_btn.text(),
                output_type=False
            )

    def _max_boxes_combo_item(self):
        """ Gets max boxes ComboBox widget current item and translates
        its value to bool value. """
        values_dict = {
            settings.MAX_BOXES_ITEMS[0]: False,
            settings.MAX_BOXES_ITEMS[1]: True
        }
        if self.max_boxes_combo.currentText():
            self.user_want_max_boxes = values_dict[self.max_boxes_combo.currentText()]

    def _to_do_combo_item_getter(self):
        """ Gets to do ComboBox widget current item translating its value. """
        value_dict = {
            settings.TO_DO_COMBO_ITEMS[0]: True,
            settings.TO_DO_COMBO_ITEMS[1]: False
        }

        if self.to_do_combo.currentText():
            self.overwrite_data_in_sheet = value_dict[self.to_do_combo.currentText()]

    def _close_btn_responder(self):
        """ Responds to user's click on the button named 'Chiudi' """
        user_choice = helper_functions.ask_before_close(
            msg_box_font=MSG_FONT,
            window_tile=settings.WINDOW_TITLE,
        )
        if user_choice == QMessageBox.Yes:
            self.close()
        else:
            pass

    def _link_label_responder(self):
        """ Keeps track of when user enter or does not enter a link
        in the line edit widget labeled 'Link' """
        if self.g_sheet_link.text():
            # Check to see that user has entered a valid link
            valid_link = helper_functions.get_sheet_id(
                google_sheet_link=self.g_sheet_link.text()
            )
            if valid_link:
                self.to_do_combo.setEnabled(True)
                self.combine_pallet_btn.setEnabled(True)
                self.google_sheet_link = self.g_sheet_link.text()
        else:
            self.to_do_combo.setEnabled(False)
            self.combine_pallet_btn.setEnabled(False)

    def _set_initial_state(self):
        """ Sets the initial state of the GUI by enabling some widgets. """
        self.g_sheet_link.clear()
        self.to_do_combo.setCurrentIndex(0)
        self.combine_pallet_btn.setEnabled(False)
        self.to_do_combo.setEnabled(False)
        self.max_boxes_combo.setEnabled(False)

    def _add_wids(self):
        username = helper_functions.get_user_name()
        self.greetings_lbl = QLabel(f'<h1> Ciao {username}.</h1>')
        self.win_layout.addWidget(self.greetings_lbl)

        self.btns_lbl = '<b> --- </b>'

        self.g_sheet_link_lbl = QLabel('Link foglio google: ')
        self.g_sheet_link = QLineEdit()
        self.g_sheet_link.setPlaceholderText(f'link {settings.GOOGLE_SHEET_WB_NAME}')
        self.g_sheet_link.setFont(QFont('Italics', 13))
        self.g_sheet_link_lbl.setFont(QFont('Italics', 16))

        self.to_do_combo = QComboBox()
        self.to_do_combo_lbl = QLabel('Sovrascrivere dati esistenti ? ')
        self.to_do_combo.addItems(settings.TO_DO_COMBO_ITEMS)
        self.to_do_combo_lbl.setFont(QFont('Italics', 16))
        self.to_do_combo.setFont(MSG_FONT)

        self.max_boxes_lbl = QLabel('Numero max cubotti per PED')
        self.max_boxes_lbl.setFont(QFont('Italics', 16))

        self.max_boxes_combo = QComboBox()
        self.max_boxes_combo.addItems(settings.MAX_BOXES_ITEMS)

        self.max_boxes_combo.setFont(MSG_FONT)

        self.max_boxes_value = QLineEdit()
        self.max_boxes_value.setValidator(QIntValidator())
        self.max_boxes_value.setPlaceholderText('0')

        self.update_db_btn = QPushButton('Aggiornare DB')
        self.update_db_btn.setFont(BUTTONS_FONT)
        self.update_db_btn.setStyleSheet('color: blue')

        self.combine_pallet_btn = QPushButton('Comporre Pedane')
        self.combine_pallet_btn.setFont(BUTTONS_FONT)

        self.close_app_btn = QPushButton('Chiudi')
        self.close_app_btn.setFont(BUTTONS_FONT)
        self.close_app_btn.setStyleSheet('color: red')

        widgets = [self.g_sheet_link_lbl, self.g_sheet_link,
                   self.to_do_combo_lbl, self.to_do_combo,
                   self.max_boxes_lbl, self.max_boxes_combo,
                   self.combine_pallet_btn, self.update_db_btn,
                   self.close_app_btn]

        for wid in widgets:
            self.win_layout.addWidget(wid)
            self.win_layout.setSpacing(5)


def main():
    app = QApplication(sys.argv)
    win = MainPage()
    win.show()
    app.exec_()


if __name__ == '__main__':
    main()
