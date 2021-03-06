#!/usr/bin/env python

""" Communicates with google sheets using Google Sheet API both reading and writing data to
the sheets. """
import math

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
    empty_order_table = pyqtSignal(str)

    processed_orders = []

    def __init__(self, order_spreadsheet: str = None, overwrite_data: bool = True,
                 for_pallets: bool = False, user_max_boxes: int = 0):
        super(PedApi, self).__init__()

        self.overwrite_data = overwrite_data
        # This is use to minimize the number of time google sheet
        # API is called to read data
        self.for_pallet = for_pallets

        self.user_max_boxes = user_max_boxes

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

        # Some information related to Google Sheet where pallet ranges are stored
        self.pallet_info_sheet_link = API_INFO_JSON_CONTENTS.get('pallet_range_sheet_link')
        self.pallet_info_sheet_id = helper_functions.get_sheet_id(
            google_sheet_link=self.pallet_info_sheet_link
        )
        self.pallet_info_read_range = API_INFO_JSON_CONTENTS.get('pallet_range_sheet_name')

        # Some information related to Google Sheet where pallet ranges related to Kievit are stored
        self.kievit_sheet_link = API_INFO_JSON_CONTENTS.get('kievit_sheet_link')
        self.kievit_sheet_id = helper_functions.get_sheet_id(
            google_sheet_link=self.kievit_sheet_link
        )
        self.kievit_range_to_read = API_INFO_JSON_CONTENTS.get('kievit_sheet_range')

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
                            'order_range_sheet_for_writing': "Feed Algoritmo per PED!Q2"}

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

    def place_boxes_on_pallets_corb(self, corbari_logistic: str,
                                    boxes_per_pallets_info: dict, pallet_type: str) -> None:

        pallet_code_name = settings.PALLETS_BASE_INFO.get(pallet_type)[0]

        boxes_info = boxes_per_pallets_info['result'].get(pallet_code_name)

        for pallet_full_name, pallet_details in boxes_info.items():
            pallet_cap = pallet_details[0]

            corb_orders = self.get_corbari_orders(corbari_logistic=corbari_logistic)
            if corb_orders:
                for current_corb_order in corb_orders:

                    if pallet_cap <= 0:
                        break

                    product_ordered_code = current_corb_order[0]

                    if product_ordered_code in PedApi.processed_orders:
                        continue
                    qta_ordered = int(current_corb_order[2])
                    product_pallet_ratio = float(helper_functions.name_controller(
                        name=str(current_corb_order[6]), char_to_remove=',',
                        new_char='.'
                    ))

                    qta_on_pallet = 0
                    qta_remaining = int(qta_ordered - qta_on_pallet)

                    if qta_remaining == 0:
                        continue
                    elif product_pallet_ratio <= round(pallet_cap):
                        self.final_data.append([product_ordered_code, qta_remaining, pallet_full_name,
                                                pallet_code_name, pallet_details[1], pallet_details[2]])

                        # Update some values
                        qta_on_pallet += qta_remaining
                        qta_remaining = int(qta_ordered - qta_on_pallet)
                        pallet_cap -= product_pallet_ratio

                        PedApi.processed_orders.append(product_ordered_code)
                        self.all_orders.remove(current_corb_order)
                    elif product_pallet_ratio > round(pallet_cap):

                        possible_product_qta = round((pallet_cap / product_pallet_ratio) * qta_remaining)

                        if possible_product_qta <= 0:
                            continue
                        else:
                            qta_on_pallet += possible_product_qta
                            qta_remaining = int(qta_ordered - qta_on_pallet)

                            ratio_occupied = (product_pallet_ratio / qta_ordered) * possible_product_qta
                            pallet_cap -= ratio_occupied
                            self.final_data.append([product_ordered_code, possible_product_qta, pallet_full_name,
                                                    pallet_code_name, pallet_details[1], pallet_details[2]])

                            if qta_remaining == 0:
                                PedApi.processed_orders.append(product_ordered_code)
                                self.all_orders.remove(current_corb_order)
                            else:
                                product_qta_in_all_orders = float(
                                    helper_functions.name_controller(
                                        name=self.all_orders[self.all_orders.index(current_corb_order)][2],
                                        char_to_remove=',', new_char='.'
                                    )
                                )

                                # Modify the quantity of the current product
                                self.all_orders[self.all_orders.index(current_corb_order)][2] = \
                                    str(int(product_qta_in_all_orders - possible_product_qta))

                                product_ratio_in_all_orders = float(helper_functions.name_controller(
                                    name=self.all_orders[self.all_orders.index(current_corb_order)][6],
                                    char_to_remove=',', new_char='.'
                                ))

                                # Modify the ratio of the current product
                                self.all_orders[self.all_orders.index(current_corb_order)][6] = \
                                    str(int(product_ratio_in_all_orders - ratio_occupied))

    def place_boxes_on_pallets_alv(self, current_logistic: str,
                                   boxes_per_pallets_info: dict, pallet_type: str) -> None:
        """ Places boxes on pallets for Alveari. """
        # Get pallet code name
        pallet_code_name = settings.PALLETS_BASE_INFO.get(pallet_type)[0]

        boxes_info = boxes_per_pallets_info['result'].get(pallet_code_name)

        # Start looping over pallets
        for pallet_full_name, pallet_details in boxes_info.items():
            pallet_current_capacity = pallet_details[0]

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
                                                pallet_code_name, pallet_details[1], pallet_details[2]])

                        pallet_current_capacity -= product_pallet_ratio
                        self.all_orders.remove(order)

    def place_boxes_on_pallets(self, current_logistic: str, boxes_per_pallets_info: dict,
                               pallet_type: str) -> None:

        # Get the code name for the current pallet
        pallet_code_name = settings.PALLETS_BASE_INFO.get(pallet_type)[0]

        # Start looping over the boxes_per_pallets_info parameter
        # it is a named tuple containing dicts
        boxes_info = boxes_per_pallets_info['result'].get(pallet_code_name)

        for pallet_full_name, pallet_details in boxes_info.items():

            pallet_cap = pallet_details[0]
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

                        # Keep track of the qt?? of the current product that is on pallet
                        product_qta_on_pallet = 0

                        qta_remaining = int(qta_ordered - product_qta_on_pallet)

                        if qta_remaining == 0:
                            # continue to the next product
                            continue
                        # If the current product_pallet_ratio is <= current pallet_details
                        if product_pallet_ratio <= round(pallet_cap):
                            data_to_append = [product_ordered_code, qta_remaining, pallet_full_name,
                                              pallet_code_name, pallet_details[1], pallet_details[2]]
                            self.final_data.append(data_to_append)

                            # Update some values
                            product_qta_on_pallet += qta_remaining
                            qta_remaining = int(qta_ordered - product_qta_on_pallet)
                            pallet_cap -= product_pallet_ratio

                            PedApi.processed_orders.append(product_ordered_code)
                            # Remove the current order from the list of orders
                            self.all_orders.remove(current_order)

                        # Elif product_pallet_ratio > pallet_details
                        elif product_pallet_ratio > round(pallet_cap):

                            possible_product_qta = round((pallet_cap / product_pallet_ratio) * qta_remaining)

                            # Do not put the current box on the pallet if it's possible quantity is <= 0
                            if possible_product_qta <= 0:
                                # Continue to the next product
                                continue
                            else:
                                product_qta_on_pallet += possible_product_qta
                                qta_remaining = qta_ordered - product_qta_on_pallet

                                occupied_ratio = (product_pallet_ratio / qta_ordered) * possible_product_qta
                                pallet_cap -= occupied_ratio
                                self.final_data.append([product_ordered_code, possible_product_qta, pallet_full_name,
                                                        pallet_code_name, pallet_details[1], pallet_details[2]])

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

    def place_boxes_on_pallets_adp(self, adp_logistic: str, pallet_type: str,
                                   pallet_number: str, pallet_alpha: str,
                                   pallet_full_name: str) -> None:
        """ Places boxes on pallets pertaining to Albero del Paradiso. """
        # Get orders pertaining to the current adp_logistic

        # Since ADP construct it's pallets already, add the returned order directly to
        # the list of final data to be written
        current_adp_orders = self.get_adp_log_orders(adp_logistic=adp_logistic)
        for order in current_adp_orders:
            data_to_append = [order[0], int(order[2]), pallet_full_name, pallet_type,
                              pallet_alpha, pallet_number]
            self.final_data.append(data_to_append)
            self.all_orders.remove(order)
            PedApi.processed_orders.append(order)

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
                log_details = logistic.split('--')[0].strip()

                # If the current logistic is for ADP
                if logistic_items[1] == settings.ADP_CHANNEL_CODE:
                    split_logistic = logistic.split(' -- ')
                    # Get the suggested pallet alpha
                    suggested_pallet_alpha = split_logistic[3].strip()
                    suggested_pallet_type = split_logistic[2].strip()
                    # Get the suggested pallet type

                    # Get the number of pallet
                    last_pallet_num = self.pallet_dict.get('last_pallet_num')

                    # Call upon the method that returns a valid pallet name
                    adp_distributor_cls = Distributor(last_pallet_num=last_pallet_num,
                                                      last_pallet_alpha=suggested_pallet_alpha)

                    adp_log_details = [logistic_items[1], logistic_items[2]]

                    # The function called below returns a tuple where the first item is the
                    # pallet full name and the other item is the pallet's number
                    pallet_full_name, pallet_number = adp_distributor_cls.distribute_adp_boxes(
                        logistic_details=adp_log_details
                    )
                    # Call upon the function that places adp boxes on it's pallet passing in the
                    # necessary parameters
                    self.place_boxes_on_pallets_adp(
                        adp_logistic=logistic, pallet_type=suggested_pallet_type,
                        pallet_number=pallet_number, pallet_alpha=suggested_pallet_alpha,
                        pallet_full_name=pallet_full_name
                    )

                    # Update pallet_dict
                    self.pallet_dict.update({'last_pallet_num': last_pallet_num + 1})

                    # Go on to the next logistic
                    continue

                # If user has entered a value for max_boxes in the GUI and the current
                # logistic is one to which such rule is applied
                elif log_details in settings.POLAND_LOGISTICS_OVERWRITE \
                        and self.user_max_boxes > 0:
                    suggested_pallets = db_reader.get_pallet_info_pl(
                        total_boxes=boxes, user_max=self.user_max_boxes
                    )

                elif log_details in settings.POLAND_LOGISTICS:
                    suggested_pallets = db_reader.get_pallet_info_pl(total_boxes=boxes)

                # Check to see maybe current logistic is for Kievit
                elif log_details in settings.KIEVIT_LOGISTICS:
                    suggested_pallets = db_reader.get_kievit_pallet_info(
                        total_boxes=boxes
                    )

                else:
                    # Pass the total number of boxes each logistics has to the function that suggests
                    # pallets
                    suggested_pallets = db_reader.get_pallet_info(
                        total_boxes=boxes
                    )

                box_distributor_cls = Distributor(last_pallet_num=self.pallet_dict.get('last_pallet_num'),
                                                  last_pallet_alpha='')

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

                    elif log_details in settings.CORBARI_LOGISTICS:
                        self.place_boxes_on_pallets_corb(
                            corbari_logistic=logistic,
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

            # Clear the list that stores already processed orders
            PedApi.processed_orders.clear()

            updated_range = write_request_response.get('updates').get('updatedRange')

            # If the data writing request was successful
            if updated_range:
                self.finished.emit('Ho finito di comporre le pedane!')

            else:
                self.unfinished.emit("C'?? stato un errore durante la composizione delle pedane")
                # Clear any data written in google sheet
                self.api_service.spreadsheets().values().batchClear(
                    spreadsheetId=self.order_spreadsheet_id,
                    body={'ranges': self.order_sheet_range_to_clear}
                ).execute()

    def get_adp_log_orders(self, adp_logistic: str):
        """ Returns a nested list of all orders pertaining to the current adp_logistic. """
        return list(filter(lambda x: x[5] == adp_logistic and x[0] not in PedApi.processed_orders,
                           self.all_orders))

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

    def get_varieties_order(self, logistic: str, variety: str):
        variety_order = list(filter(lambda x: all((
            x[5] == logistic, x[0] not in PedApi.processed_orders, x[7] == variety)),
                                    self.all_orders))
        return sorted(variety_order, key=lambda x: (x[2], x[5], x[1], x[4], x[3]), reverse=True)

    def get_corbari_orders(self, corbari_logistic: str) -> list[list]:
        """ Gets all orders pertaining to the entered corbari_logistic"""
        log_orders = list(filter(lambda x: x[5] == corbari_logistic and x[0] not in PedApi.processed_orders,
                                 self.all_orders))
        return sorted(log_orders, key=lambda x: x[9], reverse=True)

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
        sort_varieties = dict(sorted(varieties.items(), key=lambda x: x[1], reverse=True))

        final_data = {}
        # Loop over sort_varieties to check if their are MIX_BOXES
        for product_code, value in sort_varieties.items():
            if product_code.split('--')[0].strip() == settings.MIX_BOX_NAME:
                final_data[product_code] = value

        # At the end, add the remaining products
        final_data.update(sort_varieties)
        return final_data

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
                logistics[order_content[5]] = [float(float_num), order_content[3].strip(), order_content[4],
                                               order_content[10]]
            else:
                logistics[order_content[5]][0] += float(float_num)

        # Sort logistics first by their shipping date, then by the name of their channel and lastly by
        # The position of the alphabet given to them
        # This is to prevent the algorithm from processing orders of the same channel at different interval
        return dict(sorted(logistics.items(), key=lambda x: (x[1][2], x[1][1], int(x[1][3]))))

    def get_all_orders(self):
        """ Reads from the spreadsheet that contains client orders and returns
        the data from it. """
        order_data = self.sheet_api.values().get(
            spreadsheetId=self.order_spreadsheet_id,
            range=self.order_sheet_range_to_read
        ).execute()
        all_orders = order_data.get('values', [])[1:]
        self.all_orders = sorted(all_orders, key=lambda x: (x[2], x[5], x[1], x[4]), reverse=True)

    def update_kievit_pallet_table(self):
        """ Reads from a Google Spreadsheet some data related to Kievit pallet
        ranges and stores them in the database. """
        db_writer_class = DatabaseCommunicator(write_to_db=True)
        pallet_data = self.sheet_api.values().get(
            spreadsheetId=self.kievit_sheet_id,
            range=self.kievit_range_to_read).execute()
        values_to_write = pallet_data.get('values', [])[1:]
        for data in values_to_write:
            write_result = db_writer_class.write_to_kievit_pallet_table(
                info_to_write=data
            )
        return write_result is not None

    def update_pallet_table(self):
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
    pass
