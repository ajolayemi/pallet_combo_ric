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
from modules import settings
from modules.box_distributor import Distributor
from modules.db_communicator import DatabaseCommunicator

API_INFO_JSON_CONTENTS = helper_functions.json_file_loader(
    file_name=settings.INFORMATION_JSON
)


class PedApi(QObject):

    # Custom sigs
    started = pyqtSignal(str)
    finished = pyqtSignal(str)
    unfinished = pyqtSignal(str)
    empty_orders = pyqtSignal(str)
    empty_order_table = pyqtSignal(str)

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

        self.pallet_info_sheet_link = API_INFO_JSON_CONTENTS.get('pallet_range_sheet_link')
        self.pallet_info_sheet_id = helper_functions.get_sheet_id(
            google_sheet_link=self.pallet_info_sheet_link
        )
        self.pallet_info_read_range = API_INFO_JSON_CONTENTS.get('pallet_range_sheet_name')

        self.pallet_dict_range = API_INFO_JSON_CONTENTS.get('pallet_dict_range')

        self.api_service = None
        self.sheet_api = None

        self._create_pallet_api_service()

        self.all_orders = []

        # Saves the final data that will be written to google sheet
        self.final_data = []

        # This dict stores information like last pallet number, last pallet letter
        # and the range for writing
        self.pallet_dict = {'last_pallet_num': 0,
                            'last_pallet_letter': "",
                            'order_range_sheet_for_writing': "Feed Algoritmo per PED!N2"}

        if self.for_pallet:
            self.update_sheet_writing_range()
            self.get_all_orders()
            self.populate_pallet_dict()

        self.order_sheet_range_to_write = self.pallet_dict.get(
            'order_range_sheet_for_writing'
        )

    def populate_pallet_dict(self):
        """ Reads from Google sheet and updates this class attribute called pallet_dict."""
        # If user chose not to overwrite existing data
        if not self.overwrite_data:

            pallet_dict_data = self.sheet_api.values().get(
                spreadsheetId=self.order_spreadsheet_id,
                range=self.pallet_dict_range).execute()
            values_read = pallet_dict_data.get('values', [])
            for value in values_read:
                if len(value) > 1:
                    self.pallet_dict.update({value[0]: value[1]})
                else:
                    self.pallet_dict.update({value[0]: ""})

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
        else:
            pass

    def place_boxes_on_pallets_alv(self, current_logistic: str,
                                   boxes_per_pallets_info: dict, pallet_type: str) -> None:
        """ Places boxes on pallets for Alveari. """
        # Get pallet code name
        pallet_code_name = settings.PALLETS_BASE_INFO.get(pallet_type)[0]

        boxes_info = boxes_per_pallets_info['result'].get(pallet_code_name)

        # Start looping over pallets
        for pallet_full_name, pallet_capacity in boxes_info.items():
            pallet_current_capacity = pallet_capacity

            logistic_clients = self.get_logistic_clients(logistic=current_logistic)

            # Start looping over clients
            for client in logistic_clients:

                # If the total ratio of current client is > pallet_current_capacity
                if logistic_clients[client] > pallet_current_capacity:
                    # Go on to the next client
                    continue

                else:
                    # Get client's order
                    client_order = self.get_client_order(client_order_num=client)

                    for order in client_order:
                        product_ordered_code = order[0]
                        qta_ordered = int(order[2])
                        product_pallet_ratio = float(helper_functions.name_controller(
                            name=str(order[6]), char_to_remove=',',
                            new_char='.'
                        ))
                        self.final_data.append([product_ordered_code, qta_ordered, pallet_full_name,
                                                pallet_code_name])

                        pallet_current_capacity -= product_pallet_ratio
                        self.all_orders.remove(order)

    def get_client_order(self, client_order_num: str):
        """ Returns a nested list of all orders pertaining to a certain client
        with client_order_num. """
        client_order = list(filter(lambda x: x[8] == client_order_num and x[0] not in PedApi.processed_orders,
                                   self.all_orders))
        return client_order

    def get_logistic_clients(self, logistic: str) -> dict[str, float]:
        """ Gets all clients that ordered with the logistic value provided
        with the parameter logistic.
        Returns a dict where keys are the clients and values are the total
        number of boxes they ordered (the pallet ratio) """
        current_log_orders = list(filter(lambda x: x[5] == logistic and x[0] not in PedApi.processed_orders,
                                         self.all_orders))
        clients = {}
        for order_ in current_log_orders:
            current_ratio = helper_functions.name_controller(
                name=order_[6], char_to_remove=',', new_char='.'
            )
            if order_[8] not in clients:
                clients[order_[8]] = float(current_ratio)
            else:
                clients[order_[8]] += float(current_ratio)

        # The returned dict is sorted from highest to lowest
        return dict(sorted(clients.items(), key=lambda item: item[1], reverse=True))

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
            log_varieties = self.get_log_varieties(logistic=current_logistic)
            for variety in log_varieties:
                if pallet_cap <= 0:
                    break
                log_variety_order = self.get_varieties_order(logistic=current_logistic, variety=variety)
                if log_variety_order:
                    for current_order in log_variety_order:

                        if pallet_cap <= 0:
                            break
                        product_ordered_code = current_order[0]

                        if product_ordered_code in PedApi.processed_orders:
                            continue

                        qta_ordered = int(current_order[2])
                        product_pallet_ratio = float(helper_functions.name_controller(
                            name=str(current_order[6]), char_to_remove=',',
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

                                occupied_ratio = int(round((possible_product_qta / float(product_pallet_ratio))
                                                           * pallet_initial_capacity))
                                pallet_cap -= occupied_ratio
                                self.final_data.append([product_ordered_code, possible_product_qta, pallet_full_name,
                                                        pallet_code_name])

                                if qta_remaining == 0:
                                    PedApi.processed_orders.append(product_ordered_code)
                                    self.all_orders.remove(current_order)
                                else:
                                    product_qta_in_all_orders = float(helper_functions.name_controller(
                                        name=self.all_orders[self.all_orders.index(current_order)][2],
                                        char_to_remove=',', new_char='.'
                                    ))
                                    # Modify the quantity of the current product
                                    self.all_orders[self.all_orders.index(current_order)][2] = \
                                        str(int(product_qta_in_all_orders - possible_product_qta))

                                    product_ratio_in_all_orders = float(helper_functions.name_controller(
                                        name=self.all_orders[self.all_orders.index(current_order)][6],
                                        char_to_remove=',', new_char='.'
                                    ))

                                    # Modify the ratio of the current product
                                    self.all_orders[self.all_orders.index(current_order)][6] = \
                                        str(int(product_ratio_in_all_orders - occupied_ratio))

    def construct_pallets(self):
        """ Constructs pallets by putting boxes on them. """
        self.started.emit('Started constructing pallet')
        db_reader_cls = DatabaseCommunicator()
        check_table = db_reader_cls.check_table(
            table_name=settings.PALLET_INFO_TABLE)

        # If the Pallet table is empty
        if not check_table:
            self.empty_order_table.emit('Bisogna che aggiorni il database!\n'
                                        'Lo puoi fare cliccando su "Aggiornare DB"')

        # If there is no order
        elif not self.all_orders:
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
                box_distributor_cls = Distributor(last_pallet_num=self.pallet_dict.get('last_pallet_num'),
                                                  last_pallet_alpha=self.pallet_dict.get('last_pallet_letter'))
                for pallet in suggested_pallets:
                    boxes_per_pallets = box_distributor_cls.box_distributor(
                        pallet_type=pallet,
                        boxes_per_pallets=suggested_pallets[pallet][1],
                        logistic_details=[logistic_items[1], logistic_items[2]],
                        tot_boxes_ordered=boxes,
                        tot_pallets=suggested_pallets[pallet][0]
                    )
                    boxes = boxes_per_pallets['remaining_boxes']

                    # Pass the value of boxes_per_pallets to the functions that places boxes
                    # on the pallets
                    # If the current channel is ALV
                    if logistic_items[1] == settings.ALV_CHANNEL_CODE:
                        self.place_boxes_on_pallets_alv(
                            current_logistic=logistic,
                            boxes_per_pallets_info=boxes_per_pallets,
                            pallet_type=pallet
                        )
                    else:

                        self.place_boxes_on_pallets(
                            current_logistic=logistic,
                            boxes_per_pallets_info=boxes_per_pallets,
                            pallet_type=pallet
                        )

                self.pallet_dict.update({'last_pallet_num': boxes_per_pallets.get('last_box_num'),
                                         'last_pallet_letter': boxes_per_pallets.get('last_box_alpha')})

            # write the final data
            write_request_response = self.write_data_to_google_sheet()
            updated_range = write_request_response.get('updates').get('updatedRange')

            # If the data writing request was successful
            if updated_range:
                self.finished.emit('Ho finito di comporre le pedane!')

            else:
                self.unfinished.emit("C'è stato un errore durante la composizione delle pedane")
                # Clear any data written in google sheet
                self.api_service.spreadsheets().values().batchClear(
                    spreadsheetId=self.order_spreadsheet_id,
                    body={'ranges': self.order_sheet_range_to_clear}
                ).execute()

    def get_varieties_order(self, logistic: str, variety: str):
        variety_order = list(filter(lambda x: all((
            x[5] == logistic, x[0] not in PedApi.processed_orders, x[7] == variety)),
                                    self.all_orders))
        return sorted(variety_order, key=lambda x: (x[2], x[5], x[1]), reverse=True)

    def get_log_varieties(self, logistic: str) -> dict:
        """ Returns all varieties pertaining to a specific logistic
        and their respective total boxes ratio from the order contents
        read from Google Spreadsheet. """
        log_varieties = list(filter(lambda x: x[5] == logistic and x[0] not in PedApi.processed_orders,
                                    self.all_orders))
        varieties = {}
        for order_content in log_varieties:
            float_ratio = float(helper_functions.name_controller(
                name=order_content[6], new_char='.',
                char_to_remove=','))
            if order_content[7] not in varieties:
                varieties[order_content[7]] = float_ratio
            else:
                varieties[order_content[7]] += float_ratio
        return dict(sorted(varieties.items(), key=lambda x: x[1], reverse=True))

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
        self.all_orders = sorted(all_orders, key=lambda x: (x[2], x[5], x[1]), reverse=True)

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
        'https://docs.google.com/spreadsheets/d/1umjpTeSty4h6IGnaexrlNyV9b0vPWmif551E7P4hoMI/edit#gid=2110154666'
    test = PedApi(order_spreadsheet=order_link, overwrite_data=True, for_pallets=True)
    test.construct_pallets()
