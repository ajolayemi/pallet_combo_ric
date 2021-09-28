#!/usr/bin/env python

""" Communicates with the database that stores some necessary
information needed in this project. """


from PyQt5.QtSql import QSqlQuery, QSqlDatabase


# self defined modules
import settings
from helper_modules import helper_functions


def determine_max_per_pallet(pallet_name: str, tot_pallet: int, total_boxes_ordered: int,
                             alternative_max_min: int = 0, is_kievit: bool = False):
    if not tot_pallet:
        return 0, 0
    else:

        if pallet_name == 'euro' or pallet_name == 'alternative_euro':
            if alternative_max_min > 0:
                max_per_pallet = alternative_max_min

            elif is_kievit:
                max_per_pallet = helper_functions.get_pallet_limit(
                    limit_decider_range=settings.EURO_LIMIT_CHANGE_FROM,
                    tot_pallet=tot_pallet, max_capacity=settings.KIEVIT_EURO_MAX,
                    min_capacity=settings.KIEVIT_EURO_MIN
                )
            else:
                max_per_pallet = helper_functions.get_pallet_limit(
                    limit_decider_range=settings.EURO_LIMIT_CHANGE_FROM,
                    tot_pallet=tot_pallet, max_capacity=settings.EURO_PALLET_MAX,
                    min_capacity=settings.EURO_PALLET_MIN
                )

        else:
            if is_kievit:
                max_per_pallet = helper_functions.get_pallet_limit(
                    limit_decider_range=settings.INDUSTRIAL_LIMIT_CHANGE_FROM,
                    min_capacity=settings.KIEVIT_IND_MIN,
                    max_capacity=settings.KIEVIT_IND_MAX,
                    tot_pallet=tot_pallet
                )
            else:
                max_per_pallet = helper_functions.get_pallet_limit(
                    limit_decider_range=settings.INDUSTRIAL_LIMIT_CHANGE_FROM,
                    min_capacity=settings.INDUSTRIAL_PALLET_LIMIT_MIN,
                    max_capacity=settings.INDUSTRIAL_PALLET_LIMIT_MAX,
                    tot_pallet=tot_pallet
                )

        # If the max_per_pallet value is equals the maximum capacity of a pallet
        if any((max_per_pallet == settings.INDUSTRIAL_PALLET_LIMIT_MAX,
                max_per_pallet == settings.EURO_PALLET_MAX,
               max_per_pallet == settings.KIEVIT_EURO_MAX,
                max_per_pallet == settings.KIEVIT_IND_MAX)):
            return tot_pallet, max_per_pallet

        # elif the total number of boxes ordered % the max capacity of a pallet == 0
        elif total_boxes_ordered % max_per_pallet == 0:
            final_tot_pallet = int(total_boxes_ordered / max_per_pallet)
            return final_tot_pallet, max_per_pallet
        else:
            final_tot_pallet = total_boxes_ordered // max_per_pallet + 1
            return final_tot_pallet, max_per_pallet


class DatabaseCommunicator:
    """ Communicates with the database used in this project. """

    def __init__(self, write_to_db: bool = False,
                 read_from_db: bool = True):
        self.db_driver = settings.DATABASE_DRIVER
        self.db_name = settings.DATABASE_NAME

        if write_to_db:
            self.con_name = settings.WRITING_CONNECTION_NAME
        elif read_from_db:
            self.con_name = settings.READER_CONNECTION_NAME

        self.pallet_table_name = settings.PALLET_INFO_TABLE
        self.kievit_pallet_table = settings.KIEVIT_PALLET_TABLE
        self.client_table_name = settings.CLIENT_INFO_TABLE

        self.con_error = False
        self.connection = None

    def drop_table(self, table_name: str) -> bool:
        """ Drops table.
         Returns True if the drop request was successful, False otherwise"""
        if not self.connection:
            self.create_connection()
        delete_query = QSqlQuery(self.connection)
        delete_query.exec_(f'DROP TABLE {table_name}')
        if delete_query.isActive():
            return True
        else:
            return False

    def check_table(self, table_name) -> bool:
        """ Returns True if the said table is not empty,
        False otherwise. """
        if not self.connection:
            self.create_connection()
        check_query = QSqlQuery(self.connection)
        query = f'SELECT Max_Value FROM {table_name}'
        check_query.exec_(query)
        check_query.first()
        record_check = check_query.value(
            check_query.record().indexOf(
                "Max_Value"
            )
        )

        check_query.finish()
        return record_check is not None

    def get_pallet_info_pl(self, total_boxes: int,
                           user_max: int = 0):
        """ Returns the suggested pallet combination necessary for the
        total_boxes entered for all logistics that are for Poland """
        if not self.connection:
            self.create_connection()

        pl_pallet_info_query = QSqlQuery(self.connection)
        query = f'SELECT Poland_Euro FROM {self.pallet_table_name} ' \
                f'WHERE Min_Value <= {total_boxes} AND Max_Value >= {total_boxes}'
        if pl_pallet_info_query.prepare(query):
            pl_pallet_info_query.exec_()

            pl_pallet_info_query.first()
            pl_euro_pallet = pl_pallet_info_query.value(
                pl_pallet_info_query.record().indexOf('Poland_Euro')
            )
            if user_max > 0:
                return {'euro': determine_max_per_pallet(pallet_name='euro', tot_pallet=pl_euro_pallet,
                                                         total_boxes_ordered=total_boxes,
                                                         alternative_max_min=user_max)}

            return {'euro': determine_max_per_pallet(pallet_name='euro', tot_pallet=pl_euro_pallet,
                                                     total_boxes_ordered=total_boxes)}

    def get_kievit_pallet_info(self, total_boxes: int):
        """ Returns the suggested pallet combination necessary for the
        total_boxes entered for Kievit's order. """
        if not self.connection:
            self.create_connection()

        kievit_pallet_query = QSqlQuery(self.connection)
        query = f'SELECT Euro, Industrial ' \
                f'FROM {self.kievit_pallet_table} WHERE Min_Value <= {total_boxes} ' \
                f'AND Max_Value >= {total_boxes}'

        if kievit_pallet_query.prepare(query):

            kievit_pallet_query.exec_()
            kievit_pallet_query.first()
            euro_pallet = kievit_pallet_query.value(
                kievit_pallet_query.record().indexOf('Euro')
            )

            ind_pallet = kievit_pallet_query.value(
                kievit_pallet_query.record().indexOf('Industrial')
            )

            if all((not euro_pallet, not ind_pallet)):
                return {}

            pallets = {
                'euro': euro_pallet,
                'industrial': ind_pallet,
            }
            remaining_boxes = total_boxes
            final_pallets = {}
            for pallet in pallets:
                if not pallets[pallet]:
                    continue
                else:
                    final_pallets[pallet] = determine_max_per_pallet(pallet_name=pallet, tot_pallet=pallets[pallet],
                                                                     total_boxes_ordered=remaining_boxes,
                                                                     is_kievit=True)
                    remaining_boxes -= final_pallets[pallet][0] * final_pallets[pallet][1]

            return dict(sorted(final_pallets.items(), key=lambda x: x[1][0] * x[1][1], reverse=True))
        else:
            return {}

    def get_pallet_info(self, total_boxes: int):
        """ Returns the suggested pallet combination necessary for the
        total_boxes entered for all logistics that aren't for Poland. """
        if not self.connection:
            self.create_connection()

        pallet_info_query = QSqlQuery(self.connection)
        query = f'SELECT Euro, Industrial, Alternative_Euro ' \
                f'FROM {self.pallet_table_name} WHERE Min_Value <= {total_boxes}' \
                f' and Max_Value >= {total_boxes}'
        if pallet_info_query.prepare(query):
            pallet_info_query.exec_()

            pallet_info_query.first()

            euro_pallet = pallet_info_query.value(
                pallet_info_query.record().indexOf('Euro')
            )
            industrial_pallet = pallet_info_query.value(
                pallet_info_query.record().indexOf('Industrial')
            )
            alternative_euro = pallet_info_query.value(
                pallet_info_query.record().indexOf('Alternative_Euro')
            )
            # If no value is found for the specified total_boxes
            if all((not euro_pallet, not industrial_pallet, not alternative_euro)):
                return {}

            pallets = {
                'euro': euro_pallet,
                'industrial': industrial_pallet,
                'alternative_euro': alternative_euro
            }
            # If there is a value for alternative euro
            if pallets.get('alternative_euro'):
                return {'alternative_euro':
                        determine_max_per_pallet(pallet_name='alternative_euro',
                                                 tot_pallet=pallets.get('alternative_euro'),
                                                 total_boxes_ordered=total_boxes)}

            remaining_boxes = total_boxes
            final_pallets = {}
            for pallet in pallets:
                if not pallets[pallet]:
                    continue
                else:
                    final_pallets[pallet] = determine_max_per_pallet(pallet_name=pallet, tot_pallet=pallets[pallet],
                                                                     total_boxes_ordered=remaining_boxes)
                    remaining_boxes -= final_pallets[pallet][0] * final_pallets[pallet][1]

            return final_pallets
        else:
            return {}

    def write_to_kievit_pallet_table(self, info_to_write: list):
        """ Writes the necessary information passed into info_to_write parameter
        into kievit table in the database used in this project.
        """
        if len(info_to_write) == settings.MAX_KIEVIT_INFO:
            self.create_kievit_pallet_table()
            if not self.connection:
                self.create_connection()
            pallet_writer_query = QSqlQuery(self.connection)
            query = (
                f"""INSERT INTO {self.kievit_pallet_table} (
                Min_Value,
                Max_Value,
                Euro,
                Industrial)
                VALUES (?, ?, ?, ?)"""
            )
            if pallet_writer_query.prepare(query):
                pallet_writer_query.addBindValue(int(info_to_write[0]))
                pallet_writer_query.addBindValue(int(info_to_write[1]))
                pallet_writer_query.addBindValue(int(info_to_write[2]))
                pallet_writer_query.addBindValue(int(info_to_write[3]))

                pallet_writer_query.exec_()
                return True

    def write_to_pallet_table(self, info_to_write: list):
        """ Writes the necessary information passed into info_to_write parameter
        into pallet_table in the database used in this project.
        """
        if len(info_to_write) == settings.MAX_PALLET_INFO:
            self.create_pallet_table()
            if not self.connection:
                self.create_connection()
            pallet_writer_query = QSqlQuery(self.connection)
            query = (
                f"""INSERT INTO {self.pallet_table_name} (
                Min_Value,
                Max_Value,
                Euro,
                Industrial,
                Alternative_Euro,
                Poland_Euro)
                VALUES (?, ?, ?, ?, ?, ?)"""
            )
            if pallet_writer_query.prepare(query):
                pallet_writer_query.addBindValue(int(info_to_write[0]))
                pallet_writer_query.addBindValue(int(info_to_write[1]))
                pallet_writer_query.addBindValue(int(info_to_write[2]))
                pallet_writer_query.addBindValue(int(info_to_write[3]))
                pallet_writer_query.addBindValue(int(info_to_write[4]))
                pallet_writer_query.addBindValue(int(info_to_write[5]))

                pallet_writer_query.exec_()
                return True

    def create_pallet_table(self):
        """ Creates the table where information related to pallets
        is stored. """
        if not self.connection:
            self.create_connection()

        pallet_query = QSqlQuery(self.connection)
        query = (
            f""" CREATE TABLE IF NOT EXISTS {self.pallet_table_name} (
            Min_Value INTEGER,
            Max_Value INTEGER,
            Euro INTEGER,
            Industrial INTEGER,
            Alternative_Euro INTEGER,
            Poland_Euro INTEGER
            )"""
        )
        pallet_query.exec_(query)

    def create_kievit_pallet_table(self):
        """ Creates the table where information related to Kievit (a special client)
        pallets information is stored. """
        if not self.connection:
            self.create_connection()

        pallet_query = QSqlQuery(self.connection)
        query = (
            f""" CREATE TABLE IF NOT EXISTS {self.kievit_pallet_table} (
            Min_Value INTEGER,
            Max_Value INTEGER,
            Euro INTEGER,
            Industrial INTEGER
            )"""
        )
        pallet_query.exec_(query)

    def create_connection(self):
        """ Creates database connection. """
        self.connection = QSqlDatabase.addDatabase(
            self.db_driver, self.con_name
        )
        self.connection.setDatabaseName(self.db_name)
        if not self.connection.open():
            self.con_error = True


if __name__ == '__main__':
    pass
