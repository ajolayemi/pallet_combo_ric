#!/usr/bin/env python

from PyQt5.QtWidgets import (QApplication, QLabel,
                             QWidget, QFormLayout,
                             QMainWindow, QPushButton,
                             QComboBox, QLineEdit)

from PyQt5.QtGui import QFont


MSG_FONT = QFont('Italics', 13)


class MainPage(QMainWindow):
    """" User GUI. """
