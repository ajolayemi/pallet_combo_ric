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
from box_distributor import Distributor

API_INFO_JSON_CONTENTS = helper_functions.json_file_loader(
    file_name=settings.INFORMATION_JSON
)


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

    def place_boxes_on_pallets(self, current_logistic: str,
                               boxes_per_pallets_info: dict):
        current_log_orders = list(filter(lambda x: x[5] == current_logistic, self.all_orders))
        return current_log_orders

    def construct_pallets(self):
        """ Constructs pallets by putting boxes on them. """
        db_reader = DatabaseCommunicator(read_from_db=True)
        # Get all logistics and the total number of boxes each of them has
        all_logs = self.get_all_logistics()
        # Start looping over the dict returned by get_all_logistics method
        for logistic, logistic_items in all_logs.items():

            # logistic_items is a list of this kind
            # [a string concatenation of logistic -- date of shipping -- client name,
            # the corresponding channel of the logistic in question,
            # the total num of boxes the logistic has]

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
                boxes_per_pallets = box_distributor_cls.box_distributor(
                    pallet_type=pallet,
                    boxes_per_pallets=suggested_pallets[pallet][1],
                    logistic_details=[logistic_items[1], logistic_items[2]],
                    tot_boxes_ordered=boxes,
                    tot_pallets=suggested_pallets[pallet][0]
                )
                boxes = boxes_per_pallets.remaining_boxes

                # Pass the value of boxes_per_pallets to the function that places boxes
                # on the pallets
                box_placer = self.place_boxes_on_pallets(
                    current_logistic=logistic,
                    boxes_per_pallets_info=boxes_per_pallets
                )
                print(box_placer)

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
