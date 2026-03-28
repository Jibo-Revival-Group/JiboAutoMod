# -*- coding: utf-8 -*-


from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFormLayout,
    QFrame, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QMainWindow, QPlainTextEdit, QPushButton,
    QScrollArea, QSizePolicy, QSpacerItem, QSpinBox,
    QStatusBar, QTabWidget, QVBoxLayout, QWidget)

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

        self.groupToolSettings = QGroupBox(self.configScrollContents)
        self.groupToolSettings.setObjectName(u"groupToolSettings")
        self.formToolSettings = QFormLayout(self.groupToolSettings)
        self.formToolSettings.setObjectName(u"formToolSettings")
        self.labelEnableLogging = QLabel(self.groupToolSettings)
        self.labelEnableLogging.setObjectName(u"labelEnableLogging")

        self.formToolSettings.setWidget(0, QFormLayout.ItemRole.LabelRole, self.labelEnableLogging)

        self.enableLoggingCheck = QCheckBox(self.groupToolSettings)
        self.enableLoggingCheck.setObjectName(u"enableLoggingCheck")
        self.enableLoggingCheck.setChecked(False)

        self.formToolSettings.setWidget(0, QFormLayout.ItemRole.FieldRole, self.enableLoggingCheck)


        self.configScrollLayout.addWidget(self.groupToolSettings)

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

        self.formAiProvider.setWidget(3, QFormLayout.ItemRole.FieldRole, self.aiKeyField)

        self.labelAiBridgeRecordSeconds = QLabel(self.groupAiProvider)
        self.labelAiBridgeRecordSeconds.setObjectName(u"labelAiBridgeRecordSeconds")

        self.formAiProvider.setWidget(4, QFormLayout.ItemRole.LabelRole, self.labelAiBridgeRecordSeconds)

        self.aiBridgeRecordSecondsSpin = QSpinBox(self.groupAiProvider)
        self.aiBridgeRecordSecondsSpin.setObjectName(u"aiBridgeRecordSecondsSpin")
        self.aiBridgeRecordSecondsSpin.setMinimum(1)
        self.aiBridgeRecordSecondsSpin.setMaximum(60)
        self.aiBridgeRecordSecondsSpin.setValue(5)

        self.formAiProvider.setWidget(4, QFormLayout.ItemRole.FieldRole, self.aiBridgeRecordSecondsSpin)

        self.labelAiBridgeUseAsr = QLabel(self.groupAiProvider)
        self.labelAiBridgeUseAsr.setObjectName(u"labelAiBridgeUseAsr")

        self.formAiProvider.setWidget(5, QFormLayout.ItemRole.LabelRole, self.labelAiBridgeUseAsr)

        self.aiBridgeUseAsrServiceSttCheck = QCheckBox(self.groupAiProvider)
        self.aiBridgeUseAsrServiceSttCheck.setObjectName(u"aiBridgeUseAsrServiceSttCheck")
        self.aiBridgeUseAsrServiceSttCheck.setChecked(True)

        self.formAiProvider.setWidget(5, QFormLayout.ItemRole.FieldRole, self.aiBridgeUseAsrServiceSttCheck)

        self.labelAiBridgeAsrPort = QLabel(self.groupAiProvider)
        self.labelAiBridgeAsrPort.setObjectName(u"labelAiBridgeAsrPort")

        self.formAiProvider.setWidget(6, QFormLayout.ItemRole.LabelRole, self.labelAiBridgeAsrPort)

        self.aiBridgeAsrPortSpin = QSpinBox(self.groupAiProvider)
        self.aiBridgeAsrPortSpin.setObjectName(u"aiBridgeAsrPortSpin")
        self.aiBridgeAsrPortSpin.setMinimum(1)
        self.aiBridgeAsrPortSpin.setMaximum(65535)
        self.aiBridgeAsrPortSpin.setValue(8088)

        self.formAiProvider.setWidget(6, QFormLayout.ItemRole.FieldRole, self.aiBridgeAsrPortSpin)

        self.labelAiBridgeAsrAudioSource = QLabel(self.groupAiProvider)
        self.labelAiBridgeAsrAudioSource.setObjectName(u"labelAiBridgeAsrAudioSource")

        self.formAiProvider.setWidget(7, QFormLayout.ItemRole.LabelRole, self.labelAiBridgeAsrAudioSource)

        self.aiBridgeAsrAudioSourceField = QLineEdit(self.groupAiProvider)
        self.aiBridgeAsrAudioSourceField.setObjectName(u"aiBridgeAsrAudioSourceField")

        self.formAiProvider.setWidget(7, QFormLayout.ItemRole.FieldRole, self.aiBridgeAsrAudioSourceField)

        self.labelAiBridgeAsrTimeout = QLabel(self.groupAiProvider)
        self.labelAiBridgeAsrTimeout.setObjectName(u"labelAiBridgeAsrTimeout")

        self.formAiProvider.setWidget(8, QFormLayout.ItemRole.LabelRole, self.labelAiBridgeAsrTimeout)

        self.aiBridgeAsrTimeoutSpin = QSpinBox(self.groupAiProvider)
        self.aiBridgeAsrTimeoutSpin.setObjectName(u"aiBridgeAsrTimeoutSpin")
        self.aiBridgeAsrTimeoutSpin.setMinimum(100)
        self.aiBridgeAsrTimeoutSpin.setMaximum(120000)
        self.aiBridgeAsrTimeoutSpin.setSingleStep(100)
        self.aiBridgeAsrTimeoutSpin.setValue(15000)

        self.formAiProvider.setWidget(8, QFormLayout.ItemRole.FieldRole, self.aiBridgeAsrTimeoutSpin)

        self.labelAiBridgeAsrAutoStart = QLabel(self.groupAiProvider)
        self.labelAiBridgeAsrAutoStart.setObjectName(u"labelAiBridgeAsrAutoStart")

        self.formAiProvider.setWidget(9, QFormLayout.ItemRole.LabelRole, self.labelAiBridgeAsrAutoStart)

        self.aiBridgeAsrAutoStartCheck = QCheckBox(self.groupAiProvider)
        self.aiBridgeAsrAutoStartCheck.setObjectName(u"aiBridgeAsrAutoStartCheck")
        self.aiBridgeAsrAutoStartCheck.setChecked(True)

        self.formAiProvider.setWidget(9, QFormLayout.ItemRole.FieldRole, self.aiBridgeAsrAutoStartCheck)

        self.labelAiBridgeFollowupEnabled = QLabel(self.groupAiProvider)
        self.labelAiBridgeFollowupEnabled.setObjectName(u"labelAiBridgeFollowupEnabled")

        self.formAiProvider.setWidget(10, QFormLayout.ItemRole.LabelRole, self.labelAiBridgeFollowupEnabled)

        self.aiBridgeFollowupEnabledCheck = QCheckBox(self.groupAiProvider)
        self.aiBridgeFollowupEnabledCheck.setObjectName(u"aiBridgeFollowupEnabledCheck")
        self.aiBridgeFollowupEnabledCheck.setChecked(True)

        self.formAiProvider.setWidget(10, QFormLayout.ItemRole.FieldRole, self.aiBridgeFollowupEnabledCheck)

        self.labelAiBridgeFollowupDelay = QLabel(self.groupAiProvider)
        self.labelAiBridgeFollowupDelay.setObjectName(u"labelAiBridgeFollowupDelay")

        self.formAiProvider.setWidget(11, QFormLayout.ItemRole.LabelRole, self.labelAiBridgeFollowupDelay)

        self.aiBridgeFollowupDelaySpin = QSpinBox(self.groupAiProvider)
        self.aiBridgeFollowupDelaySpin.setObjectName(u"aiBridgeFollowupDelaySpin")
        self.aiBridgeFollowupDelaySpin.setMinimum(0)
        self.aiBridgeFollowupDelaySpin.setMaximum(60000)
        self.aiBridgeFollowupDelaySpin.setSingleStep(50)
        self.aiBridgeFollowupDelaySpin.setValue(250)

        self.formAiProvider.setWidget(11, QFormLayout.ItemRole.FieldRole, self.aiBridgeFollowupDelaySpin)

        self.labelAiBridge = QLabel(self.groupAiProvider)
        self.labelAiBridge.setObjectName(u"labelAiBridge")

        self.formAiProvider.setWidget(12, QFormLayout.ItemRole.LabelRole, self.labelAiBridge)

        self.editAiBridgeConfigButton = QPushButton(self.groupAiProvider)
        self.editAiBridgeConfigButton.setObjectName(u"editAiBridgeConfigButton")

        self.formAiProvider.setWidget(12, QFormLayout.ItemRole.FieldRole, self.editAiBridgeConfigButton)


        self.configScrollLayout.addWidget(self.groupAiProvider)

        self.groupConfigFiles = QGroupBox(self.configScrollContents)
        self.groupConfigFiles.setObjectName(u"groupConfigFiles")
        self.configFilesLayout = QVBoxLayout(self.groupConfigFiles)
        self.configFilesLayout.setSpacing(8)
        self.configFilesLayout.setObjectName(u"configFilesLayout")
        self.configFilesTopRow = QHBoxLayout()
        self.configFilesTopRow.setSpacing(8)
        self.configFilesTopRow.setObjectName(u"configFilesTopRow")
        self.configFileCombo = QComboBox(self.groupConfigFiles)
        self.configFileCombo.setObjectName(u"configFileCombo")

        self.configFilesTopRow.addWidget(self.configFileCombo)

        self.configReadButton = QPushButton(self.groupConfigFiles)
        self.configReadButton.setObjectName(u"configReadButton")

        self.configFilesTopRow.addWidget(self.configReadButton)

        self.configWriteButton = QPushButton(self.groupConfigFiles)
        self.configWriteButton.setObjectName(u"configWriteButton")
        self.configWriteButton.setEnabled(False)

        self.configFilesTopRow.addWidget(self.configWriteButton)


        self.configFilesLayout.addLayout(self.configFilesTopRow)

        self.configFileStatusLabel = QLabel(self.groupConfigFiles)
        self.configFileStatusLabel.setObjectName(u"configFileStatusLabel")
        self.configFileStatusLabel.setWordWrap(True)

        self.configFilesLayout.addWidget(self.configFileStatusLabel)

        self.configEditor = QPlainTextEdit(self.groupConfigFiles)
        self.configEditor.setObjectName(u"configEditor")

        self.configFilesLayout.addWidget(self.configEditor)

        self.configLogLabel = QLabel(self.groupConfigFiles)
        self.configLogLabel.setObjectName(u"configLogLabel")

        self.configFilesLayout.addWidget(self.configLogLabel)

        self.configActivityLog = QPlainTextEdit(self.groupConfigFiles)
        self.configActivityLog.setObjectName(u"configActivityLog")
        self.configActivityLog.setReadOnly(True)

        self.configFilesLayout.addWidget(self.configActivityLog)


        self.configScrollLayout.addWidget(self.groupConfigFiles)

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

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"Jibo Tools", None))
        self.configTitle.setText(QCoreApplication.translate("MainWindow", u"Config", None))
        self.groupPreview.setTitle(QCoreApplication.translate("MainWindow", u"Preview", None))
        self.labelOverride.setText(QCoreApplication.translate("MainWindow", u"Override", None))
        self.overrideCheck.setText("")
        self.labelPreviewConnected.setText(QCoreApplication.translate("MainWindow", u"Connected", None))
        self.previewConnectedCheck.setText("")
        self.groupToolSettings.setTitle(QCoreApplication.translate("MainWindow", u"Tool Settings", None))
        self.labelEnableLogging.setText(QCoreApplication.translate("MainWindow", u"Enable logging", None))
        self.enableLoggingCheck.setText("")
        self.groupHomeAssistant.setTitle(QCoreApplication.translate("MainWindow", u"Home Assistant", None))
        self.labelHaEnable.setText(QCoreApplication.translate("MainWindow", u"Enabled", None))
        self.haEnableCheck.setText("")
        self.labelHaServerIp.setText(QCoreApplication.translate("MainWindow", u"Server IP", None))
        self.haServerIpField.setPlaceholderText(QCoreApplication.translate("MainWindow", u"Home Assistant host", None))
        self.groupAiProvider.setTitle(QCoreApplication.translate("MainWindow", u"AI Bridge", None))
        self.labelAiEnable.setText(QCoreApplication.translate("MainWindow", u"Enabled", None))
        self.aiEnableCheck.setText("")
        self.labelAiProvider.setText(QCoreApplication.translate("MainWindow", u"Mode", None))
        self.labelAiEndpoint.setText(QCoreApplication.translate("MainWindow", u"Server base URL", None))
        self.aiEndpointField.setPlaceholderText(QCoreApplication.translate("MainWindow", u"http://...", None))
        self.labelAiKey.setText(QCoreApplication.translate("MainWindow", u"ASR host", None))
        self.aiKeyField.setPlaceholderText(QCoreApplication.translate("MainWindow", u"127.0.0.1", None))
        self.labelAiBridgeRecordSeconds.setText(QCoreApplication.translate("MainWindow", u"Record seconds", None))
        self.labelAiBridgeUseAsr.setText(QCoreApplication.translate("MainWindow", u"Use ASR service STT", None))
        self.aiBridgeUseAsrServiceSttCheck.setText("")
        self.labelAiBridgeAsrPort.setText(QCoreApplication.translate("MainWindow", u"ASR port", None))
        self.labelAiBridgeAsrAudioSource.setText(QCoreApplication.translate("MainWindow", u"ASR audio source", None))
        self.aiBridgeAsrAudioSourceField.setPlaceholderText(QCoreApplication.translate("MainWindow", u"alsa1", None))
        self.labelAiBridgeAsrTimeout.setText(QCoreApplication.translate("MainWindow", u"ASR timeout (ms)", None))
        self.labelAiBridgeAsrAutoStart.setText(QCoreApplication.translate("MainWindow", u"ASR auto start", None))
        self.aiBridgeAsrAutoStartCheck.setText("")
        self.labelAiBridgeFollowupEnabled.setText(QCoreApplication.translate("MainWindow", u"Followup enabled", None))
        self.aiBridgeFollowupEnabledCheck.setText("")
        self.labelAiBridgeFollowupDelay.setText(QCoreApplication.translate("MainWindow", u"Followup delay (ms)", None))
        self.labelAiBridge.setText(QCoreApplication.translate("MainWindow", u"Advanced", None))
        self.editAiBridgeConfigButton.setText(QCoreApplication.translate("MainWindow", u"Edit AI Bridge Config", None))
        self.groupConfigFiles.setTitle(QCoreApplication.translate("MainWindow", u"Config Files", None))
        self.configReadButton.setText(QCoreApplication.translate("MainWindow", u"Read", None))
        self.configWriteButton.setText(QCoreApplication.translate("MainWindow", u"Write", None))
        self.configFileStatusLabel.setText(QCoreApplication.translate("MainWindow", u"Select a config to view/edit", None))
        self.configLogLabel.setText(QCoreApplication.translate("MainWindow", u"Activity log", None))
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

