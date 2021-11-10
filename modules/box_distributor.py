#!/usr/bin/env python

""" Handles the logic behind the correct placement of boxes on
pallets. """

from collections import namedtuple

# Self defined module
import settings
from helper_modules import helper_functions


class Distributor:

    def __init__(self, last_pallet_num: int,
                 last_pallet_alpha: str):

        self.last_ped_num = int(last_pallet_num) + 1
        self.last_ped_alpha = last_pallet_alpha

    def distribute_adp_boxes(self, logistic_details: list):
        """ Returns the appropriate pallet name for ADP """
        if logistic_details[0] == settings.ADP_CHANNEL_CODE:
            current_pallet_name = f"PED {self.last_ped_num} {self.last_ped_alpha} " \
                                  f"{logistic_details[0]} del {logistic_details[1]}"
            return current_pallet_name, self.last_ped_num

    def box_distributor(self, pallet_type: str, tot_pallets: int,
                        boxes_per_pallets: int, tot_boxes_ordered: int,
                        logistic_details: list) -> dict:
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
                # logistic_details is a list that contains the following information
                # [client channel of order (B2C - LV, B2C - PL), date of shipping]
                if logistic_details[0] == settings.ADP_CHANNEL_CODE:
                    self.last_ped_alpha = helper_functions.get_next_alpha(
                        current_alpha=self.last_ped_alpha
                    )
                    current_pallet_name = f"PED {self.last_ped_num} {self.last_ped_alpha} " \
                                          f"{logistic_details[0]} del {logistic_details[1]}"

                else:
                    current_pallet_name = f"PED {self.last_ped_num} {logistic_details[0]} " \
                                        f"del {logistic_details[1]}"

                # If the current remaining boxes is less than the value of boxes_per_pallets
                if remaining_boxes < boxes_per_pallets:
                    result[pallet_code_name][current_pallet_name] = [remaining_boxes, self.last_ped_alpha,
                                                                     self.last_ped_num]
                    remaining_boxes -= remaining_boxes
                    remaining_pallets -= 1
                    self.last_ped_num += 1

                # If the value of boxes_per_pallets * tot_pallets <= remaining_boxes
                # distribute the boxes in tot_pallets equally
                elif (boxes_per_pallets * remaining_pallets) <= remaining_boxes:
                    result[pallet_code_name][current_pallet_name] = [boxes_per_pallets, self.last_ped_alpha,
                                                                     self.last_ped_num]
                    remaining_boxes -= boxes_per_pallets
                    remaining_pallets -= 1
                    self.last_ped_num += 1

                # If the value of boxes_per_pallets * tot_pallets > tot_boxes_ordered
                # do the following
                else:
                    # If the current value of remaining_boxes // remaining_pallets
                    # is not a multiple of the base of the pallet.
                    if (remaining_boxes // remaining_pallets) % pallet_base_value:
                        valid_boxes = helper_functions.get_multiples_of(
                            number=pallet_base_value, multiple_start=remaining_boxes // remaining_pallets,
                            multiple_limit=boxes_per_pallets
                        )[0]
                        result[pallet_code_name][current_pallet_name] = [valid_boxes, self.last_ped_alpha,
                                                                         self.last_ped_num]
                        remaining_boxes -= valid_boxes
                        remaining_pallets -= 1
                        self.last_ped_num += 1

                    else:
                        result[pallet_code_name][current_pallet_name] = [remaining_boxes // remaining_pallets,
                                                                         self.last_ped_alpha, self.last_ped_num]
                        remaining_boxes -= remaining_boxes // remaining_pallets
                        remaining_pallets -= 1
                        self.last_ped_num += 1

            return {'result': result, 'remaining_boxes': remaining_boxes, 'last_box_num': self.last_ped_num - 1,
                    'last_box_alpha': self.last_ped_alpha}


if __name__ == '__main__':
    pass
