#!/usr/bin/env python

""" Communicates with google sheets using Google Sheet API both reading and writing data to
the sheets. """

import string
from PyQt5.QtCore import pyqtSignal, QObject
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Self defined modules
import settings
from helper_modules import helper_functions
from collections import namedtuple


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


if __name__ == '__main__':
    pass
