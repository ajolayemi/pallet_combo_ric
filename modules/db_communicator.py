#!/usr/bin/env python

""" Communicates with the database that stores some necessary
information needed in this project. """


from PyQt5.QtSql import QSqlQuery, QSqlDatabase

# self defined modules
import settings
from helper_modules import helper_functions


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
        self.client_table_name = settings.CLIENT_INFO_TABLE

        self.con_error = False
        self.connection = None

    def get_pallet_info(self, total_boxes: int):
        """ Returns the suggested pallet combination necessary for the
        total_boxes entered. """
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
            if all((not euro_pallet, not industrial_pallet, not alternative_euro)):
                return {}

            return {
                'euro': euro_pallet,
                'industrial': industrial_pallet,
                'alternative_euro': alternative_euro
            }
        else:
            return {}

    def write_to_client_table(self, info_to_write: list):
        """ Writes the necessary information to client table in the database
        used in this algorithm. """
        if len(info_to_write) == settings.MAX_CLIENT_INFO:
            self.create_client_info_table()
            if not self.connection:
                self.create_client_info_table()
            client_writer_query = QSqlQuery(self.connection)
            query = (
                f""" INSERT INTO {self.client_table_name} (
                Client_Name,
                Client_Logistic
                )
                VALUES (
                ?, ?)
                """
            )
            if client_writer_query.prepare(query):
                client_writer_query.addBindValue(info_to_write[0])
                client_writer_query.addBindValue(info_to_write[1])

                client_writer_query.exec_()

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
                Alternative_Euro)
                VALUES (?, ?, ?, ?, ?)"""
            )
            if pallet_writer_query.prepare(query):
                pallet_writer_query.addBindValue(int(info_to_write[0]))
                pallet_writer_query.addBindValue(int(info_to_write[1]))
                pallet_writer_query.addBindValue(int(info_to_write[2]))
                pallet_writer_query.addBindValue(int(info_to_write[3]))
                pallet_writer_query.addBindValue(int(info_to_write[4]))

                pallet_writer_query.exec_()

    def create_client_info_table(self):
        """ Creates the table where information related to clients is
        stored. """

        if not self.connection:
            self.create_connection()

        client_query = QSqlQuery(self.connection)

        query = (
            f""" CREATE TABLE IF NOT EXISTS {self.client_table_name} (
            Client_Name VARCHAR,
            Client_Logistic VARCHAR
            )"""
        )
        client_query.exec_(query)

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
            Alternative_Euro INTEGER 
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
    reader = DatabaseCommunicator(read_from_db=True)
    print(reader.get_pallet_info(10))
