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

        self.con_error = False

    def _create_connection(self):
        """ Creates database connection. """
        self.connection = QSqlDatabase.addDatabase(
            self.db_driver, self.con_name
        )
        self.connection.setDatabaseName(self.db_name)
        if not self.connection.open():
            self.con_error = True