""" Contains some information necessary for the correct
functioning of this algorithm. """

from helper_modules import helper_functions

WINDOW_TITLE = 'PED RiC'
INFORMATION_JSON = '../app_info_json.json'
TO_DO_COMBO_ITEMS = ['Sì', 'No']
GOOGLE_SHEET_WB_NAME = 'Feed Algoritmo per PED'
GOOGLE_SHEET_INITIAL_WRITING_RANGE = 'Feed Algoritmo per PED!M'

ADP_CHANNEL_CODE = '(Serv-AdP)'

ALV_CHANNEL_CODE = 'ALV'

# Database constants
DATABASE_NAME = 'info_pedane.sqlite'
PALLET_INFO_TABLE = 'Pallets'
CLIENT_INFO_TABLE = 'Clients'
MAX_PALLET_INFO = 7
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

PALLETS_BASE_INFO = {
                'euro': ['Euro', 8],
                'industrial': ['Ind', 10],
                'alternative_euro': ['Euro', 8]
            }

# This keeps track of whether all pallets going to Poland has to be EURO or not
POLAND_ALL_EURO = True
POLAND_LOGISTICS = ['UPS Polska', 'Good Speed',
                    'good Speed_bancali', 'Nagel Polska']

if __name__ == '__main__':
    pass
