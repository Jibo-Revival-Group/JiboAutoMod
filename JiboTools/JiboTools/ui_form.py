# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'form.ui'
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
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFormLayout,
    QFrame, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QMainWindow, QPushButton, QScrollArea,
    QSizePolicy, QSpacerItem, QStatusBar, QTabWidget,
    QVBoxLayout, QWidget)

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(782, 649)
        MainWindow.setTabShape(QTabWidget.TabShape.Rounded)
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.rootLayout = QVBoxLayout(self.centralwidget)
        self.rootLayout.setSpacing(12)
        self.rootLayout.setObjectName(u"rootLayout")
        self.rootLayout.setContentsMargins(14, 14, 14, 14)
        self.tabWidget = QTabWidget(self.centralwidget)
        self.tabWidget.setObjectName(u"tabWidget")
        self.tabWidget.setDocumentMode(True)
        self.tabWidget.setTabsClosable(False)
        self.tabWidget.setMovable(False)
        self.tabJibo = QWidget()
        self.tabJibo.setObjectName(u"tabJibo")
        self.jiboPageLayout = QHBoxLayout(self.tabJibo)
        self.jiboPageLayout.setSpacing(14)
        self.jiboPageLayout.setObjectName(u"jiboPageLayout")
        self.configFrame = QFrame(self.tabJibo)
        self.configFrame.setObjectName(u"configFrame")
        self.configFrame.setMinimumSize(QSize(420, 0))
        self.configFrame.setFrameShape(QFrame.Shape.StyledPanel)
        self.configFrame.setFrameShadow(QFrame.Shadow.Raised)
        self.configLayout = QVBoxLayout(self.configFrame)
        self.configLayout.setSpacing(10)
        self.configLayout.setObjectName(u"configLayout")
        self.configLayout.setContentsMargins(18, 18, 18, 18)
        self.configTitle = QLabel(self.configFrame)
        self.configTitle.setObjectName(u"configTitle")
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        self.configTitle.setFont(font)

        self.configLayout.addWidget(self.configTitle)

        self.configScroll = QScrollArea(self.configFrame)
        self.configScroll.setObjectName(u"configScroll")
        self.configScroll.setWidgetResizable(True)
        self.configScrollContents = QWidget()
        self.configScrollContents.setObjectName(u"configScrollContents")
        self.configScrollContents.setGeometry(QRect(0, 0, 380, 478))
        self.configScrollLayout = QVBoxLayout(self.configScrollContents)
        self.configScrollLayout.setSpacing(14)
        self.configScrollLayout.setObjectName(u"configScrollLayout")
        self.groupPreview = QGroupBox(self.configScrollContents)
        self.groupPreview.setObjectName(u"groupPreview")
        self.formPreview = QFormLayout(self.groupPreview)
        self.formPreview.setObjectName(u"formPreview")
        self.labelOverride = QLabel(self.groupPreview)
        self.labelOverride.setObjectName(u"labelOverride")

        self.formPreview.setWidget(0, QFormLayout.ItemRole.LabelRole, self.labelOverride)

        self.overrideCheck = QCheckBox(self.groupPreview)
        self.overrideCheck.setObjectName(u"overrideCheck")
        self.overrideCheck.setChecked(True)

        self.formPreview.setWidget(0, QFormLayout.ItemRole.FieldRole, self.overrideCheck)

        self.labelPreviewConnected = QLabel(self.groupPreview)
        self.labelPreviewConnected.setObjectName(u"labelPreviewConnected")

        self.formPreview.setWidget(1, QFormLayout.ItemRole.LabelRole, self.labelPreviewConnected)

        self.previewConnectedCheck = QCheckBox(self.groupPreview)
        self.previewConnectedCheck.setObjectName(u"previewConnectedCheck")

        self.formPreview.setWidget(1, QFormLayout.ItemRole.FieldRole, self.previewConnectedCheck)


        self.configScrollLayout.addWidget(self.groupPreview)

        self.groupHomeAssistant = QGroupBox(self.configScrollContents)
        self.groupHomeAssistant.setObjectName(u"groupHomeAssistant")
        self.formHomeAssistant = QFormLayout(self.groupHomeAssistant)
        self.formHomeAssistant.setObjectName(u"formHomeAssistant")
        self.labelHaEnable = QLabel(self.groupHomeAssistant)
        self.labelHaEnable.setObjectName(u"labelHaEnable")

        self.formHomeAssistant.setWidget(0, QFormLayout.ItemRole.LabelRole, self.labelHaEnable)

        self.haEnableCheck = QCheckBox(self.groupHomeAssistant)
        self.haEnableCheck.setObjectName(u"haEnableCheck")

        self.formHomeAssistant.setWidget(0, QFormLayout.ItemRole.FieldRole, self.haEnableCheck)

        self.labelHaServerIp = QLabel(self.groupHomeAssistant)
        self.labelHaServerIp.setObjectName(u"labelHaServerIp")

        self.formHomeAssistant.setWidget(1, QFormLayout.ItemRole.LabelRole, self.labelHaServerIp)

        self.haServerIpField = QLineEdit(self.groupHomeAssistant)
        self.haServerIpField.setObjectName(u"haServerIpField")

        self.formHomeAssistant.setWidget(1, QFormLayout.ItemRole.FieldRole, self.haServerIpField)


        self.configScrollLayout.addWidget(self.groupHomeAssistant)

        self.groupAiProvider = QGroupBox(self.configScrollContents)
        self.groupAiProvider.setObjectName(u"groupAiProvider")
        self.formAiProvider = QFormLayout(self.groupAiProvider)
        self.formAiProvider.setObjectName(u"formAiProvider")
        self.labelAiEnable = QLabel(self.groupAiProvider)
        self.labelAiEnable.setObjectName(u"labelAiEnable")

        self.formAiProvider.setWidget(0, QFormLayout.ItemRole.LabelRole, self.labelAiEnable)

        self.aiEnableCheck = QCheckBox(self.groupAiProvider)
        self.aiEnableCheck.setObjectName(u"aiEnableCheck")

        self.formAiProvider.setWidget(0, QFormLayout.ItemRole.FieldRole, self.aiEnableCheck)

        self.labelAiProvider = QLabel(self.groupAiProvider)
        self.labelAiProvider.setObjectName(u"labelAiProvider")

        self.formAiProvider.setWidget(1, QFormLayout.ItemRole.LabelRole, self.labelAiProvider)

        self.aiProviderCombo = QComboBox(self.groupAiProvider)
        self.aiProviderCombo.setObjectName(u"aiProviderCombo")

        self.formAiProvider.setWidget(1, QFormLayout.ItemRole.FieldRole, self.aiProviderCombo)

        self.labelAiEndpoint = QLabel(self.groupAiProvider)
        self.labelAiEndpoint.setObjectName(u"labelAiEndpoint")

        self.formAiProvider.setWidget(2, QFormLayout.ItemRole.LabelRole, self.labelAiEndpoint)

        self.aiEndpointField = QLineEdit(self.groupAiProvider)
        self.aiEndpointField.setObjectName(u"aiEndpointField")

        self.formAiProvider.setWidget(2, QFormLayout.ItemRole.FieldRole, self.aiEndpointField)

        self.labelAiKey = QLabel(self.groupAiProvider)
        self.labelAiKey.setObjectName(u"labelAiKey")

        self.formAiProvider.setWidget(3, QFormLayout.ItemRole.LabelRole, self.labelAiKey)

        self.aiKeyField = QLineEdit(self.groupAiProvider)
        self.aiKeyField.setObjectName(u"aiKeyField")
        self.aiKeyField.setEchoMode(QLineEdit.EchoMode.Password)

        self.formAiProvider.setWidget(3, QFormLayout.ItemRole.FieldRole, self.aiKeyField)

        self.labelTokens = QLabel(self.groupAiProvider)
        self.labelTokens.setObjectName(u"labelTokens")

        self.formAiProvider.setWidget(4, QFormLayout.ItemRole.LabelRole, self.labelTokens)

        self.tokensUsedLabel = QLabel(self.groupAiProvider)
        self.tokensUsedLabel.setObjectName(u"tokensUsedLabel")

        self.formAiProvider.setWidget(4, QFormLayout.ItemRole.FieldRole, self.tokensUsedLabel)


        self.configScrollLayout.addWidget(self.groupAiProvider)

        self.configBottomSpacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.configScrollLayout.addItem(self.configBottomSpacer)

        self.configScroll.setWidget(self.configScrollContents)

        self.configLayout.addWidget(self.configScroll)


        self.jiboPageLayout.addWidget(self.configFrame)

        self.jiboCardFrame = QFrame(self.tabJibo)
        self.jiboCardFrame.setObjectName(u"jiboCardFrame")
        self.jiboCardFrame.setFrameShape(QFrame.Shape.StyledPanel)
        self.jiboCardFrame.setFrameShadow(QFrame.Shadow.Raised)
        self.jiboCardLayout = QVBoxLayout(self.jiboCardFrame)
        self.jiboCardLayout.setSpacing(12)
        self.jiboCardLayout.setObjectName(u"jiboCardLayout")
        self.jiboCardLayout.setContentsMargins(18, 18, 18, 18)
        self.IpConfig = QHBoxLayout()
        self.IpConfig.setObjectName(u"IpConfig")
        self.TryToConnect = QPushButton(self.jiboCardFrame)
        self.TryToConnect.setObjectName(u"TryToConnect")
        self.TryToConnect.setCheckable(False)

        self.IpConfig.addWidget(self.TryToConnect, 0, Qt.AlignmentFlag.AlignRight)

        self.JiboIpField = QLineEdit(self.jiboCardFrame)
        self.JiboIpField.setObjectName(u"JiboIpField")

        self.IpConfig.addWidget(self.JiboIpField)


        self.jiboCardLayout.addLayout(self.IpConfig)

        self.jiboHeaderLayout = QHBoxLayout()
        self.jiboHeaderLayout.setObjectName(u"jiboHeaderLayout")
        self.jiboTitle = QLabel(self.jiboCardFrame)
        self.jiboTitle.setObjectName(u"jiboTitle")
        font1 = QFont()
        font1.setPointSize(12)
        font1.setBold(True)
        font1.setUnderline(False)
        self.jiboTitle.setFont(font1)
        self.jiboTitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.jiboHeaderLayout.addWidget(self.jiboTitle)


        self.jiboCardLayout.addLayout(self.jiboHeaderLayout)

        self.jiboTopSpacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.jiboCardLayout.addItem(self.jiboTopSpacer)

        self.jiboImage = QLabel(self.jiboCardFrame)
        self.jiboImage.setObjectName(u"jiboImage")
        self.jiboImage.setMinimumSize(QSize(260, 260))
        self.jiboImage.setMaximumSize(QSize(260, 260))
        self.jiboImage.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.jiboCardLayout.addWidget(self.jiboImage)

        self.jiboBottomSpacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)

        self.jiboCardLayout.addItem(self.jiboBottomSpacer)

        self.RobotSettings = QPushButton(self.jiboCardFrame)
        self.RobotSettings.setObjectName(u"RobotSettings")
        self.RobotSettings.setEnabled(False)
        self.RobotSettings.setFlat(False)

        self.jiboCardLayout.addWidget(self.RobotSettings)

        self.comboBox = QComboBox(self.jiboCardFrame)
        self.comboBox.setObjectName(u"comboBox")
        self.comboBox.setEnabled(False)
        self.comboBox.setEditable(True)

        self.jiboCardLayout.addWidget(self.comboBox)


        self.jiboPageLayout.addWidget(self.jiboCardFrame)

        self.tabWidget.addTab(self.tabJibo, "")
        self.tabUpdate = QWidget()
        self.tabUpdate.setObjectName(u"tabUpdate")
        self.updatePageLayout = QVBoxLayout(self.tabUpdate)
        self.updatePageLayout.setSpacing(12)
        self.updatePageLayout.setObjectName(u"updatePageLayout")
        self.updateFrame = QFrame(self.tabUpdate)
        self.updateFrame.setObjectName(u"updateFrame")
        self.updateFrame.setFrameShape(QFrame.Shape.StyledPanel)
        self.updateFrame.setFrameShadow(QFrame.Shadow.Raised)
        self.updateFrameLayout = QVBoxLayout(self.updateFrame)
        self.updateFrameLayout.setSpacing(12)
        self.updateFrameLayout.setObjectName(u"updateFrameLayout")
        self.updateFrameLayout.setContentsMargins(18, 18, 18, 18)
        self.updateInfoText = QLabel(self.updateFrame)
        self.updateInfoText.setObjectName(u"updateInfoText")
        self.updateInfoText.setWordWrap(True)

        self.updateFrameLayout.addWidget(self.updateInfoText)

        self.updateSpacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.updateFrameLayout.addItem(self.updateSpacer)

        self.updateButtonsLayout = QHBoxLayout()
        self.updateButtonsLayout.setSpacing(12)
        self.updateButtonsLayout.setObjectName(u"updateButtonsLayout")
        self.installButton = QPushButton(self.updateFrame)
        self.installButton.setObjectName(u"installButton")

        self.updateButtonsLayout.addWidget(self.installButton)

        self.checkUpdatesButton = QPushButton(self.updateFrame)
        self.checkUpdatesButton.setObjectName(u"checkUpdatesButton")

        self.updateButtonsLayout.addWidget(self.checkUpdatesButton)


        self.updateFrameLayout.addLayout(self.updateButtonsLayout)


        self.updatePageLayout.addWidget(self.updateFrame)

        self.tabWidget.addTab(self.tabUpdate, "")
        self.tabSkills = QWidget()
        self.tabSkills.setObjectName(u"tabSkills")
        self.skillsLayout = QVBoxLayout(self.tabSkills)
        self.skillsLayout.setObjectName(u"skillsLayout")
        self.skillsComingSoon = QLabel(self.tabSkills)
        self.skillsComingSoon.setObjectName(u"skillsComingSoon")

        self.skillsLayout.addWidget(self.skillsComingSoon)

        self.tabWidget.addTab(self.tabSkills, "")
        self.tabSsh = QWidget()
        self.tabSsh.setObjectName(u"tabSsh")
        self.sshLayout = QVBoxLayout(self.tabSsh)
        self.sshLayout.setObjectName(u"sshLayout")
        self.sshComingSoon = QLabel(self.tabSsh)
        self.sshComingSoon.setObjectName(u"sshComingSoon")

        self.sshLayout.addWidget(self.sshComingSoon)

        self.tabWidget.addTab(self.tabSsh, "")
        self.tabFtp = QWidget()
        self.tabFtp.setObjectName(u"tabFtp")
        self.ftpLayout = QVBoxLayout(self.tabFtp)
        self.ftpLayout.setObjectName(u"ftpLayout")
        self.ftpComingSoon = QLabel(self.tabFtp)
        self.ftpComingSoon.setObjectName(u"ftpComingSoon")

        self.ftpLayout.addWidget(self.ftpComingSoon)

        self.tabWidget.addTab(self.tabFtp, "")
        self.tabStatus = QWidget()
        self.tabStatus.setObjectName(u"tabStatus")
        self.statusLayout = QVBoxLayout(self.tabStatus)
        self.statusLayout.setSpacing(10)
        self.statusLayout.setObjectName(u"statusLayout")
        self.statusRow = QHBoxLayout()
        self.statusRow.setSpacing(10)
        self.statusRow.setObjectName(u"statusRow")
        self.statusDot = QLabel(self.tabStatus)
        self.statusDot.setObjectName(u"statusDot")
        self.statusDot.setMinimumSize(QSize(10, 10))
        self.statusDot.setMaximumSize(QSize(10, 10))

        self.statusRow.addWidget(self.statusDot)

        self.statusText = QLabel(self.tabStatus)
        self.statusText.setObjectName(u"statusText")
        self.statusText.setWordWrap(True)

        self.statusRow.addWidget(self.statusText)


        self.statusLayout.addLayout(self.statusRow)

        self.tabWidget.addTab(self.tabStatus, "")
        self.tabRobotOs = QWidget()
        self.tabRobotOs.setObjectName(u"tabRobotOs")
        self.robotOsLayout = QVBoxLayout(self.tabRobotOs)
        self.robotOsLayout.setObjectName(u"robotOsLayout")
        self.robotOsComingSoon = QLabel(self.tabRobotOs)
        self.robotOsComingSoon.setObjectName(u"robotOsComingSoon")

        self.robotOsLayout.addWidget(self.robotOsComingSoon)

        self.tabWidget.addTab(self.tabRobotOs, "")

        self.rootLayout.addWidget(self.tabWidget)

        MainWindow.setCentralWidget(self.centralwidget)
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName(u"statusbar")
        self.statusbar.setSizeGripEnabled(False)
        MainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(MainWindow)

        self.tabWidget.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"Jibo Tools", None))
        self.configTitle.setText(QCoreApplication.translate("MainWindow", u"Config", None))
        self.groupPreview.setTitle(QCoreApplication.translate("MainWindow", u"Preview", None))
        self.labelOverride.setText(QCoreApplication.translate("MainWindow", u"Override", None))
        self.overrideCheck.setText("")
        self.labelPreviewConnected.setText(QCoreApplication.translate("MainWindow", u"Connected", None))
        self.previewConnectedCheck.setText("")
        self.groupHomeAssistant.setTitle(QCoreApplication.translate("MainWindow", u"Home Assistant", None))
        self.labelHaEnable.setText(QCoreApplication.translate("MainWindow", u"Enabled", None))
        self.haEnableCheck.setText("")
        self.labelHaServerIp.setText(QCoreApplication.translate("MainWindow", u"Server IP", None))
        self.haServerIpField.setPlaceholderText(QCoreApplication.translate("MainWindow", u"Home Assistant host", None))
        self.groupAiProvider.setTitle(QCoreApplication.translate("MainWindow", u"AI Provider", None))
        self.labelAiEnable.setText(QCoreApplication.translate("MainWindow", u"Enabled", None))
        self.aiEnableCheck.setText("")
        self.labelAiProvider.setText(QCoreApplication.translate("MainWindow", u"Provider", None))
        self.labelAiEndpoint.setText(QCoreApplication.translate("MainWindow", u"API endpoint", None))
        self.aiEndpointField.setPlaceholderText(QCoreApplication.translate("MainWindow", u"http://...", None))
        self.labelAiKey.setText(QCoreApplication.translate("MainWindow", u"API key", None))
        self.labelTokens.setText(QCoreApplication.translate("MainWindow", u"Tokens used", None))
        self.tokensUsedLabel.setText(QCoreApplication.translate("MainWindow", u"-1", None))
        self.TryToConnect.setText(QCoreApplication.translate("MainWindow", u"Connect", None))
        self.JiboIpField.setInputMask("")
        self.JiboIpField.setText("")
        self.JiboIpField.setPlaceholderText(QCoreApplication.translate("MainWindow", u"e.g 192.168.1.54", None))
        self.jiboTitle.setText(QCoreApplication.translate("MainWindow", u"Connect Your Jibo", None))
        self.jiboImage.setText("")
        self.RobotSettings.setText(QCoreApplication.translate("MainWindow", u"Robot Settings", None))
        self.comboBox.setCurrentText(QCoreApplication.translate("MainWindow", u"Reboot", None))
        self.comboBox.setPlaceholderText(QCoreApplication.translate("MainWindow", u"Reboot", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tabJibo), QCoreApplication.translate("MainWindow", u"Jibo", None))
        self.updateInfoText.setText(QCoreApplication.translate("MainWindow", u"Installer and updater remain available via CLI. Use the buttons below to launch their GUIs.", None))
        self.installButton.setText(QCoreApplication.translate("MainWindow", u"Install", None))
        self.checkUpdatesButton.setText(QCoreApplication.translate("MainWindow", u"Check for updates", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tabUpdate), QCoreApplication.translate("MainWindow", u"Update", None))
        self.skillsComingSoon.setText(QCoreApplication.translate("MainWindow", u"Coming soon.", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tabSkills), QCoreApplication.translate("MainWindow", u"Skills", None))
        self.sshComingSoon.setText(QCoreApplication.translate("MainWindow", u"Coming soon.", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tabSsh), QCoreApplication.translate("MainWindow", u"SSH", None))
        self.ftpComingSoon.setText(QCoreApplication.translate("MainWindow", u"Coming soon.", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tabFtp), QCoreApplication.translate("MainWindow", u"FTP", None))
        self.statusDot.setText("")
        self.statusText.setText(QCoreApplication.translate("MainWindow", u"No Jibo IP configured", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tabStatus), QCoreApplication.translate("MainWindow", u"Status", None))
        self.robotOsComingSoon.setText(QCoreApplication.translate("MainWindow", u"Coming soon.", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tabRobotOs), QCoreApplication.translate("MainWindow", u"Robot OS", None))
    # retranslateUi

