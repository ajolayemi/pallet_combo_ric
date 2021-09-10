#!/usr/bin/env python

""" Communicates with google sheets using Google Sheet API both reading and writing data to
the sheets. """
import math
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


class Distributor:

    def __init__(self):
        self.all_api_contents = helper_functions.json_file_loader(
            file_name='../app_info_json.json'
        )
        self.last_ped_num = self.all_api_contents.get('last_pallet_num')
        self.last_ped_alpha = self.all_api_contents.get('last_pallet_letter')

    def box_distributor(self, pallet_type: str, tot_pallets: int,
                        boxes_per_pallets: int, tot_boxes_ordered: int,
                        logistic_details: list):
        """ Distributes all the boxes ordered provided by the tot_boxes_ordered
        parameter on the total available pallets given by tot_pallets parameter value.
        For example, if the total available pallets for a certain logistic is 10 and the total
        number of boxes ordered are 1000, this function distributes all the thousand boxes
        on the 10 pallets.
        It returns a named tuple. """

        pallet_type_base_info = settings.PALLETS_BASE_INFO.get(pallet_type)

        if pallet_type_base_info and logistic_details:
            pallet_code_name = pallet_type_base_info[0]
            pallet_base_value = pallet_type_base_info[1]
            result = {pallet_code_name: {}}
            remaining_boxes = tot_boxes_ordered
            remaining_pallets = tot_pallets

            # Loop over the value provided for total_pallets
            for current_pallet_num in range(1, int(tot_pallets) + 1):
                self.last_ped_num += 1
                # logistic_details is a list that contains the following information
                # [client channel of order (B2C - LV, B2C - PL), date of shipping]
                if logistic_details[0] == settings.ADP_CHANNEL_CODE:
                    self.last_ped_alpha = helper_functions.get_next_alpha(
                        current_alpha=pallet_alphabet
                    )
                    current_pallet_name = f"PED {self.last_ped_num}{self.last_ped_alpha} " \
                                          f"{logistic_details[0]} del {logistic_details[1]}"
                else:
                    current_pallet_name = f"PED {self.last_ped_num} {logistic_details[0]} " \
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

            result_tuple = namedtuple('BoxDivision', ['box_division', 'remaining_boxes'])
            helper_functions.update_json_content(
                json_file_name='../app_info_json.json',
                keys_values_to_update={'last_pallet_num': self.last_ped_num,
                                       'last_pallet_letter': self.last_ped_alpha}
            )
            return result_tuple(result, remaining_boxes)


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

        self.all_orders = None

        self._create_pallet_api_service()
        self.get_all_orders()

    def construct_pallets(self):
        """ Constructs pallets by putting boxes on them. """
        db_reader = DatabaseCommunicator(read_from_db=True)
        # Get all logistics and the total number of boxes each of them has
        all_logs = self.get_all_logistics()
        # Start looping over the dict returned by get_all_logistics method
        for logistic, logistic_items in all_logs.items():
            boxes = math.ceil(logistic_items[0])
            # Check to see if the current logistic is for Poland
            if logistic.split('--')[0].strip() in settings.POLAND_LOGISTICS:
                suggested_pallets = db_reader.get_pallet_info_pl(
                    total_boxes=boxes
                )
            else:
                # Pass the total number of boxes each logistics has to the function that suggests
                # pallets
                suggested_pallets = db_reader.get_pallet_info(
                    total_boxes=boxes
                )
            box_distributor_cls = Distributor()
            for pallet in suggested_pallets:
                distributed_boxes = box_distributor_cls.box_distributor(
                    pallet_type=pallet,
                    boxes_per_pallets=suggested_pallets[pallet][1],
                    logistic_details=[logistic_items[1], logistic_items[2]],
                    tot_boxes_ordered=boxes,
                    tot_pallets=suggested_pallets[pallet][0]
                )
                boxes = distributed_boxes.remaining_boxes

    def get_all_logistics(self) -> dict:
        """ Returns all logistics and there respective total boxes
        from the order contents read from Google Spreadsheet. """
        logistics = {}
        for order_content in self.all_orders:
            # Removes , from numbers that have it
            float_num = helper_functions.name_controller(
                name=order_content[6], new_char='.',
                char_to_remove=',')
            if order_content[5] not in logistics:
                logistics[order_content[5]] = [float(float_num), order_content[3].strip(), order_content[4]]
            else:
                logistics[order_content[5]][0] += float(float_num)

        return logistics

    def get_all_orders(self):
        """ Reads from the spreadsheet that contains client orders and returns
        the data from it. """
        order_data = self.sheet_api.values().get(
            spreadsheetId=self.order_spreadsheet_id,
            range=self.order_sheet_range_to_read
        ).execute()
        all_orders = order_data.get('values', [])[1:]
        self.all_orders = sorted(all_orders, key=lambda x: (x[5], x[1], x[2]))

    def get_pallet_range_data(self):
        """ Reads from a Google Spreadsheet some data related to pallet
        ranges and store them in the database. """
        db_writer_class = DatabaseCommunicator(write_to_db=True)
        pallet_data = self.sheet_api.values().get(
            spreadsheetId=self.pallet_info_sheet_id,
            range=self.pallet_info_read_range).execute()
        values_to_write = pallet_data.get('values', [])[1:]
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
    test.construct_pallets()