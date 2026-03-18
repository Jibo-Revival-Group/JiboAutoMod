from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
)

from .process_runner import resolve_python, resolve_python_invocation
from .ui_loader import load_ui, require_child


def _set_dot(label: QLabel, color: str) -> None:
    label.setStyleSheet(
        "QLabel {"
        f"background-color: {color};"
        "border-radius: 5px;"
        "}"
    )


class MainWindowController:
    def __init__(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        ui_path = project_root / "form.ui"
        self.window = load_ui(ui_path)
        if not hasattr(self.window, "setWindowTitle"):
            raise RuntimeError("form.ui must have a QMainWindow root")

        self._ssh_client: Optional[object] = None
        self._identity: Optional[dict] = None
        self._connecting = False

        # Tabs + connection pill
        self.tab_widget = require_child(self.window, "tabWidget", QTabWidget)
        self.connection_pill, self.conn_dot, self.conn_text = self._create_connection_pill()
        self.tab_widget.setCornerWidget(self.connection_pill, Qt.TopRightCorner)

        # Jibo/config
        self.jibo_ip = require_child(self.window, "JiboIpField", QLineEdit)
        self.connect_button = require_child(self.window, "TryToConnect", QPushButton)
        self.jibo_title = require_child(self.window, "jiboTitle", QLabel)
        self.override_check = require_child(self.window, "overrideCheck", QCheckBox)
        self.preview_connected_check = require_child(self.window, "previewConnectedCheck", QCheckBox)

        self.ha_enable = require_child(self.window, "haEnableCheck", QCheckBox)
        self.ha_server_ip = require_child(self.window, "haServerIpField", QLineEdit)

        self.ai_enable = require_child(self.window, "aiEnableCheck", QCheckBox)
        self.ai_provider = require_child(self.window, "aiProviderCombo", QComboBox)
        self.ai_endpoint = require_child(self.window, "aiEndpointField", QLineEdit)
        self.ai_key = require_child(self.window, "aiKeyField", QLineEdit)
        self.tokens_used = require_child(self.window, "tokensUsedLabel", QLabel)

        # Jibo card controls
        self.robot_settings_button = require_child(self.window, "RobotSettings", QPushButton)
        self.robot_action_combo = require_child(self.window, "comboBox", QComboBox)
        self.jibo_image = require_child(self.window, "jiboImage", QLabel)

        # Update page
        self.install_button = require_child(self.window, "installButton", QPushButton)
        self.check_updates_button = require_child(self.window, "checkUpdatesButton", QPushButton)

        # Status page
        self.status_dot = require_child(self.window, "statusDot", QLabel)
        self.status_text = require_child(self.window, "statusText", QLabel)

        self._configure_ui()
        self._wire_signals()
        self._sync_enabled()
        self._sync_all()

    @property
    def host(self) -> str:
        return self.jibo_ip.text().strip()

    @property
    def session_connected(self) -> bool:
        return self._ssh_client is not None

    def effective_connected(self) -> bool:
        """Effective connection state for visuals.

        The Preview override is kept for UI testing, but the real connect/
        disconnect state comes from an active SSH session.
        """

        if self.override_check.isChecked():
            return self.preview_connected_check.isChecked()
        return self.session_connected

    def _configure_ui(self) -> None:
        # Simple styling, roughly matching the previous QML look.
        self.connection_pill.setStyleSheet(
            "QFrame#connectionPill {"
            "background-color: #f6f6f6;"
            "border: 1px solid #e4e4e4;"
            "border-radius: 14px;"
            "}"
        )

        # Provider choices
        self.ai_provider.clear()
        self.ai_provider.addItems(["Self-hosted", "OpenAI", "Other"])

        # Robot controls start disabled until connected.
        self.robot_settings_button.setEnabled(False)
        self.robot_action_combo.setEnabled(False)

        # Defaults
        self.tokens_used.setText("-1")
        self.connect_button.setText("Connect")
        self.jibo_title.setText("Connect Your Jibo")

    def _wire_signals(self) -> None:
        self.connect_button.clicked.connect(self._toggle_connection)

        self.override_check.toggled.connect(self._sync_enabled)
        self.preview_connected_check.toggled.connect(self._sync_all)
        self.override_check.toggled.connect(self._sync_all)

        self.ha_enable.toggled.connect(self._sync_enabled)
        self.ai_enable.toggled.connect(self._sync_enabled)

        self.install_button.clicked.connect(self._launch_installer)
        self.check_updates_button.clicked.connect(self._launch_updater)

    def _sync_enabled(self) -> None:
        self.preview_connected_check.setEnabled(self.override_check.isChecked())
        self.ha_server_ip.setEnabled(self.ha_enable.isChecked())

        ai_enabled = self.ai_enable.isChecked()
        self.ai_provider.setEnabled(ai_enabled)
        self.ai_endpoint.setEnabled(ai_enabled)
        self.ai_key.setEnabled(ai_enabled)

        # Connection button enabled unless a connect attempt is in progress.
        self.connect_button.setEnabled(not self._connecting)

    def _sync_all(self) -> None:
        host = self.host
        connected = self.session_connected
        visual_connected = self.effective_connected()

        if connected:
            title = (self._identity or {}).get("name") or "Connected"
        else:
            title = "Connect Your Jibo"
        self.jibo_title.setText(title)

        self.robot_settings_button.setEnabled(connected)
        self.robot_action_combo.setEnabled(connected)
        self.connect_button.setText("Disconnect" if connected else "Connect")

        dot_color = "#2ecc71" if connected else ("#e67e22" if host else "#bdc3c7")
        _set_dot(self.conn_dot, dot_color)
        _set_dot(self.status_dot, dot_color)

        if connected:
            self.conn_text.setText("Connected")
        else:
            self.conn_text.setText("Disconnected" if host else "No IP")

        if connected:
            self.status_text.setText(f"Connected via SSH to {host}" if host else "Connected via SSH")
        elif host:
            self.status_text.setText(f"Disconnected ({host})")
        else:
            self.status_text.setText("No Jibo IP configured")

        # Image swap
        assets = Path(__file__).resolve().parent / "Assets" / "Jibo"
        img_path = assets / ("JiboFaceForward.png" if visual_connected else "NoJiboConnected.png")
        pm = QPixmap(str(img_path))
        if not pm.isNull():
            pm = pm.scaled(
                self.jibo_image.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        self.jibo_image.setPixmap(pm)

    def _launch_installer(self) -> None:
        program, prefix = resolve_python_invocation()
        subprocess.Popen(
            [program, *prefix, "-m", "gui.installer_gui"],
            cwd=str(Path(__file__).resolve().parents[1]),
        )

    def _launch_updater(self) -> None:
        program, prefix = resolve_python_invocation()
        subprocess.Popen(
            [program, *prefix, "-m", "gui.updater_gui"],
            cwd=str(Path(__file__).resolve().parents[1]),
        )

    def _disconnect(self) -> None:
        try:
            if self._ssh_client is not None:
                self._ssh_client.close()
        finally:
            self._ssh_client = None
            self._identity = None
            self._sync_all()

    def _toggle_connection(self) -> None:
        if self.session_connected:
            self._disconnect()
            return

        host = self.host
        if not host:
            self.status_text.setText("Enter a Jibo IP address")
            return

        self._connecting = True
        self._sync_enabled()
        self.status_text.setText(f"Connecting to {host}...")

        try:
            import paramiko  # type: ignore
        except Exception:
            self._connecting = False
            self._sync_enabled()
            self.status_text.setText("Paramiko not installed; install requirements")
            return

        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(
                hostname=host,
                username="root",
                password="jibo",
                look_for_keys=False,
                allow_agent=False,
                timeout=10,
                banner_timeout=10,
                auth_timeout=10,
            )

            sftp = client.open_sftp()
            try:
                with sftp.open("/var/jibo/identity.json", "r") as f:
                    raw = f.read()
            finally:
                sftp.close()

            if isinstance(raw, bytes):
                raw_text = raw.decode("utf-8", errors="replace")
            else:
                raw_text = str(raw)

            identity = json.loads(raw_text)

            # Success: store session.
            self._ssh_client = client
            self._identity = identity if isinstance(identity, dict) else None
            self.status_text.setText(f"Connected via SSH to {host}")
        except Exception as e:
            try:
                client.close()
            except Exception:
                pass
            self.status_text.setText(f"Connect failed: {e}")
        finally:
            self._connecting = False
            self._sync_enabled()
            self._sync_all()

    def _create_connection_pill(self) -> tuple[QFrame, QLabel, QLabel]:
        pill = QFrame()
        pill.setObjectName("connectionPill")

        layout = QHBoxLayout(pill)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(6)

        dot = QLabel()
        dot.setObjectName("connDot")
        dot.setFixedSize(10, 10)

        text = QLabel("No IP")
        text.setObjectName("connText")

        layout.addWidget(dot)
        layout.addWidget(text)

        # Keep it tight on the tab bar.
        pill.setSizePolicy(pill.sizePolicy().horizontalPolicy(), pill.sizePolicy().verticalPolicy())
        pill.setMinimumHeight(28)
        return pill, dot, text


def main() -> int:
    _ = resolve_python  # keep import stable (used elsewhere)
    app = QApplication(sys.argv)
    ctrl = MainWindowController()
    ctrl.window.show()
    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main())
