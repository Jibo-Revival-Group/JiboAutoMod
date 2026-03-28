from __future__ import annotations

import os
import shlex
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QProcess, QTimer, Signal, Slot, Property


def _find_repo_root(start: Path) -> Path:
    """Find the outer JiboAutoMod repo root.

    The Qt Creator project lives under JiboTools/JiboTools, while the CLI tools
    (jibo_updater.py, jibo_automod.py) usually live in the outer repo root.
    """

    cur = start.resolve()
    for _ in range(6):
        if (cur / "jibo_updater.py").exists() and (cur / "jibo_automod.py").exists():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return start.resolve().parents[1]


REPO_ROOT = _find_repo_root(Path(__file__).resolve())


def resolve_python_invocation() -> tuple[str, list[str]]:
    """Return (program, prefix_args) to invoke Python reliably.

    On Windows, prefer the repo-local venv; otherwise prefer the `py -3` launcher
    when present so we don’t depend on `python.exe` being on PATH.
    """

    venv_py = REPO_ROOT / ".venv" / ("Scripts" if os.name == "nt" else "bin") / (
        "python.exe" if os.name == "nt" else "python"
    )
    if venv_py.exists():
        return (str(venv_py), [])

    try:
        if sys.executable and Path(sys.executable).exists():
            return (sys.executable, [])
    except Exception:
        pass

    if os.name == "nt" and shutil.which("py"):
        return ("py", ["-3"])

    if shutil.which("python3"):
        return ("python3", [])

    return ("python", [])


def resolve_python() -> str:
    program, prefix = resolve_python_invocation()
    if prefix:
        return " ".join([program] + prefix)
    return program


def can_connect(host: str, port: int, timeout_s: float = 0.8) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout_s):
            return True
    except OSError:
        return False


def _pick_terminal_command() -> Optional[list[str]]:
    if os.name == "nt":
        return None

    candidates: list[list[str]] = []
    candidates.append(["x-terminal-emulator", "-e"])
    candidates.append(["gnome-terminal", "--"])
    candidates.append(["konsole", "-e"])
    candidates.append(["xfce4-terminal", "-e"])
    candidates.append(["xterm", "-e"])

    for cmd in candidates:
        if shutil.which(cmd[0]):
            return cmd
    return None


def spawn_in_terminal(argv: list[str]) -> bool:
    """Best-effort external terminal launcher.

    Returns True if a terminal was spawned, False otherwise.
    """

    if os.name == "nt":
        cmdline = " ".join(shlex.quote(a) for a in argv)
        subprocess.Popen(["cmd", "/c", "start", "cmd", "/k", cmdline], shell=False)
        return True

    term = _pick_terminal_command()
    if not term:
        return False

    subprocess.Popen(term + argv, cwd=str(REPO_ROOT))
    return True


class ProcessRunner(QObject):
    runningChanged = Signal()
    exitCodeChanged = Signal()
    outputAppended = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._proc = QProcess(self)
        self._proc.setProcessChannelMode(QProcess.MergedChannels)
        self._proc.readyReadStandardOutput.connect(self._on_ready)
        self._proc.finished.connect(self._on_finished)
        self._exit_code: int = -1

    @Property(bool, notify=runningChanged)
    def running(self) -> bool:
        return self._proc.state() != QProcess.NotRunning

    @Property(int, notify=exitCodeChanged)
    def exitCode(self) -> int:
        return self._exit_code

    @Slot(str, list)
    def start(self, program: str, arguments: list) -> None:
        if self.running:
            return
        self._exit_code = -1
        self.exitCodeChanged.emit()
        self._proc.setProgram(program)
        self._proc.setArguments([str(a) for a in arguments])
        self._proc.setWorkingDirectory(str(REPO_ROOT))
        self._proc.start()
        self.runningChanged.emit()

    @Slot()
    def stop(self) -> None:
        if not self.running:
            return
        self._proc.terminate()
        if not self._proc.waitForFinished(1500):
            self._proc.kill()
        self.runningChanged.emit()

    def _on_ready(self) -> None:
        data = bytes(self._proc.readAllStandardOutput()).decode("utf-8", errors="replace")
        if data:
            self.outputAppended.emit(data)

    def _on_finished(self, exit_code: int, _status) -> None:
        self._exit_code = int(exit_code)
        self.exitCodeChanged.emit()
        self.runningChanged.emit()


class ConnectionMonitor(QObject):
    hostChanged = Signal()
    connectedChanged = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._host = ""
        self._connected = False
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._poll)
        self._timer.start()

    @Property(str, notify=hostChanged)
    def host(self) -> str:
        return self._host

    @host.setter
    def host(self, value: str) -> None:
        value = (value or "").strip()
        if value == self._host:
            return
        self._host = value
        self.hostChanged.emit()
        self._poll()

    @Property(bool, notify=connectedChanged)
    def connected(self) -> bool:
        return self._connected

    def _poll(self) -> None:
        host = self._host
        connected = False
        if host:
            connected = can_connect(host, 22)
        if connected != self._connected:
            self._connected = connected
            self.connectedChanged.emit()
