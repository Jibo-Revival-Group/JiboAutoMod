# -*- coding: utf-8 -*-


from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QCheckBox, QHBoxLayout, QLabel,
    QLineEdit, QMainWindow, QPlainTextEdit, QProgressBar,
    QPushButton, QSizePolicy, QSpacerItem, QStatusBar,
    QVBoxLayout, QWidget)

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

        self.descriptionLabel = QLabel(self.centralwidget)
        self.descriptionLabel.setObjectName(u"descriptionLabel")
        self.descriptionLabel.setWordWrap(True)

        self.rootLayout.addWidget(self.descriptionLabel)

        self.dumpLayout = QHBoxLayout()
        self.dumpLayout.setSpacing(10)
        self.dumpLayout.setObjectName(u"dumpLayout")
        self.useExistingDumpCheck = QCheckBox(self.centralwidget)
        self.useExistingDumpCheck.setObjectName(u"useExistingDumpCheck")

        self.dumpLayout.addWidget(self.useExistingDumpCheck)

        self.dumpPathField = QLineEdit(self.centralwidget)
        self.dumpPathField.setObjectName(u"dumpPathField")

        self.dumpLayout.addWidget(self.dumpPathField)

        self.browseDumpButton = QPushButton(self.centralwidget)
        self.browseDumpButton.setObjectName(u"browseDumpButton")

        self.dumpLayout.addWidget(self.browseDumpButton)


        self.rootLayout.addLayout(self.dumpLayout)

        self.progressBar = QProgressBar(self.centralwidget)
        self.progressBar.setObjectName(u"progressBar")
        self.progressBar.setValue(0)

        self.rootLayout.addWidget(self.progressBar)

        self.currentStepLabel = QLabel(self.centralwidget)
        self.currentStepLabel.setObjectName(u"currentStepLabel")
        self.currentStepLabel.setWordWrap(True)

        self.rootLayout.addWidget(self.currentStepLabel)

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

    def retranslateUi(self, ToolRunnerWindow):
        ToolRunnerWindow.setWindowTitle(QCoreApplication.translate("ToolRunnerWindow", u"Tool", None))
        self.titleLabel.setText(QCoreApplication.translate("ToolRunnerWindow", u"Tool", None))
        self.startStopButton.setText(QCoreApplication.translate("ToolRunnerWindow", u"Start", None))
        self.openTerminalButton.setText(QCoreApplication.translate("ToolRunnerWindow", u"Open in terminal", None))
        self.hostField.setPlaceholderText(QCoreApplication.translate("ToolRunnerWindow", u"Jibo IP (required for updater)", None))
        self.extraArgsField.setPlaceholderText(QCoreApplication.translate("ToolRunnerWindow", u"Extra arguments (optional)", None))
        self.descriptionLabel.setText(QCoreApplication.translate("ToolRunnerWindow", u"Tool description", None))
        self.useExistingDumpCheck.setText(QCoreApplication.translate("ToolRunnerWindow", u"I already have a full eMMC dump (.bin)", None))
        self.dumpPathField.setPlaceholderText(QCoreApplication.translate("ToolRunnerWindow", u"Dump path (passed as --dump-path)", None))
        self.browseDumpButton.setText(QCoreApplication.translate("ToolRunnerWindow", u"Browse\u2026", None))
        self.currentStepLabel.setText(QCoreApplication.translate("ToolRunnerWindow", u"Idle", None))
        self.statusLabel.setText(QCoreApplication.translate("ToolRunnerWindow", u"Idle", None))
        self.clearLogButton.setText(QCoreApplication.translate("ToolRunnerWindow", u"Clear log", None))

