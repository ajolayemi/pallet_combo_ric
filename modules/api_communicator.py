#!/usr/bin/env python

""" Communicates with google sheets using Google Sheet API both reading and writing data to
the sheets. """

import string
from PyQt5.QtCore import pyqtSignal, QObject
from google.oauth2 import service_account
from googleapiclient.discovery import build
from collections import namedtuple

# Self defined modules
import settings
from helper_modules import helper_functions
from db_communicator import DatabaseCommunicator


API_INFO_JSON_CONTENTS = helper_functions.json_file_loader(
    file_name='../app_info_json.json'
)


def box_distributor(pallet_type: str, tot_pallets: int,
                    boxes_per_pallets: int, tot_boxes_ordered: int,
                    logistic_details: list):
    """ Distributes all the boxes ordered provided by the tot_boxes_ordered
    parameter on the total available pallets given by tot_pallets parameter value.
    For example, if the total available pallets for a certain logistic is 10 and the total
    number of boxes ordered are 1000, this function distributes all the thousand boxes
    on the 10 pallets.
    It returns a named tuple. """

    pallet_type_base_info = settings.PALLETS_BASE_INFO.get(pallet_type)
    last_pallet_num = API_INFO_JSON_CONTENTS.get('last_pallet_num')
    last_alphabet = API_INFO_JSON_CONTENTS.get('last_pallet_letter')

    if pallet_type_base_info and logistic_details:
        pallet_code_name = pallet_type_base_info[0]
        pallet_base_value = pallet_type_base_info[1]
        result = {pallet_code_name: {}}
        remaining_boxes = tot_boxes_ordered
        remaining_pallets = tot_pallets

        # Loop over the value provided for total_pallets
        for current_pallet_num in range(1, int(tot_pallets) + 1):
            pallet_num = current_pallet_num + last_pallet_num
            # logistic_details is a list that contains the following information
            # [client channel of order (B2C - LV, B2C - PL), date of shipping]
            if logistic_details[0] == settings.ADP_CHANNEL_CODE:
                last_alphabet = helper_functions.get_next_alpha(
                    current_alpha=last_alphabet
                )
                current_pallet_name = f"PED {pallet_num}{last_alphabet} " \
                                      f"{logistic_details[0]} del {logistic_details[1]}"
            else:
                current_pallet_name = f"PED {pallet_num} {logistic_details[0]} " \
                                    f"del {logistic_details[1]}"

            # If the current remaining boxes is less than the value of boxes_per_pallets
            if remaining_boxes < boxes_per_pallets:
                result[pallet_code_name][current_pallet_name] = remaining_boxes
                remaining_boxes -= remaining_boxes
                remaining_pallets -= 1

            # If the value of boxes_per_pallets * tot_pallets <= remaining_boxes
            # distribute the boxes in tot_pallets equally
            elif boxes_per_pallets * remaining_pallets <= remaining_boxes:
                result[pallet_code_name][current_pallet_name] = boxes_per_pallets
                remaining_boxes -= boxes_per_pallets
                remaining_pallets -= 1

            # If the value of boxes_per_pallets * tot_pallets > tot_boxes_ordered
            # do the following
            else:
                # If the current value of remaining_boxes // remaining_pallets
                # is not a multiple of the base of the pallet.
                if remaining_boxes // remaining_pallets % pallet_base_value:
                    valid_boxes = helper_functions.get_multiples_of(
                        number=pallet_base_value, multiple_start=remaining_boxes // remaining_pallets,
                        multiple_limit=boxes_per_pallets
                    )[0]
                    result[pallet_code_name][current_pallet_name] = valid_boxes
                    remaining_boxes -= valid_boxes
                    remaining_pallets -= 1

                else:
                    result[pallet_code_name][current_pallet_name] = remaining_boxes // remaining_pallets
                    remaining_boxes -= remaining_boxes // remaining_pallets
                    remaining_pallets -= 1

        result_tuple = namedtuple('BoxDivision', ['box_division', 'remaining_boxes',
                                                  'last_alphabet', 'last_pallet_num'])
        return result_tuple(result, remaining_boxes, last_alphabet,
                            pallet_num)


class PedApi(QObject):

    # Custom sigs
    started = pyqtSignal()
    finished = pyqtSignal()
    unfinished = pyqtSignal()
    db_updated = pyqtSignal()
    db_not_updated = pyqtSignal()

    def __init__(self, order_spreadsheet: str, overwrite_data: bool):
        super(PedApi, self).__init__()
        self.scopes = ['https://www.googleapis.com/auth/spreadsheets']
        self.api_key_file = API_INFO_JSON_CONTENTS.get('api_key_file_name')
        self.api_creds = service_account.Credentials.from_service_account_file(
            self.api_key_file, scopes=self.scopes
        )

        # Google SpreadSheets Info
        self.order_spreadsheet_id = helper_functions.get_sheet_id(
            google_sheet_link=order_spreadsheet
        )
        self.order_sheet_range_to_read = API_INFO_JSON_CONTENTS.get('order_range_sheet_read')
        self.order_sheet_range_to_write = None

        # TODO - define a method that updates the value of the previous
        #  attribute

        self.pallet_info_sheet_link = API_INFO_JSON_CONTENTS.get('pallet_range_sheet_link')
        self.pallet_info_sheet_id = helper_functions.get_sheet_id(
            google_sheet_link=self.pallet_info_sheet_link
        )
        self.pallet_info_read_range = API_INFO_JSON_CONTENTS.get('pallet_range_sheet_name')

        self.api_service = None
        self.sheet_api = None

        self._create_pallet_api_service()

    def get_pallet_range_data(self):
        """ Reads from a Google Spreadsheet some data related to pallet
        ranges and store them in the database. """
        db_writer_class = DatabaseCommunicator(write_to_db=True)
        pallet_ranges = self.sheet_api.values().get(
            spreadsheetId=self.pallet_info_sheet_id,
            range=self.pallet_info_read_range).execute()
        values_to_write = pallet_ranges.get('values', [])[1:]
        for data in values_to_write:
            write_result = db_writer_class.write_to_pallet_table(
                info_to_write=data
            )
        if write_result:
            self.db_updated.emit('Database aggiornato con successo')
        else:
            self.db_not_updated.emit('Aggiornamento di database non riuscito')

    def _create_pallet_api_service(self):
        self.api_service = build('sheets', 'v4', credentials=self.api_creds)
        self.sheet_api = self.api_service.spreadsheets()


if __name__ == '__main__':
    order_link = \
        'https://docs.google.com/spreadsheets/d/13hMFE5_geDifTbeBn4fsFx5MANFSGSCVRY6eAH0SCkA/edit#gid=1330242481'
    test = PedApi(order_spreadsheet=order_link, overwrite_data=True)
    print(test.get_pallet_range_data())
