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
    pass
