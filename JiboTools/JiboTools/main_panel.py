"""Qt Creator entrypoint.

This project is intended to run cleanly from Qt Creator. The UI is implemented
with Qt Widgets loaded from `.ui` files at runtime (see gui/main_panel.py and
form.ui).
"""

from __future__ import annotations


def main() -> int:
    from gui.main_panel import main as widgets_main

    return int(widgets_main())


if __name__ == "__main__":
    raise SystemExit(main())
