from __future__ import annotations

import sys
from PySide6.QtWidgets import QApplication

from .tool_runner_window import ToolRunnerWindow


def main() -> int:
    app = QApplication(sys.argv)
    win = ToolRunnerWindow(title="Updater", script="jibo_updater.py")
    win.show()
    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main())
