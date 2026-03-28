from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

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
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
)

from .process_runner import resolve_python, resolve_python_invocation
from .ui_loader import load_ui, require_child
from .config_inventory import MISSING, diff_json, is_sensitive_path, load_config_entries_from_values_md, short_json


def _set_dot(label: QLabel, color: str) -> None:
    label.setStyleSheet(
        "QLabel {"
        f"background-color: {color};"
        "border-radius: 5px;"
        "}"
    )


class MainWindowController:
    _AI_BRIDGE_PATH = "/opt/jibo/Jibo/Skills/@be/be/be/ai-bridge-config.json"

    def __init__(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        ui_path = project_root / "form.ui"
        self.window = load_ui(ui_path)
        if not hasattr(self.window, "setWindowTitle"):
            raise RuntimeError("form.ui must have a QMainWindow root")

        self._ssh_client: Optional[object] = None
        self._identity: Optional[dict] = None
        self._connecting = False

        self.tab_widget = require_child(self.window, "tabWidget", QTabWidget)
        self.connection_pill, self.conn_dot, self.conn_text = self._create_connection_pill()
        self.tab_widget.setCornerWidget(self.connection_pill, Qt.TopRightCorner)

        self.jibo_ip = require_child(self.window, "JiboIpField", QLineEdit)
        self.connect_button = require_child(self.window, "TryToConnect", QPushButton)
        self.jibo_title = require_child(self.window, "jiboTitle", QLabel)
        self.override_check = require_child(self.window, "overrideCheck", QCheckBox)
        self.preview_connected_check = require_child(self.window, "previewConnectedCheck", QCheckBox)

        self.ha_enable = require_child(self.window, "haEnableCheck", QCheckBox)
        self.ha_server_ip = require_child(self.window, "haServerIpField", QLineEdit)

        self.ai_enable = require_child(self.window, "aiEnableCheck", QCheckBox)
        self.ai_mode = require_child(self.window, "aiProviderCombo", QComboBox)
        self.ai_server_base_url = require_child(self.window, "aiEndpointField", QLineEdit)
        self.ai_asr_host = require_child(self.window, "aiKeyField", QLineEdit)
        self.ai_record_seconds = require_child(self.window, "aiBridgeRecordSecondsSpin", QSpinBox)
        self.ai_use_asr_service_stt = require_child(self.window, "aiBridgeUseAsrServiceSttCheck", QCheckBox)
        self.ai_asr_port = require_child(self.window, "aiBridgeAsrPortSpin", QSpinBox)
        self.ai_asr_audio_source = require_child(self.window, "aiBridgeAsrAudioSourceField", QLineEdit)
        self.ai_asr_timeout_ms = require_child(self.window, "aiBridgeAsrTimeoutSpin", QSpinBox)
        self.ai_asr_auto_start = require_child(self.window, "aiBridgeAsrAutoStartCheck", QCheckBox)
        self.ai_followup_enabled = require_child(self.window, "aiBridgeFollowupEnabledCheck", QCheckBox)
        self.ai_followup_delay_ms = require_child(self.window, "aiBridgeFollowupDelaySpin", QSpinBox)
        self.edit_ai_bridge_button = require_child(self.window, "editAiBridgeConfigButton", QPushButton)

        self._ai_bridge_obj: Optional[dict[str, Any]] = None

        self.enable_logging_check = require_child(self.window, "enableLoggingCheck", QCheckBox)

        self.config_file_combo = require_child(self.window, "configFileCombo", QComboBox)
        self.config_read_button = require_child(self.window, "configReadButton", QPushButton)
        self.config_write_button = require_child(self.window, "configWriteButton", QPushButton)
        self.config_status_label = require_child(self.window, "configFileStatusLabel", QLabel)
        self.config_editor = require_child(self.window, "configEditor", QPlainTextEdit)
        self.config_activity_log = require_child(self.window, "configActivityLog", QPlainTextEdit)

        self._config_last_read_text: Optional[str] = None
        self._config_paths: list[str] = []

        self.robot_settings_button = require_child(self.window, "RobotSettings", QPushButton)
        self.robot_action_combo = require_child(self.window, "comboBox", QComboBox)
        self.jibo_image = require_child(self.window, "jiboImage", QLabel)

        self._robot_settings_window: Optional[object] = None

        self.install_button = require_child(self.window, "installButton", QPushButton)
        self.check_updates_button = require_child(self.window, "checkUpdatesButton", QPushButton)

        self.status_dot = require_child(self.window, "statusDot", QLabel)
        self.status_text = require_child(self.window, "statusText", QLabel)

        self._configure_ui()
        self._wire_signals()
        self._sync_enabled()
        self._sync_all()
        self._populate_config_file_combo()

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
        self.connection_pill.setStyleSheet(
            "QFrame#connectionPill {"
            "background-color: #f6f6f6;"
            "border: 1px solid #e4e4e4;"
            "border-radius: 14px;"
            "}"
        )

        self.ai_mode.clear()
        self.ai_mode.addItems(["TEXT", "AUDIO"])

        self.robot_settings_button.setEnabled(False)
        self.robot_action_combo.setEnabled(False)

        self.config_editor.setPlaceholderText("Select a config file, then Read")
        self.config_activity_log.setReadOnly(True)
        self.config_activity_log.setPlaceholderText("Logging is disabled")
        self.config_read_button.setEnabled(False)
        self.config_write_button.setEnabled(False)

        self.connect_button.setText("Connect")
        self.jibo_title.setText("Connect Your Jibo")

    def _wire_signals(self) -> None:
        self.connect_button.clicked.connect(self._toggle_connection)

        self.override_check.toggled.connect(self._sync_enabled)
        self.preview_connected_check.toggled.connect(self._sync_all)
        self.override_check.toggled.connect(self._sync_all)

        self.ha_enable.toggled.connect(self._sync_enabled)
        self.ai_enable.toggled.connect(self._sync_enabled)

        self.robot_settings_button.clicked.connect(self._open_robot_settings)

        self.edit_ai_bridge_button.clicked.connect(self._jump_to_ai_bridge_config)

        self.ai_enable.toggled.connect(self._sync_ai_bridge_obj_from_ui)
        self.ai_mode.currentIndexChanged.connect(self._sync_ai_bridge_obj_from_ui)
        self.ai_server_base_url.textChanged.connect(self._sync_ai_bridge_obj_from_ui)
        self.ai_asr_host.textChanged.connect(self._sync_ai_bridge_obj_from_ui)
        self.ai_record_seconds.valueChanged.connect(self._sync_ai_bridge_obj_from_ui)
        self.ai_use_asr_service_stt.toggled.connect(self._sync_ai_bridge_obj_from_ui)
        self.ai_asr_port.valueChanged.connect(self._sync_ai_bridge_obj_from_ui)
        self.ai_asr_audio_source.textChanged.connect(self._sync_ai_bridge_obj_from_ui)
        self.ai_asr_timeout_ms.valueChanged.connect(self._sync_ai_bridge_obj_from_ui)
        self.ai_asr_auto_start.toggled.connect(self._sync_ai_bridge_obj_from_ui)
        self.ai_followup_enabled.toggled.connect(self._sync_ai_bridge_obj_from_ui)
        self.ai_followup_delay_ms.valueChanged.connect(self._sync_ai_bridge_obj_from_ui)

        self.config_file_combo.currentIndexChanged.connect(self._on_config_combo_changed)
        self.config_read_button.clicked.connect(self._read_selected_config)
        self.config_write_button.clicked.connect(self._write_selected_config)
        self.config_editor.textChanged.connect(self._on_config_editor_changed)
        self.enable_logging_check.toggled.connect(self._sync_logging_placeholders)

        self.install_button.clicked.connect(self._launch_installer)
        self.check_updates_button.clicked.connect(self._launch_updater)

    def _open_robot_settings(self) -> None:
        if not self.session_connected or self._ssh_client is None:
            self.status_text.setText("Connect to a Jibo first")
            return

        try:
            from .robot_settings_window import RobotSettingsWindow  # local import to keep startup fast
        except Exception as e:
            self.status_text.setText(f"Failed to load Robot Settings UI: {e}")
            return

        if self._robot_settings_window is None:
            self._robot_settings_window = RobotSettingsWindow(
                ssh_client=self._ssh_client,
                logging_enabled_check=self.enable_logging_check,
            )
        try:
            self._robot_settings_window.set_ssh_client(self._ssh_client)  # type: ignore[attr-defined]
        except Exception:
            pass
        try:
            self._robot_settings_window.show()  # type: ignore[attr-defined]
        except Exception:
            pass

    def _sync_enabled(self) -> None:
        self.preview_connected_check.setEnabled(self.override_check.isChecked())
        self.ha_server_ip.setEnabled(self.ha_enable.isChecked())

        ai_enabled = self.ai_enable.isChecked()
        self.ai_mode.setEnabled(ai_enabled)
        self.ai_server_base_url.setEnabled(ai_enabled)
        self.ai_asr_host.setEnabled(ai_enabled)
        self.ai_record_seconds.setEnabled(ai_enabled)
        self.ai_use_asr_service_stt.setEnabled(ai_enabled)
        self.ai_asr_port.setEnabled(ai_enabled)
        self.ai_asr_audio_source.setEnabled(ai_enabled)
        self.ai_asr_timeout_ms.setEnabled(ai_enabled)
        self.ai_asr_auto_start.setEnabled(ai_enabled)
        self.ai_followup_enabled.setEnabled(ai_enabled)
        self.ai_followup_delay_ms.setEnabled(ai_enabled)

        self.connect_button.setEnabled(not self._connecting)

        connected = self.session_connected
        self.config_read_button.setEnabled(connected and self.config_file_combo.count() > 0)

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

        self._sync_enabled()

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
            if self._robot_settings_window is not None:
                try:
                    self._robot_settings_window.set_ssh_client(None)  # type: ignore[attr-defined]
                except Exception:
                    pass
            self.config_status_label.setText("Disconnected")
            self._config_last_read_text = None
            self.config_write_button.setEnabled(False)
            self._sync_all()

    def _sync_logging_placeholders(self) -> None:
        if self.enable_logging_check.isChecked():
            self.config_activity_log.setPlaceholderText("")
        else:
            self.config_activity_log.setPlaceholderText("Logging is disabled")

    def _log(self, message: str) -> None:
        if not self.enable_logging_check.isChecked():
            return
        self.config_activity_log.appendPlainText(message)

    def _populate_config_file_combo(self) -> None:
        entries = load_config_entries_from_values_md()
        paths = [e.remote_path for e in entries if not e.is_usr_local_etc]
        paths = sorted(paths)
        self._config_paths = paths

        self.config_file_combo.blockSignals(True)
        try:
            self.config_file_combo.clear()
            self.config_file_combo.addItems(paths)
        finally:
            self.config_file_combo.blockSignals(False)

        if paths:
            self.config_status_label.setText("Select a config to view/edit")
        else:
            self.config_status_label.setText("No configs found in inventory")

    def _jump_to_ai_bridge_config(self) -> None:
        target = self._AI_BRIDGE_PATH
        idx = self.config_file_combo.findText(target)
        if idx < 0:
            self.config_file_combo.addItem(target)
            idx = self.config_file_combo.findText(target)

        if idx >= 0:
            self.config_file_combo.setCurrentIndex(idx)
            self._read_selected_config()

            try:
                merged = self._merged_ai_bridge_obj_from_ui()
                desired_text = json.dumps(merged, indent=2, ensure_ascii=False) + "\n"
                self.config_editor.setPlainText(desired_text)
            except Exception:
                pass
            return
        self.config_status_label.setText("AI Bridge config not selectable")

    def _on_config_combo_changed(self) -> None:
        self._config_last_read_text = None
        self.config_write_button.setEnabled(False)
        p = self._selected_config_path()
        self.config_status_label.setText(p or "Select a config to view/edit")

    def _selected_config_path(self) -> Optional[str]:
        p = self.config_file_combo.currentText().strip()
        if p.startswith("/"):
            return p
        return None

    def _sftp_read_text(self, remote_path: str) -> str:
        if self._ssh_client is None:
            raise RuntimeError("Not connected")
        sftp = self._ssh_client.open_sftp()
        try:
            with sftp.open(remote_path, "r") as f:
                raw = f.read()
        finally:
            sftp.close()
        if isinstance(raw, bytes):
            return raw.decode("utf-8", errors="replace")
        return str(raw)

    def _sftp_write_text(self, remote_path: str, text: str) -> None:
        if self._ssh_client is None:
            raise RuntimeError("Not connected")
        sftp = self._ssh_client.open_sftp()
        try:
            with sftp.open(remote_path, "w") as f:
                f.write(text.encode("utf-8"))
        finally:
            sftp.close()

    def _ssh_exec(self, command: str, *, timeout: int = 30) -> tuple[int, str, str]:
        if self._ssh_client is None:
            raise RuntimeError("Not connected")
        stdin, stdout, stderr = self._ssh_client.exec_command(command, timeout=timeout)
        _ = stdin
        out = stdout.read()
        err = stderr.read()
        out_s = out.decode("utf-8", errors="replace") if isinstance(out, bytes) else str(out)
        err_s = err.decode("utf-8", errors="replace") if isinstance(err, bytes) else str(err)
        code = stdout.channel.recv_exit_status()
        return int(code), out_s, err_s

    def _read_selected_config(self) -> None:
        p = self._selected_config_path()
        if not p:
            return
        if not self.session_connected:
            self.config_status_label.setText("Connect to a Jibo first")
            return

        try:
            text = self._sftp_read_text(p)
            self._config_last_read_text = text
            self.config_editor.setPlainText(text)
            self.config_write_button.setEnabled(False)
            self.config_status_label.setText(f"Loaded {p}")
            self._log(f"READ {p} ({len(text)} bytes)")

            if p == self._AI_BRIDGE_PATH:
                try:
                    obj = json.loads(text)
                    if isinstance(obj, dict):
                        self._ai_bridge_obj = obj
                        self._apply_ai_bridge_obj_to_ui(obj)
                except Exception:
                    pass
        except Exception as e:
            self.config_status_label.setText(f"Read failed: {e}")
            self._log(f"READ FAILED {p}: {e}")

    def _load_ai_bridge_from_robot(self) -> None:
        if self._ssh_client is None:
            return
        try:
            raw = self._sftp_read_text(self._AI_BRIDGE_PATH)
        except Exception:
            return
        try:
            obj = json.loads(raw)
        except Exception:
            return
        if not isinstance(obj, dict):
            return
        self._ai_bridge_obj = obj
        self._apply_ai_bridge_obj_to_ui(obj)
        self._log(f"READ {self._AI_BRIDGE_PATH} (auto)")

    def _apply_ai_bridge_obj_to_ui(self, obj: dict[str, Any]) -> None:
        widgets = [
            self.ai_enable,
            self.ai_mode,
            self.ai_server_base_url,
            self.ai_asr_host,
            self.ai_record_seconds,
            self.ai_use_asr_service_stt,
            self.ai_asr_port,
            self.ai_asr_audio_source,
            self.ai_asr_timeout_ms,
            self.ai_asr_auto_start,
            self.ai_followup_enabled,
            self.ai_followup_delay_ms,
        ]
        for w in widgets:
            w.blockSignals(True)
        try:
            self.ai_enable.setChecked(bool(obj.get("enabled", True)))

            mode = str(obj.get("mode", "TEXT")).upper()
            idx = self.ai_mode.findText(mode)
            if idx >= 0:
                self.ai_mode.setCurrentIndex(idx)

            self.ai_server_base_url.setText(str(obj.get("serverBaseUrl", "")))
            self.ai_record_seconds.setValue(int(obj.get("recordSeconds", 5)))

            self.ai_use_asr_service_stt.setChecked(bool(obj.get("useAsrServiceStt", True)))
            self.ai_asr_host.setText(str(obj.get("asrServiceHost", "127.0.0.1")))
            self.ai_asr_port.setValue(int(obj.get("asrServicePort", 8088)))
            self.ai_asr_audio_source.setText(str(obj.get("asrAudioSourceId", "alsa1")))
            self.ai_asr_timeout_ms.setValue(int(obj.get("asrTimeoutMs", 15000)))
            self.ai_asr_auto_start.setChecked(bool(obj.get("asrAutoStart", True)))

            self.ai_followup_enabled.setChecked(bool(obj.get("followupEnabled", True)))
            self.ai_followup_delay_ms.setValue(int(obj.get("followupDelayMs", 250)))
        finally:
            for w in widgets:
                w.blockSignals(False)
        self._sync_enabled()

    def _ai_bridge_fields_from_ui(self) -> dict[str, Any]:
        mode = self.ai_mode.currentText().strip() or "TEXT"
        return {
            "enabled": bool(self.ai_enable.isChecked()),
            "mode": mode,
            "serverBaseUrl": self.ai_server_base_url.text().strip(),
            "recordSeconds": int(self.ai_record_seconds.value()),
            "useAsrServiceStt": bool(self.ai_use_asr_service_stt.isChecked()),
            "asrServiceHost": self.ai_asr_host.text().strip() or "127.0.0.1",
            "asrServicePort": int(self.ai_asr_port.value()),
            "asrAudioSourceId": self.ai_asr_audio_source.text().strip() or "alsa1",
            "asrTimeoutMs": int(self.ai_asr_timeout_ms.value()),
            "asrAutoStart": bool(self.ai_asr_auto_start.isChecked()),
            "followupEnabled": bool(self.ai_followup_enabled.isChecked()),
            "followupDelayMs": int(self.ai_followup_delay_ms.value()),
        }

    def _merged_ai_bridge_obj_from_ui(self) -> dict[str, Any]:
        base: dict[str, Any] = {}
        if isinstance(self._ai_bridge_obj, dict):
            base.update(self._ai_bridge_obj)
        base.update(self._ai_bridge_fields_from_ui())
        return base

    def _sync_ai_bridge_obj_from_ui(self, *_args: Any) -> None:
        try:
            self._ai_bridge_obj = self._merged_ai_bridge_obj_from_ui()
        except Exception:
            pass

    def _on_config_editor_changed(self) -> None:
        if self._config_last_read_text is None:
            self.config_write_button.setEnabled(False)
            return
        self.config_write_button.setEnabled(self.config_editor.toPlainText() != self._config_last_read_text)

    def _write_selected_config(self) -> None:
        p = self._selected_config_path()
        if not p:
            return
        if not self.session_connected:
            self.config_status_label.setText("Connect to a Jibo first")
            return

        new_text_raw = self.config_editor.toPlainText()
        try:
            new_obj = json.loads(new_text_raw)
        except Exception as e:
            self.config_status_label.setText(f"Invalid JSON: {e}")
            return

        new_text = json.dumps(new_obj, indent=2, ensure_ascii=False) + "\n"

        try:
            old_text = self._sftp_read_text(p)
        except Exception:
            old_text = ""
        try:
            old_obj: Any = json.loads(old_text) if old_text else MISSING
        except Exception:
            old_obj = MISSING

        if p.startswith("/usr/local/"):
            cmd = "mount -o remount,rw /usr/local"
            self._log(f"EXEC {cmd}")
            code, _out, err = self._ssh_exec(cmd, timeout=30)
            if code != 0:
                self.config_status_label.setText("Remount /usr/local failed")
                self._log(f"EXEC FAILED ({code}) {cmd} :: {err.strip()}")
                return

        if old_obj is not MISSING:
            diffs = diff_json(old_obj, new_obj)
            if diffs:
                self._log(f"WRITE {p} (changes: {len(diffs)})")
                for path, ov, nv in diffs[:200]:
                    if is_sensitive_path(path):
                        self._log(f"  {path}: *** -> ***")
                        continue
                    o = "<missing>" if ov is MISSING else short_json(ov)
                    n = "<missing>" if nv is MISSING else short_json(nv)
                    self._log(f"  {path}: {o} -> {n}")
                if len(diffs) > 200:
                    self._log(f"  ... ({len(diffs) - 200} more)")
            else:
                self._log(f"WRITE {p} (no JSON diffs detected)")
        else:
            self._log(f"WRITE {p} (no previous JSON to diff)")

        try:
            self._sftp_write_text(p, new_text)
            self._log(f"WROTE {p} ({len(new_text)} bytes)")
            self._config_last_read_text = new_text
            self.config_editor.setPlainText(new_text)
            self.config_write_button.setEnabled(False)
            self.config_status_label.setText(f"Wrote {p}")
        except Exception as e:
            self.config_status_label.setText(f"Write failed: {e}")
            self._log(f"WRITE FAILED {p}: {e}")

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

            self._ssh_client = client
            self._identity = identity if isinstance(identity, dict) else None
            self.status_text.setText(f"Connected via SSH to {host}")

            try:
                self._load_ai_bridge_from_robot()
            except Exception:
                pass
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
