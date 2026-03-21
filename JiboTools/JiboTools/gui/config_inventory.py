from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


_SENSITIVE_SUBSTRINGS = ("appkey", "key", "credential", "password", "token")


@dataclass(frozen=True)
class ConfigEntry:
    remote_path: str

    @property
    def is_usr_local_etc(self) -> bool:
        return self.remote_path.startswith("/usr/local/etc/")


class _Missing:
    pass


MISSING = _Missing()


_HEADING_RE = re.compile(r"^###\s+(/\S+)")


def _find_inventory_file(filename: str) -> Optional[Path]:
    """Find inventory markdown files shipped with the repo.

    The GUI package layout is:
      JiboTools/JiboTools/gui/*.py
    so we search:
      - JiboTools/ (packaged copy)
      - repo root (workspace copy)
    """

    here = Path(__file__).resolve()
    pkg_root = here.parents[2]  # .../JiboTools
    repo_root = pkg_root.parent  # .../JiboAutoModv2

    for p in (pkg_root / filename, repo_root / filename):
        if p.exists():
            return p
    return None


def load_config_entries_from_values_md() -> list[ConfigEntry]:
    values_md = _find_inventory_file("CONFIG_VALUES.md")
    if values_md is None:
        return []

    entries: list[ConfigEntry] = []
    seen: set[str] = set()

    for line in values_md.read_text("utf-8", errors="replace").splitlines():
        m = _HEADING_RE.match(line.strip())
        if not m:
            continue
        path = m.group(1).strip()
        if not path.startswith("/"):
            continue
        if path in seen:
            continue

        # Filter out non-robot/server dev configs the user doesn't want here.
        if path.startswith("/hub-shim/"):
            continue
        if path.lower().endswith(".md"):
            continue

        # Keep it focused on JSON files (these are strict JSON configs).
        if not path.lower().endswith(".json"):
            continue

        seen.add(path)
        entries.append(ConfigEntry(remote_path=path))

    return entries


def is_sensitive_path(path: str) -> bool:
    p = path.lower()
    return any(s in p for s in _SENSITIVE_SUBSTRINGS)


def short_json(value: Any, *, limit: int = 180) -> str:
    try:
        s = json.dumps(value, ensure_ascii=False)
    except Exception:
        s = repr(value)
    if len(s) > limit:
        return s[: limit - 3] + "..."
    return s


def diff_json(old: Any, new: Any, prefix: str = "") -> list[tuple[str, Any, Any]]:
    diffs: list[tuple[str, Any, Any]] = []

    if isinstance(old, dict) and isinstance(new, dict):
        keys = set(old.keys()) | set(new.keys())
        for key in sorted(keys, key=lambda x: str(x)):
            old_value = old.get(key, MISSING)
            new_value = new.get(key, MISSING)
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            if old_value is MISSING or new_value is MISSING:
                diffs.append((child_prefix, old_value, new_value))
            else:
                diffs.extend(diff_json(old_value, new_value, child_prefix))
        return diffs

    if isinstance(old, list) and isinstance(new, list):
        max_len = max(len(old), len(new))
        for i in range(max_len):
            old_value = old[i] if i < len(old) else MISSING
            new_value = new[i] if i < len(new) else MISSING
            child_prefix = f"{prefix}[{i}]"
            if old_value is MISSING or new_value is MISSING:
                diffs.append((child_prefix, old_value, new_value))
            else:
                diffs.extend(diff_json(old_value, new_value, child_prefix))
        return diffs

    if old != new:
        diffs.append((prefix or "<root>", old, new))

    return diffs
