from __future__ import annotations

from pathlib import Path
from typing import TypeVar, cast

from PySide6.QtCore import QFile
from PySide6.QtUiTools import QUiLoader


T = TypeVar("T")


def load_ui(ui_path: Path) -> object:
    loader = QUiLoader()
    file = QFile(str(ui_path))
    if not file.open(QFile.ReadOnly):
        raise RuntimeError(f"Failed to open UI file: {ui_path}")
    try:
        widget = loader.load(file)
    finally:
        file.close()

    if widget is None:
        raise RuntimeError(f"Failed to load UI: {ui_path}")

    return widget


def require_child(parent: object, name: str, typ: type[T]) -> T:
    # Qt objects implement findChild; keep typing light.
    child = parent.findChild(typ, name)  # type: ignore[attr-defined]
    if child is None:
        raise RuntimeError(f"UI is missing required widget '{name}' ({typ.__name__})")
    return cast(T, child)
