import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: win
    width: 900
    height: 560
    visible: true
    title: (typeof toolTitle === "string" ? toolTitle : "Tool")

    property string script: (typeof toolScript === "string" ? toolScript : "")
    property bool isUpdater: script.indexOf("jibo_updater.py") >= 0

    function buildArgs() {
        var args = []
        args.push(script)

        if (isUpdater) {
            var h = hostField.text.trim()
            if (h.length > 0) {
                args.push("--ip")
                args.push(h)
            }
        }

        var extra = extraArgs.text.trim()
        if (extra.length > 0) {
            // naive split (keeps GUI minimal)
            var parts = extra.split(/\s+/)
            for (var i=0; i<parts.length; i++) {
                if (parts[i].length > 0) args.push(parts[i])
            }
        }

        return args
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12

        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            Text {
                text: title
                font.pixelSize: 18
                font.bold: true
            }

            Item { Layout.fillWidth: true }

            Button {
                text: runner.running ? "Stop" : "Start"
                onClicked: {
                    if (runner.running) {
                        runner.stop()
                    } else {
                        runner.start(pyExec, buildArgs())
                    }
                }
            }

            Button {
                text: "Open in terminal"
                enabled: !runner.running
                onClicked: {
                    terminal.openTerminal(pyExec, buildArgs())
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            TextField {
                id: hostField
                visible: isUpdater
                placeholderText: "Jibo IP (required for updater)"
                Layout.preferredWidth: 260
            }

            TextField {
                id: extraArgs
                placeholderText: "Extra arguments (optional)"
                Layout.fillWidth: true
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: 12
            color: "#0f0f0f"

            ScrollView {
                anchors.fill: parent
                anchors.margins: 10
                clip: true

                TextArea {
                    id: log
                    readOnly: true
                    wrapMode: TextArea.Wrap
                    color: "#e8e8e8"
                    font.family: "monospace"
                    background: null
                    text: ""
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            Text {
                text: runner.running ? "Running..." : (runner.exitCode >= 0 ? ("Exit: " + runner.exitCode) : "Idle")
                color: "#666"
            }

            Item { Layout.fillWidth: true }

            Button {
                text: "Clear log"
                onClicked: log.text = ""
            }
        }
    }

    Connections {
        target: runner
        function onOutputAppended(chunk) {
            log.text += chunk
            log.cursorPosition = log.length
        }
    }
}
