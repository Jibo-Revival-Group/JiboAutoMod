from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from .process_runner import ProcessRunner, resolve_python
from .terminal_helper import TerminalHelper


def main() -> int:
    app = QGuiApplication(sys.argv)

    engine = QQmlApplicationEngine()

    runner = ProcessRunner()
    terminal = TerminalHelper()
    engine.rootContext().setContextProperty("runner", runner)
    engine.rootContext().setContextProperty("terminal", terminal)
    engine.rootContext().setContextProperty("pyExec", resolve_python())
    engine.rootContext().setContextProperty("toolScript", "jibo_automod.py")
    engine.rootContext().setContextProperty("toolTitle", "Installer")

    qml_path = Path(__file__).resolve().parent / "qml" / "ToolRunner.qml"
    engine.load(QUrl.fromLocalFile(str(qml_path)))

    if not engine.rootObjects():
        return 1

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
