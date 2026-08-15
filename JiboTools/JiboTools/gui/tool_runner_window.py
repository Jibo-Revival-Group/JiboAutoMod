from __future__ import annotations

import shlex
import re
from pathlib import Path

from PySide6.QtCore import QObject, Slot
from PySide6.QtGui import QCloseEvent, QTextCursor
from PySide6.QtWidgets import (
    QMainWindow,
    QApplication,
    QLabel,
    QLineEdit,
    QPushButton,
    QPlainTextEdit,
    QCheckBox,
    QFileDialog,
    QProgressBar,
)

from .process_runner import ProcessRunner, resolve_python_invocation
from .terminal_helper import TerminalHelper
from .ui_loader import load_ui, require_child


class ToolRunnerWindow(QObject):
    def __init__(self, *, title: str, script: str) -> None:
        super().__init__()

        self._script = script
        self._is_updater = "jibo_updater.py" in script
        self._is_installer = "jibo_automod.py" in script

        self._output_buffer = ""
        self._last_step_total: int | None = None

        ui_path = Path(__file__).resolve().parent / "tool_runner.ui"
        self.window = load_ui(ui_path)
        if not isinstance(self.window, QMainWindow):
            raise RuntimeError("tool_runner.ui must have a QMainWindow as root")

        self.window.setWindowTitle(title)

        self.runner = ProcessRunner()
        self.terminal = TerminalHelper()

        self._title_label = require_child(self.window, "titleLabel", QLabel)
        self._start_stop = require_child(self.window, "startStopButton", QPushButton)
        self._open_terminal = require_child(self.window, "openTerminalButton", QPushButton)
        self._host_field = require_child(self.window, "hostField", QLineEdit)
        self._extra_args = require_child(self.window, "extraArgsField", QLineEdit)
        self._description = require_child(self.window, "descriptionLabel", QLabel)
        self._firewall_only = require_child(self.window, "firewallOnlyCheck", QCheckBox)
        self._use_existing_dump = require_child(self.window, "useExistingDumpCheck", QCheckBox)
        self._dump_path = require_child(self.window, "dumpPathField", QLineEdit)
        self._browse_dump = require_child(self.window, "browseDumpButton", QPushButton)
        self._progress = require_child(self.window, "progressBar", QProgressBar)
        self._current_step = require_child(self.window, "currentStepLabel", QLabel)
        self._log = require_child(self.window, "logEdit", QPlainTextEdit)
        self._status = require_child(self.window, "statusLabel", QLabel)
        self._clear = require_child(self.window, "clearLogButton", QPushButton)

        self._title_label.setText(title)

        self._host_field.setVisible(self._is_updater)

        self._firewall_only.setVisible(self._is_installer)
        self._use_existing_dump.setVisible(self._is_installer)
        self._dump_path.setVisible(self._is_installer)
        self._browse_dump.setVisible(self._is_installer)
        self._progress.setVisible(self._is_installer)
        self._current_step.setVisible(self._is_installer)

        if self._is_installer:
            self._description.setText(
                "Choose 'Open SSH firewall only' to preserve normal mode while validating and "
                "patching both rootfs slots with mandatory read-back. Leave it unchecked for the "
                "legacy mode.json developer-mode workflow.\n"
                "Warning: Do not disconnect the robot during reads/writes."
            )
        elif self._is_updater:
            self._description.setText(
                "Updater will: download/extract a JiboOs release and upload the build/ overlay to the robot over SSH." 
            )
        else:
            self._description.setText("Run the selected tool with optional arguments.")

        self._dump_path.setEnabled(False)
        self._browse_dump.setEnabled(False)

        self._use_existing_dump.toggled.connect(self._sync_dump_widgets)
        self._firewall_only.toggled.connect(self._sync_dump_widgets)
        self._browse_dump.clicked.connect(self._pick_dump_path)
        self._sync_dump_widgets()

        self._progress.setRange(0, 6)
        self._progress.setValue(0)
        self._progress.setTextVisible(True)
        self._progress.setFormat("Step %v/%m")
        self._current_step.setText("Idle")

        self._start_stop.clicked.connect(self._toggle)
        self._open_terminal.clicked.connect(self._open_in_terminal)
        self._clear.clicked.connect(lambda: self._log.setPlainText(""))

        self.runner.outputAppended.connect(self._append_output)
        self.runner.runningChanged.connect(self._sync_buttons)
        self.runner.exitCodeChanged.connect(self._sync_status)

        self._sync_buttons()
        self._sync_status()

        self.window.closeEvent = self._on_close  # type: ignore[assignment]

    def show(self) -> None:
        self.window.show()

    def _build_args(self) -> list[str]:
        args: list[str] = [self._script]

        if self._is_updater:
            host = self._host_field.text().strip()
            if host:
                args += ["--ip", host]

        extra = self._extra_args.text().strip()
        extra_args: list[str] = shlex.split(extra) if extra else []

        if (self._is_installer and self._use_existing_dump.isChecked()
                and not self._firewall_only.isChecked()):
            dump_path = self._dump_path.text().strip()
            if dump_path and "--dump-path" not in extra_args:
                extra_args += ["--dump-path", dump_path]

        if self._is_installer and self._firewall_only.isChecked() and "--firewall-only" not in extra_args:
            extra_args += ["--firewall-only"]

        if extra_args:
            args += extra_args

        return args

    @Slot()
    def _toggle(self) -> None:
        if self.runner.running:
            self.runner.stop()
        else:
            if (self._is_installer and self._use_existing_dump.isChecked()
                    and not self._firewall_only.isChecked()
                    and not self._dump_path.text().strip()):
                self._status.setText("Pick a dump file (or uncheck 'existing dump')")
                return
            if (self._is_installer and self._use_existing_dump.isChecked()
                    and not self._firewall_only.isChecked()):
                p = Path(self._dump_path.text().strip())
                if not p.exists():
                    self._status.setText("Dump file not found")
                    return

            self._output_buffer = ""
            self._last_step_total = None
            if self._is_installer:
                self._progress.setRange(0, 0)
                self._progress.setValue(0)
                self._current_step.setText("Starting…")

            program, prefix = resolve_python_invocation()
            self.runner.start(program, [*prefix, *self._build_args()])

    @Slot()
    def _open_in_terminal(self) -> None:
        program, prefix = resolve_python_invocation()
        self.terminal.openTerminal(program, [*prefix, *self._build_args()])

    @Slot(str)
    def _append_output(self, chunk: str) -> None:
        self._log.moveCursor(QTextCursor.End)
        self._log.insertPlainText(chunk)
        self._log.moveCursor(QTextCursor.End)

        if self._is_installer:
            self._ingest_for_progress(chunk)

    def _sync_buttons(self) -> None:
        running = self.runner.running
        self._start_stop.setText("Stop" if running else "Start")
        self._open_terminal.setEnabled(not running)
        if not running and self._is_installer:
            if self.runner.exitCode == 0 and self._last_step_total:
                self._progress.setRange(0, self._last_step_total)
                self._progress.setValue(self._last_step_total)
                if self._current_step.text().strip() in ("", "Starting…"):
                    self._current_step.setText("Finished")
            elif self.runner.exitCode > 0:
                if self._current_step.text().strip() in ("", "Starting…"):
                    self._current_step.setText("Exited with errors")

    def _sync_status(self) -> None:
        if self.runner.running:
            self._status.setText("Running...")
            if self._is_installer and self._last_step_total is None:
                self._progress.setRange(0, 0)
            return
        code = self.runner.exitCode
        if code >= 0:
            self._status.setText(f"Exit: {code}")
        else:
            self._status.setText("Idle")

    def _on_close(self, event: QCloseEvent) -> None:
        try:
            self.runner.stop()
        except Exception:
            pass
        event.accept()

    @Slot(bool)
    def _sync_dump_widgets(self, checked: bool | None = None) -> None:
        enabled = self._use_existing_dump.isChecked() and not self._firewall_only.isChecked()
        self._use_existing_dump.setEnabled(not self._firewall_only.isChecked())
        self._dump_path.setEnabled(enabled)
        self._browse_dump.setEnabled(enabled)

    @Slot()
    def _pick_dump_path(self) -> None:
        start_dir = str(Path.home())
        path, _ = QFileDialog.getOpenFileName(
            self.window,
            "Select full eMMC dump (.bin)",
            start_dir,
            "Binary images (*.bin *.img *.raw);;All files (*)",
        )
        if path:
            self._dump_path.setText(path)

    def _ingest_for_progress(self, chunk: str) -> None:
        self._output_buffer += chunk
        lines = self._output_buffer.splitlines(keepends=True)

        if lines and not (lines[-1].endswith("\n") or lines[-1].endswith("\r")):
            self._output_buffer = lines[-1]
            lines = lines[:-1]
        else:
            self._output_buffer = ""

        for line in lines:
            clean = _strip_ansi(line).strip()
            if not clean:
                continue

            if clean.startswith(("ℹ", "⚠", "✓", "✗")) or "RCM" in clean:
                msg = _clean_status_line(clean)
                if msg and not msg.startswith("["):
                    self._current_step.setText(msg)

            m = re.search(r"\[(\d+)\s*/\s*(\d+)\]\s*(.+)$", clean)
            if not m:
                continue
            step = int(m.group(1))
            total = int(m.group(2))
            msg = m.group(3).strip()

            if total > 0:
                self._last_step_total = total
                self._progress.setRange(0, total)
                self._progress.setValue(max(0, min(step, total)))
                self._progress.setFormat("Step %v/%m")

            if msg:
                self._current_step.setText(msg)

    def _on_close(self, event: QCloseEvent) -> None:
        try:
            self.runner.stop()
        except Exception:
            pass
        event.accept()


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _strip_ansi(s: str) -> str:
    return _ANSI_RE.sub("", s)


def _clean_status_line(s: str) -> str:
    s = re.sub(r"^[✓⚠✗ℹ]\s+", "", s).strip()
    s = re.sub(r"\s+", " ", s).strip()
    return s


def run_tool_window(*, title: str, script: str) -> int:
    app = QApplication.instance() or QApplication([])
    win = ToolRunnerWindow(title=title, script=script)
    win.show()
    return int(app.exec())
