import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window

ApplicationWindow {
    id: win
    width: 880
    height: 520
    visible: true
    title: "Jibo Tools"

    property string host: hostField.text.trim()

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 18
        spacing: 14

        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            Text {
                text: "Connection"
                font.pixelSize: 18
                font.bold: true
            }

            Rectangle {
                width: 10
                height: 10
                radius: 5
                color: conn.connected ? "#2ecc71" : (host.length > 0 ? "#e67e22" : "#bdc3c7")
                Layout.alignment: Qt.AlignVCenter
            }

            Text {
                text: conn.connected ? "SSH reachable" : (host.length > 0 ? "Not reachable" : "No IP")
                color: "#555"
                Layout.alignment: Qt.AlignVCenter
            }

            Item { Layout.fillWidth: true }

            TextField {
                id: hostField
                placeholderText: "Jibo IP (e.g. 192.168.1.50)"
                Layout.preferredWidth: 280
                onTextChanged: conn.host = text
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 16

            Rectangle {
                Layout.preferredWidth: 320
                Layout.fillHeight: true
                radius: 14
                color: "#f6f6f6"
                border.color: "#e4e4e4"

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 18
                    spacing: 10

                    Text {
                        text: "Your Jibo"
                        font.pixelSize: 18
                        font.bold: true
                    }

                    Item { Layout.fillHeight: true }

                    Rectangle {
                        id: jiboCard
                        Layout.alignment: Qt.AlignHCenter
                        width: 240
                        height: 240
                        radius: 18
                        color: "#ffffff"
                        border.color: "#e4e4e4"

                        Image {
                            anchors.centerIn: parent
                            width: 200
                            height: 200
                            source: "../assets/jibo.svg"
                            fillMode: Image.PreserveAspectFit
                        }

                        MouseArea {
                            anchors.fill: parent
                            onClicked: {
                                // Best-effort: open Chrome remote devices page.
                                Qt.openUrlExternally("chrome://inspect/#devices")
                            }
                        }
                    }

                    Item { Layout.fillHeight: true }

                    Text {
                        text: "Click Jibo to open chrome://inspect"
                        color: "#666"
                        Layout.alignment: Qt.AlignHCenter
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: 14
                color: "#f6f6f6"
                border.color: "#e4e4e4"

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 18
                    spacing: 12

                    Text {
                        text: "Actions"
                        font.pixelSize: 18
                        font.bold: true
                    }

                    Text {
                        text: "Installer and updater remain available via CLI.\nUse the buttons below to launch their GUIs."
                        color: "#555"
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }

                    Item { Layout.fillHeight: true }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 12

                        Button {
                            Layout.fillWidth: true
                            text: "Install"
                            enabled: true
                            onClicked: {
                                launcher.launchInstaller()
                            }
                        }

                        Button {
                            Layout.fillWidth: true
                            text: "Check for updates"
                            enabled: true
                            onClicked: {
                                launcher.launchUpdater()
                            }
                        }
                    }
                }
            }
        }
    }
}
