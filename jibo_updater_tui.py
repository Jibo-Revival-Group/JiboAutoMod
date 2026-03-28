#!/usr/bin/env python3
"""Simple curses TUI for selecting a distribution host and release.

This TUI reuses helper functions from `jibo_updater.py` to probe hosts and
list local archives. It prints a JSON object to stdout with the chosen
selection so other tools or a GUI wrapper can invoke it.

Usage:
  python3 jibo_updater_tui.py [--distributors Distributors.json]

Output (on success): JSON to stdout, e.g.
  {"host": "https://...","source":"remote","tag":"v3.3.0","tarball_url":"https://..."}

Keyboard:
- Up/Down: navigate
- Enter: select
- b: back
- v: view release notes/name
- q: quit
"""

from __future__ import annotations

import curses
import json
import sys
from pathlib import Path
from typing import List

try:
    from jibo_updater import (
        load_distributors_file,
        measure_host_latency,
        get_releases_from_host,
        list_local_archives,
        _version_tuple,
        check_updater_version,
        __version__ as UPDATER_VERSION,
        DEFAULT_UPDATER_RELEASES_API,
    )
except Exception as e:
    print(f"Failed to import helpers from jibo_updater: {e}", file=sys.stderr)
    raise


def gather_host_infos(distributors_path: Path):
    d = load_distributors_file(distributors_path)
    hosts = d.get("UpdateHosts") or d.get("OfficialHosts") or []
    hosts = [h for h in hosts if isinstance(h, str)]

    infos = []
    for h in hosts:
        lat = measure_host_latency(h)
        rels = get_releases_from_host(h)
        infos.append({"host": h, "lat": lat, "rels": rels})

    local = list_local_archives()
    if local:
        infos.append({"host": "local", "lat": 0.0, "rels": local})

    infos.sort(key=lambda x: x["lat"] if isinstance(x["lat"], float) else float("inf"))
    return infos


class TUI:
    def __init__(self, stdscr, distributors: Path):
        self.stdscr = stdscr
        self.distributors = distributors
        curses.curs_set(0)
        try:
            latest, is_newer = check_updater_version(DEFAULT_UPDATER_RELEASES_API, UPDATER_VERSION)
            if latest and is_newer:
                self.updater_status = f"Updater update available: {latest} (current {UPDATER_VERSION})"
            elif latest:
                self.updater_status = f"Updater up-to-date ({UPDATER_VERSION})"
            else:
                self.updater_status = "Updater version check failed"
        except Exception:
            self.updater_status = "Updater version check failed"

        self.hosts = gather_host_infos(distributors)

    def draw_list(self, items: List[str], title: str, idx: int, offset: int = 0):
        self.stdscr.clear()
        h, w = self.stdscr.getmaxyx()
        header = title[: w - 1]
        status = (" - " + self.updater_status) if hasattr(self, "updater_status") else ""
        if len(header) + len(status) < w - 1:
            header = header + status
        self.stdscr.addstr(0, 0, header[: w - 1])
        for i, line in enumerate(items[offset : offset + h - 3]):
            y = i + 2
            style = curses.A_REVERSE if (i + offset) == idx else curses.A_NORMAL
            try:
                self.stdscr.addstr(y, 0, line[: w - 1], style)
            except curses.error:
                pass
        self.stdscr.addstr(h - 1, 0, "Enter=select  v=view  b=back  q=quit")
        self.stdscr.refresh()

    def run(self):
        if not self.hosts:
            self.stdscr.addstr(0, 0, "No hosts found in distributors file or no local archives.")
            self.stdscr.addstr(2, 0, "Press any key to exit.")
            self.stdscr.getch()
            return 1

        idx = 0
        offset = 0
        while True:
            items = [f"{h['host']}  ({'local' if h['host']=='local' else f'{h['lat']:.2f}s'}) - {len(h['rels'])} releases" for h in self.hosts]
            self.draw_list(items, "Select host:", idx, offset)
            c = self.stdscr.getch()
            if c in (curses.KEY_DOWN, ord('j')):
                if idx < len(items) - 1:
                    idx += 1
            elif c in (curses.KEY_UP, ord('k')):
                if idx > 0:
                    idx -= 1
            elif c in (ord('\n'), ord('\r')):
                choice = self.hosts[idx]
                res = self.show_releases(choice)
                if res:
                    print(json.dumps(res))
                    return 0
            elif c in (ord('q'), 27):
                return 1

    def show_releases(self, host_info):
        rels = host_info["rels"]
        if not rels:
            return None
        rels.sort(key=lambda r: _version_tuple(r.tag_name), reverse=True)
        idx = 0
        while True:
            items = [f"{r.tag_name}{' [prerelease]' if r.prerelease else ''} - {r.name}" for r in rels]
            self.draw_list(items, f"Host: {host_info['host']}", idx)
            c = self.stdscr.getch()
            if c in (curses.KEY_DOWN, ord('j')):
                if idx < len(items) - 1:
                    idx += 1
            elif c in (curses.KEY_UP, ord('k')):
                if idx > 0:
                    idx -= 1
            elif c in (ord('b'), 8):
                return None
            elif c == ord('v'):
                self.show_text(rels[idx].name or "(no notes)")
            elif c in (ord('\n'), ord('\r')):
                chosen = rels[idx]
                res = {
                    "host": host_info["host"],
                    "source": "local" if host_info["host"] == "local" else "remote",
                    "tag": chosen.tag_name,
                    "tarball_url": chosen.tarball_url,
                }
                return res
            elif c in (ord('q'), 27):
                return None

    def show_text(self, text: str):
        self.stdscr.clear()
        h, w = self.stdscr.getmaxyx()
        lines = []
        for ln in text.splitlines():
            while ln:
                lines.append(ln[: w - 1])
                ln = ln[w - 1 :]
        for i, ln in enumerate(lines[: h - 2]):
            try:
                self.stdscr.addstr(i, 0, ln)
            except curses.error:
                pass
        self.stdscr.addstr(h - 1, 0, "Press any key to return")
        self.stdscr.refresh()
        self.stdscr.getch()


def main(argv):
    import argparse

    parser = argparse.ArgumentParser(description="Curses TUI for jibo_updater selection")
    parser.add_argument("--distributors", type=Path, default=Path("Distributors.json"), help="Path to Distributors.json")
    args = parser.parse_args(argv)

    curses.wrapper(lambda stdscr: TUI(stdscr, args.distributors).run())


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]) or 0)
