#!/usr/bin/env python

""" Communicates with google sheets using Google Sheet API both reading and writing data to
the sheets. """
import math
import re

from PyQt5.QtCore import pyqtSignal, QObject
from google.oauth2 import service_account
from googleapiclient.discovery import build
from helper_modules import helper_functions

# Self defined modules
import settings
from box_distributor import Distributor
from db_communicator import DatabaseCommunicator

API_INFO_JSON_CONTENTS = helper_functions.json_file_loader(
    file_name=settings.INFORMATION_JSON
)


class PedApi(QObject):

    # Custom sigs
    started = pyqtSignal(str)
    finished = pyqtSignal(str)
    unfinished = pyqtSignal(str)
    empty_orders = pyqtSignal(str)

    processed_orders = []

    def __init__(self, order_spreadsheet: str = None, overwrite_data: bool = True,
                 for_pallets: bool = False):
        super(PedApi, self).__init__()

        self.overwrite_data = overwrite_data
        # This is use to minimize the number of time google sheet
        # API is called to read data
        self.for_pallet = for_pallets

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
        self.order_sheet_range_to_clear = API_INFO_JSON_CONTENTS.get('order_range_sheet_to_be_cleared')
        self.order_sheet_range_to_write = None

        self.pallet_info_sheet_link = API_INFO_JSON_CONTENTS.get('pallet_range_sheet_link')
        self.pallet_info_sheet_id = helper_functions.get_sheet_id(
            google_sheet_link=self.pallet_info_sheet_link
        )
        self.pallet_info_read_range = API_INFO_JSON_CONTENTS.get('pallet_range_sheet_name')

        self.api_service = None
        self.sheet_api = None

        self._create_pallet_api_service()

        self.all_orders = []

        # Saves the final data that will be written to google sheet
        self.final_data = []

        self.update_sheet_writing_range()
        self.get_all_orders()

    def write_data_to_google_sheet(self):
        write_request = self.api_service.spreadsheets().values().append(
            spreadsheetId=self.order_spreadsheet_id,
            range=self.order_sheet_range_to_write,
            valueInputOption='USER_ENTERED',
            insertDataOption='OVERWRITE',
            body={'values': self.final_data}
        )
        res = write_request.execute()
        return res

    def update_sheet_writing_range(self):
        """ Clears the existing data in google sheet.
        Updates the range for data writing, last pallet_num and last pallet alpha. """
        if self.overwrite_data:
            # Clear existing data in google sheet
            self.api_service.spreadsheets().values().batchClear(
                spreadsheetId=self.order_spreadsheet_id,
                body={'ranges': self.order_sheet_range_to_clear}
            ).execute()

            # Update writing range
            helper_functions.update_json_content(
                json_file_name=settings.INFORMATION_JSON,
                keys_values_to_update={
                    'order_range_sheet_for_writing': f'{settings.GOOGLE_SHEET_INITIAL_WRITING_RANGE}2',
                    'last_pallet_num': 0,
                    'last_pallet_letter': ''
                }
            )
        else:
            pass

        # Set the value of order_sheet_range_to_write (this class attribute)
        # to the new range
        self.order_sheet_range_to_write = helper_functions.json_file_loader(
            file_name=settings.INFORMATION_JSON).get('order_range_sheet_for_writing')

    def place_boxes_on_pallets(self, current_logistic: str, boxes_per_pallets_info: dict,
                               pallet_type: str) -> None:

        # Get the code name for the current pallet
        pallet_code_name = settings.PALLETS_BASE_INFO.get(pallet_type)[0]

        # Make a copy of the info related to the current pallet_code in
        # boxes_per_pallets_info
        boxes_per_pallets_info_copy = boxes_per_pallets_info['result'][pallet_code_name].copy()

        # Start looping over the boxes_per_pallets_info parameter
        # it is a named tuple containing dicts
        boxes_info = boxes_per_pallets_info['result'].get(pallet_code_name)

        for pallet_full_name, pallet_current_capacity in boxes_info.items():

            pallet_cap = pallet_current_capacity
            # Get all the order related to the current client
            current_log_orders = list(filter(lambda x: x[5] == current_logistic and x[0] not in PedApi.processed_orders,
                                             self.all_orders))
            if current_log_orders:
                for current_order in current_log_orders:
                    if pallet_cap <= 0:
                        break
                    product_ordered_code = current_order[0]

                    if product_ordered_code in PedApi.processed_orders:
                        continue

                    qta_ordered = int(current_order[2])
                    product_pallet_ratio = float(helper_functions.name_controller(
                        name=str(current_order[-1]), char_to_remove=',',
                        new_char='.'
                    ))

                    # Keep track of the qtà of the current product that is on pallet
                    product_qta_on_pallet = 0

                    qta_remaining = int(qta_ordered - product_qta_on_pallet)

                    if qta_remaining == 0:
                        # continue to the next product
                        continue
                    # If the current product_pallet_ratio is <= current pallet_current_capacity
                    if product_pallet_ratio <= round(pallet_cap):
                        data_to_append = [product_ordered_code, qta_remaining, pallet_full_name,
                                          pallet_code_name]
                        self.final_data.append(data_to_append)

                        # Update some values
                        product_qta_on_pallet += qta_remaining
                        qta_remaining = int(qta_ordered - product_qta_on_pallet)
                        pallet_cap -= product_pallet_ratio

                        PedApi.processed_orders.append(product_ordered_code)
                        # Remove the current order from the list of orders
                        self.all_orders.remove(current_order)

                    # Elif product_pallet_ratio > pallet_current_capacity
                    elif product_pallet_ratio > round(pallet_cap):

                        # Access the initial capacity of the current pallet
                        pallet_initial_capacity = boxes_per_pallets_info_copy.get(pallet_full_name)

                        possible_product_qta = round(
                            (round(pallet_cap) / pallet_initial_capacity) * product_pallet_ratio
                        )

                        # Do not put the current box on the pallet if it's possible quantity is <= 0
                        if possible_product_qta <= 0:
                            # Continue to the next product
                            continue
                        else:
                            product_qta_on_pallet += possible_product_qta
                            qta_remaining = qta_ordered - product_qta_on_pallet

                            occupied_ratio = int(round((possible_product_qta / product_pallet_ratio)
                                                       * pallet_initial_capacity))
                            pallet_cap -= occupied_ratio
                            self.final_data.append([product_ordered_code, possible_product_qta, pallet_full_name,
                                                    pallet_code_name])

                            if qta_remaining == 0:
                                PedApi.processed_orders.append(product_ordered_code)
                                self.all_orders.remove(current_order)
                            else:
                                # Modify the quantity of the current product
                                self.all_orders[self.all_orders.index(current_order)][2] = int(
                                    self.all_orders[self.all_orders.index(current_order)][2]) - possible_product_qta

                                # Modify the ratio of the current product
                                self.all_orders[self.all_orders.index(current_order)][-1] =\
                                    int(self.all_orders[self.all_orders.index(current_order)][-1]) - occupied_ratio

    def construct_pallets(self):
        """ Constructs pallets by putting boxes on them. """
        self.started.emit('Started constructing pallet')
        # If there is no order
        if not self.all_orders:
            self.empty_orders.emit('Nessun ordine in manuale!')
        else:
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
                    boxes = boxes_per_pallets['remaining_boxes']

                    # Pass the value of boxes_per_pallets to the function that places boxes
                    # on the pallets
                    self.place_boxes_on_pallets(
                        current_logistic=logistic,
                        boxes_per_pallets_info=boxes_per_pallets,
                        pallet_type=pallet
                    )

            # write the final data
            write_request_response = self.write_data_to_google_sheet()

            # If the data writing request was successful
            if write_request_response:
                self.finished.emit('Ho finito di comporre le pedane!')
                # Update the writing range
                updated_range = write_request_response.get('updates').get('updatedRange')
                last_range = int(re.search(re.compile(r'\d+'), updated_range.split(':')[-1]).group()) + 1
                helper_functions.update_json_content(
                    json_file_name=settings.INFORMATION_JSON,
                    keys_values_to_update={
                        'order_range_sheet_for_writing': f'{settings.GOOGLE_SHEET_INITIAL_WRITING_RANGE}'
                                                         f'{last_range}'})
            else:
                self.unfinished.emit("C'è stato un errore durante la composizione delle pedane")
                # Clear any data written in google sheet
                self.api_service.spreadsheets().values().batchClear(
                    spreadsheetId=self.order_spreadsheet_id,
                    body={'ranges': self.order_sheet_range_to_clear}
                ).execute()

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
        return write_result is not None

    def _create_pallet_api_service(self):
        self.api_service = build('sheets', 'v4', credentials=self.api_creds)
        self.sheet_api = self.api_service.spreadsheets()


if __name__ == '__main__':
    order_link = \
        'https://docs.google.com/spreadsheets/d/13hMFE5_geDifTbeBn4fsFx5MANFSGSCVRY6eAH0SCkA/edit#gid=1330242481'
    test = PedApi(order_spreadsheet=order_link, overwrite_data=True)
    print(test.construct_pallets())
