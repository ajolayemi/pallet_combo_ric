""" Contains some information necessary for the correct
functioning of this algorithm. """

from helper_modules import helper_functions

WINDOW_TITLE = 'PED RiC'
INFORMATION_JSON = '../app_info_json.json'
TO_DO_COMBO_ITEMS = ['Sì', 'No']
GOOGLE_SHEET_WB_NAME = 'Feed Algoritmo per PED'

# Database constants
DATABASE_NAME = 'info_pedane.sqlite'
PALLET_INFO_TABLE = 'Pallets'
CLIENT_INFO_TABLE = 'Clients'
MAX_PALLET_INFO = 5
MAX_CLIENT_INFO = 2
WRITING_CONNECTION_NAME = f'{helper_functions.get_user_name()}_Writer'
DATABASE_DRIVER = 'QSQLITE'
READER_CONNECTION_NAME = f'{helper_functions.get_user_name()}_Reader'


# Some info and functions related to pallets -
# these are information that remain the same for a long time

EURO_PALLET_MAX = 64  # boxes
EURO_PALLET_MIN = 56  # boxes
INDUSTRIAL_PALLET_LIMIT_MAX = 80  # boxes
INDUSTRIAL_PALLET_LIMIT_MIN = 70  # boxes
EURO_LIMIT_CHANGE_FROM = 10  # pallets
INDUSTRIAL_LIMIT_CHANGE_FROM = 14  # pallets


if __name__ == '__main__':
    pass
