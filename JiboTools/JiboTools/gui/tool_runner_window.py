from __future__ import annotations

import shlex
from pathlib import Path

from PySide6.QtCore import QObject, Slot
from PySide6.QtGui import QCloseEvent, QTextCursor
from PySide6.QtWidgets import QMainWindow, QApplication, QLabel, QLineEdit, QPushButton, QPlainTextEdit

from .process_runner import ProcessRunner, resolve_python_invocation
from .terminal_helper import TerminalHelper
from .ui_loader import load_ui, require_child


class ToolRunnerWindow(QObject):
    def __init__(self, *, title: str, script: str) -> None:
        super().__init__()

        self._script = script
        self._is_updater = "jibo_updater.py" in script

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
        self._log = require_child(self.window, "logEdit", QPlainTextEdit)
        self._status = require_child(self.window, "statusLabel", QLabel)
        self._clear = require_child(self.window, "clearLogButton", QPushButton)

        self._title_label.setText(title)

        self._host_field.setVisible(self._is_updater)

        self._start_stop.clicked.connect(self._toggle)
        self._open_terminal.clicked.connect(self._open_in_terminal)
        self._clear.clicked.connect(lambda: self._log.setPlainText(""))

        self.runner.outputAppended.connect(self._append_output)
        self.runner.runningChanged.connect(self._sync_buttons)
        self.runner.exitCodeChanged.connect(self._sync_status)

        self._sync_buttons()
        self._sync_status()

        # Ensure the process is stopped when the window closes.
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
        if extra:
            args += shlex.split(extra)

        return args

    @Slot()
    def _toggle(self) -> None:
        if self.runner.running:
            self.runner.stop()
        else:
            program, prefix = resolve_python_invocation()
            self.runner.start(program, [*prefix, *self._build_args()])

    @Slot()
    def _open_in_terminal(self) -> None:
        program, prefix = resolve_python_invocation()
        self.terminal.openTerminal(program, [*prefix, *self._build_args()])

    @Slot(str)
    def _append_output(self, chunk: str) -> None:
        # Keep it simple: append and scroll to end.
        self._log.moveCursor(QTextCursor.End)
        self._log.insertPlainText(chunk)
        self._log.moveCursor(QTextCursor.End)

    def _sync_buttons(self) -> None:
        running = self.runner.running
        self._start_stop.setText("Stop" if running else "Start")
        self._open_terminal.setEnabled(not running)

    def _sync_status(self) -> None:
        if self.runner.running:
            self._status.setText("Running...")
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


def run_tool_window(*, title: str, script: str) -> int:
    app = QApplication.instance() or QApplication([])
    win = ToolRunnerWindow(title=title, script=script)
    win.show()
    return int(app.exec())
