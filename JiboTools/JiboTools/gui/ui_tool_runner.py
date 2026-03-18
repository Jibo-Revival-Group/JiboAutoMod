# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'tool_runner.ui'
##
## Created by: Qt User Interface Compiler version 6.10.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QPlainTextEdit, QPushButton, QSizePolicy,
    QSpacerItem, QStatusBar, QVBoxLayout, QWidget)

class Ui_ToolRunnerWindow(object):
    def setupUi(self, ToolRunnerWindow):
        if not ToolRunnerWindow.objectName():
            ToolRunnerWindow.setObjectName(u"ToolRunnerWindow")
        ToolRunnerWindow.resize(900, 560)
        self.centralwidget = QWidget(ToolRunnerWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.rootLayout = QVBoxLayout(self.centralwidget)
        self.rootLayout.setSpacing(12)
        self.rootLayout.setObjectName(u"rootLayout")
        self.rootLayout.setContentsMargins(16, 16, 16, 16)
        self.headerLayout = QHBoxLayout()
        self.headerLayout.setSpacing(10)
        self.headerLayout.setObjectName(u"headerLayout")
        self.titleLabel = QLabel(self.centralwidget)
        self.titleLabel.setObjectName(u"titleLabel")
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        self.titleLabel.setFont(font)

        self.headerLayout.addWidget(self.titleLabel)

        self.headerSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.headerLayout.addItem(self.headerSpacer)

        self.startStopButton = QPushButton(self.centralwidget)
        self.startStopButton.setObjectName(u"startStopButton")

        self.headerLayout.addWidget(self.startStopButton)

        self.openTerminalButton = QPushButton(self.centralwidget)
        self.openTerminalButton.setObjectName(u"openTerminalButton")

        self.headerLayout.addWidget(self.openTerminalButton)


        self.rootLayout.addLayout(self.headerLayout)

        self.argsLayout = QHBoxLayout()
        self.argsLayout.setSpacing(10)
        self.argsLayout.setObjectName(u"argsLayout")
        self.hostField = QLineEdit(self.centralwidget)
        self.hostField.setObjectName(u"hostField")

        self.argsLayout.addWidget(self.hostField)

        self.extraArgsField = QLineEdit(self.centralwidget)
        self.extraArgsField.setObjectName(u"extraArgsField")

        self.argsLayout.addWidget(self.extraArgsField)


        self.rootLayout.addLayout(self.argsLayout)

        self.logEdit = QPlainTextEdit(self.centralwidget)
        self.logEdit.setObjectName(u"logEdit")
        self.logEdit.setReadOnly(True)

        self.rootLayout.addWidget(self.logEdit)

        self.footerLayout = QHBoxLayout()
        self.footerLayout.setSpacing(10)
        self.footerLayout.setObjectName(u"footerLayout")
        self.statusLabel = QLabel(self.centralwidget)
        self.statusLabel.setObjectName(u"statusLabel")

        self.footerLayout.addWidget(self.statusLabel)

        self.footerSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.footerLayout.addItem(self.footerSpacer)

        self.clearLogButton = QPushButton(self.centralwidget)
        self.clearLogButton.setObjectName(u"clearLogButton")

        self.footerLayout.addWidget(self.clearLogButton)


        self.rootLayout.addLayout(self.footerLayout)

        ToolRunnerWindow.setCentralWidget(self.centralwidget)
        self.statusbar = QStatusBar(ToolRunnerWindow)
        self.statusbar.setObjectName(u"statusbar")
        ToolRunnerWindow.setStatusBar(self.statusbar)

        self.retranslateUi(ToolRunnerWindow)

        QMetaObject.connectSlotsByName(ToolRunnerWindow)
    # setupUi

    def retranslateUi(self, ToolRunnerWindow):
        ToolRunnerWindow.setWindowTitle(QCoreApplication.translate("ToolRunnerWindow", u"Tool", None))
        self.titleLabel.setText(QCoreApplication.translate("ToolRunnerWindow", u"Tool", None))
        self.startStopButton.setText(QCoreApplication.translate("ToolRunnerWindow", u"Start", None))
        self.openTerminalButton.setText(QCoreApplication.translate("ToolRunnerWindow", u"Open in terminal", None))
        self.hostField.setPlaceholderText(QCoreApplication.translate("ToolRunnerWindow", u"Jibo IP (required for updater)", None))
        self.extraArgsField.setPlaceholderText(QCoreApplication.translate("ToolRunnerWindow", u"Extra arguments (optional)", None))
        self.statusLabel.setText(QCoreApplication.translate("ToolRunnerWindow", u"Idle", None))
        self.clearLogButton.setText(QCoreApplication.translate("ToolRunnerWindow", u"Clear log", None))
    # retranslateUi

