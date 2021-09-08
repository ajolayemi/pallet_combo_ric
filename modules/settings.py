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
WRITING_CONNECTION_NAME = f'{helper_functions.get_user_name()}_Writer'
DATABASE_DRIVER = 'QSQLITE'
READER_CONNECTION_NAME = f'{helper_functions.get_user_name()}_Reader'


if __name__ == '__main__':
    pass
