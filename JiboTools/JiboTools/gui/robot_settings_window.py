from __future__ import annotations

import json
import time
from typing import Any, Optional

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QCheckBox,
)
from .config_inventory import ConfigEntry, MISSING, diff_json, is_sensitive_path, load_config_entries_from_values_md, short_json


class RobotSettingsWindow:
    def __init__(self, *, ssh_client: object, logging_enabled_check: QCheckBox) -> None:
        self._ssh_client: Optional[object] = ssh_client
        self._logging_enabled_check = logging_enabled_check

        self.window = QMainWindow()
        self.window.setWindowTitle("Robot Settings")

        root = QWidget()
        self.window.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        self.status = QLabel("Select a config to view/edit")
        self.status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        outer.addWidget(self.status)

        splitter = QSplitter(Qt.Horizontal)
        outer.addWidget(splitter, 1)

        # Left: tree
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setSelectionMode(QAbstractItemView.SingleSelection)
        splitter.addWidget(self.tree)

        # Right: editor + buttons + log
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(8)

        self.read_button = QPushButton("Read")
        self.write_button = QPushButton("Write")
        self.write_button.setEnabled(False)
        btn_layout.addWidget(self.read_button)
        btn_layout.addWidget(self.write_button)
        btn_layout.addStretch(1)

        right_layout.addWidget(btn_row)

        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText("Select a config file from the list to load it")
        right_layout.addWidget(self.editor, 1)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(2000)
        self.log.setPlaceholderText("Logging is disabled")
        right_layout.addWidget(QLabel("Activity log"))
        right_layout.addWidget(self.log, 1)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([260, 520])

        self._entries: list[ConfigEntry] = []
        self._current_remote_path: Optional[str] = None
        self._last_read_text: Optional[str] = None

        self._populate_tree()
        self._wire_signals()

        self._sync_logging_ui()

    def show(self) -> None:
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()

    def set_ssh_client(self, client: Optional[object]) -> None:
        self._ssh_client = client

    def _wire_signals(self) -> None:
        self.tree.itemSelectionChanged.connect(self._on_tree_selection)
        self.read_button.clicked.connect(self._read_current)
        self.write_button.clicked.connect(self._write_current)
        self.editor.textChanged.connect(self._on_editor_changed)
        self._logging_enabled_check.toggled.connect(self._sync_logging_ui)

    def _sync_logging_ui(self) -> None:
        if self._logging_enabled_check.isChecked():
            self.log.setPlaceholderText("")
        else:
            self.log.setPlaceholderText("Logging is disabled")

    def _log(self, message: str) -> None:
        if not self._logging_enabled_check.isChecked():
            return
        ts = time.strftime("%H:%M:%S")
        self.log.appendPlainText(f"[{ts}] {message}")

    def _populate_tree(self) -> None:
        self.tree.clear()
        self._entries = load_config_entries_from_values_md()

        root_settings = QTreeWidgetItem(["Settings (/usr/local/etc)"])
        self.tree.addTopLevelItem(root_settings)
        root_settings.setExpanded(True)

        def add_entry(parent: QTreeWidgetItem, entry: ConfigEntry) -> None:
            item = QTreeWidgetItem([entry.remote_path])
            item.setData(0, Qt.UserRole, entry.remote_path)
            parent.addChild(item)

        count = 0
        for e in sorted(self._entries, key=lambda x: x.remote_path):
            if e.is_usr_local_etc:
                add_entry(root_settings, e)
                count += 1

        if count == 0:
            root_settings.addChild(QTreeWidgetItem(["(No /usr/local/etc configs found in inventory)"]))

    def _selected_remote_path(self) -> Optional[str]:
        items = self.tree.selectedItems()
        if not items:
            return None
        item = items[0]
        p = item.data(0, Qt.UserRole)
        if isinstance(p, str) and p.startswith("/"):
            return p
        return None

    @Slot()
    def _on_tree_selection(self) -> None:
        p = self._selected_remote_path()
        self._current_remote_path = p
        self.write_button.setEnabled(False)
        self._last_read_text = None
        if p:
            self.status.setText(p)
            self._read_current()
        else:
            self.status.setText("Select a config to view/edit")

    @Slot()
    def _on_editor_changed(self) -> None:
        # Enable write only if we have a loaded file and text changed.
        if not self._current_remote_path or self._last_read_text is None:
            self.write_button.setEnabled(False)
            return
        self.write_button.setEnabled(self.editor.toPlainText() != self._last_read_text)

    def _require_ssh(self) -> object:
        if self._ssh_client is None:
            raise RuntimeError("Not connected")
        return self._ssh_client

    def _ssh_exec(self, command: str, *, timeout: int = 30) -> tuple[int, str, str]:
        client = self._require_ssh()
        stdin, stdout, stderr = client.exec_command(command, timeout=timeout)  # type: ignore[attr-defined]
        _ = stdin
        out = stdout.read()
        err = stderr.read()
        if isinstance(out, bytes):
            out_s = out.decode("utf-8", errors="replace")
        else:
            out_s = str(out)
        if isinstance(err, bytes):
            err_s = err.decode("utf-8", errors="replace")
        else:
            err_s = str(err)
        code = stdout.channel.recv_exit_status()  # type: ignore[attr-defined]
        return int(code), out_s, err_s

    def _sftp_read_text(self, remote_path: str) -> str:
        client = self._require_ssh()
        sftp = client.open_sftp()  # type: ignore[attr-defined]
        try:
            with sftp.open(remote_path, "r") as f:
                raw = f.read()
        finally:
            sftp.close()
        if isinstance(raw, bytes):
            return raw.decode("utf-8", errors="replace")
        return str(raw)

    def _sftp_write_text(self, remote_path: str, text: str) -> None:
        client = self._require_ssh()
        sftp = client.open_sftp()  # type: ignore[attr-defined]
        try:
            with sftp.open(remote_path, "w") as f:
                data = text.encode("utf-8")
                f.write(data)
        finally:
            sftp.close()

    @Slot()
    def _read_current(self) -> None:
        remote_path = self._current_remote_path
        if not remote_path:
            return

        try:
            text = self._sftp_read_text(remote_path)
            self._log(f"READ {remote_path} ({len(text)} bytes)")
            self.editor.setPlainText(text)
            self._last_read_text = text
            self.write_button.setEnabled(False)
        except Exception as e:
            self.status.setText(f"Read failed: {e}")
            self._log(f"READ FAILED {remote_path}: {e}")
            QMessageBox.critical(self.window, "Read failed", str(e))

    @Slot()
    def _write_current(self) -> None:
        remote_path = self._current_remote_path
        if not remote_path:
            return

        new_text_raw = self.editor.toPlainText()

        # Validate JSON if possible; this tool is focused on strict JSON configs.
        try:
            new_obj = json.loads(new_text_raw)
        except Exception as e:
            QMessageBox.warning(self.window, "Invalid JSON", f"JSON parse failed: {e}")
            return

        # Canonicalize to keep robot-side JSON strict/clean.
        new_text = json.dumps(new_obj, indent=2, ensure_ascii=False) + "\n"

        try:
            old_text = self._sftp_read_text(remote_path)
        except Exception:
            old_text = ""

        old_obj: Any
        try:
            old_obj = json.loads(old_text) if old_text else MISSING
        except Exception:
            old_obj = MISSING

        # Mounted dir special case: /usr/local/* is often read-only until remount.
        if remote_path.startswith("/usr/local/"):
            cmd = "mount -o remount,rw /usr/local"
            self._log(f"EXEC {cmd}")
            code, out, err = self._ssh_exec(cmd, timeout=30)
            if code != 0:
                self._log(f"EXEC FAILED ({code}) {cmd} :: {err.strip()}")
                QMessageBox.critical(
                    self.window,
                    "Remount failed",
                    f"Failed to remount /usr/local read-write (exit {code}).\n\n{err.strip()}",
                )
                return
            if out.strip():
                self._log(out.strip())

        # Compute diffs (best-effort).
        if old_obj is not MISSING:
            diffs = diff_json(old_obj, new_obj)
            if diffs:
                self._log(f"WRITE {remote_path} (changes: {len(diffs)})")
                for p, ov, nv in diffs[:200]:
                    if is_sensitive_path(p):
                        self._log(f"  {p}: *** -> ***")
                        continue
                    o = "<missing>" if ov is MISSING else short_json(ov)
                    n = "<missing>" if nv is MISSING else short_json(nv)
                    self._log(f"  {p}: {o} -> {n}")
                if len(diffs) > 200:
                    self._log(f"  ... ({len(diffs) - 200} more)")
            else:
                self._log(f"WRITE {remote_path} (no JSON diffs detected)")
        else:
            self._log(f"WRITE {remote_path} (no previous JSON to diff)")

        try:
            self._sftp_write_text(remote_path, new_text)
            self._log(f"WROTE {remote_path} ({len(new_text)} bytes)")
            # Refresh read baseline.
            self.editor.setPlainText(new_text)
            self._last_read_text = new_text
            self.write_button.setEnabled(False)
            self.status.setText(f"Wrote {remote_path}")
        except Exception as e:
            self.status.setText(f"Write failed: {e}")
            self._log(f"WRITE FAILED {remote_path}: {e}")
            QMessageBox.critical(self.window, "Write failed", str(e))
