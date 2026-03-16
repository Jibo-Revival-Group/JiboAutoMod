from __future__ import annotations

from PySide6.QtCore import QObject, Slot

from .process_runner import spawn_in_terminal


class TerminalHelper(QObject):
    @Slot(str, list, result=bool)
    def openTerminal(self, program: str, arguments: list) -> bool:
        argv = [program] + [str(a) for a in arguments]
        return spawn_in_terminal(argv)
