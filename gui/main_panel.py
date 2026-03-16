from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QUrl, QObject, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from .process_runner import ConnectionMonitor, resolve_python, resolve_python_invocation


class Launcher(QObject):
    def __init__(self, python_program: str, python_prefix: list[str]) -> None:
        super().__init__()
        self._python_program = python_program
        self._python_prefix = list(python_prefix)

    @Slot()
    def launchInstaller(self) -> None:
        # Start installer GUI in a separate process.
        import subprocess
        subprocess.Popen(
            [self._python_program, *self._python_prefix, "-m", "gui.installer_gui"],
            cwd=str(Path(__file__).resolve().parents[1]),
        )

    @Slot()
    def launchUpdater(self) -> None:
        import subprocess
        subprocess.Popen(
            [self._python_program, *self._python_prefix, "-m", "gui.updater_gui"],
            cwd=str(Path(__file__).resolve().parents[1]),
        )


def main() -> int:
    app = QGuiApplication(sys.argv)

    engine = QQmlApplicationEngine()

    conn = ConnectionMonitor()
    py_program, py_prefix = resolve_python_invocation()
    py_exec = resolve_python()
    engine.rootContext().setContextProperty("conn", conn)
    engine.rootContext().setContextProperty("pyExec", py_exec)
    engine.rootContext().setContextProperty("launcher", Launcher(py_program, py_prefix))

    qml_path = Path(__file__).resolve().parent / "qml" / "MainPanel.qml"
    engine.load(QUrl.fromLocalFile(str(qml_path)))

    if not engine.rootObjects():
        return 1

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
