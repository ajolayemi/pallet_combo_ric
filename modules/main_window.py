#!/usr/bin/env python

from PyQt5.QtWidgets import (QApplication, QLabel,
                             QWidget, QFormLayout,
                             QMainWindow, QPushButton,
                             QComboBox, QLineEdit)

from PyQt5.QtGui import QFont

# Self defined modules
from helper_modules import helper_functions
import settings
MSG_FONT = QFont('Italics', 13)

APP_INFO_JSON_CONTENTS = helper_functions.json_file_loader(
    file_name=settings.INFORMATION_JSON
)


class MainPage(QMainWindow):
    """" User GUI. """


if __name__ == '__main__':
    pass