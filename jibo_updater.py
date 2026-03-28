#!/usr/bin/env python3
"""Jibo OS Updater

Downloads the latest JiboOs release from the configured Gitea instance,
extracts it, then uploads the contents of the release "build" folder into
Jibo's root filesystem over SFTP.

High-level flow:
1) Check latest release
2) Download + extract archive
3) SSH into Jibo (root / password)
4) Remount / as read-write
5) SFTP upload build/ contents into /
6) Optionally switch /var/jibo/mode.json back to "normal"

This tool assumes your Jibo is already modded and reachable via SSH.
"""

from __future__ import annotations

import argparse
import json
import os
import posixpath
import re
import shutil
import sys
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional
import socket
import threading
import http.server
import socketserver

import paramiko


SCRIPT_DIR = Path(__file__).parent.resolve()
WORK_DIR = SCRIPT_DIR / "jibo_work"
UPDATES_DIR = WORK_DIR / "updates"
STATE_FILE_DEFAULT = WORK_DIR / "update_state.json"

__version__ = "0.2.0"

DEFAULT_UPDATER_RELEASES_API = "https://kevinblog.sytes.net/Code/api/v1/repos/Kevin/JiboUpdater/releases"

DEFAULT_RELEASES_API = "https://kevinblog.sytes.net/Code/api/v1/repos/Kevin/JiboOs/releases"


class Colors:
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def _no_color_if_not_tty() -> None:
    if not sys.stdout.isatty():
        for attr in dir(Colors):
            if attr.startswith("_"):
                continue
            setattr(Colors, attr, "")


def print_info(msg: str) -> None:
    print(f"{Colors.CYAN}ℹ {msg}{Colors.RESET}")


def print_success(msg: str) -> None:
    print(f"{Colors.GREEN}✓ {msg}{Colors.RESET}")


def print_warning(msg: str) -> None:
    print(f"{Colors.YELLOW}⚠ {msg}{Colors.RESET}")


def print_error(msg: str) -> None:
    print(f"{Colors.RED}✗ {msg}{Colors.RESET}")


def prompt_yes_no(question: str, default: bool = False) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        ans = input(f"{question} {suffix} ").strip().lower()
        if not ans:
            return default
        if ans in {"y", "yes"}:
            return True
        if ans in {"n", "no"}:
            return False
        print("Please answer y or n.")


@dataclass(frozen=True)
class Release:
    tag_name: str
    name: str
    prerelease: bool
    tarball_url: str
    zipball_url: str


def http_get_json(url: str, timeout: int = 20) -> object:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "JiboUpdater/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
    return json.loads(data.decode("utf-8", errors="replace"))


def check_updater_version(releases_api: str, current_version: str) -> tuple[Optional[str], bool]:
    """Return (latest_tag, is_newer) comparing semantic-ish tags.

    If the check fails, returns (None, False).
    """
    try:
        raw = http_get_json(releases_api)
    except Exception:
        return None, False

    if not isinstance(raw, list) or not raw:
        return None, False

    tags: list[str] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        tags.append(str(item.get("tag_name", "")))

    tags = [t for t in tags if t]
    if not tags:
        return None, False

    tags.sort(key=_version_tuple, reverse=True)
    latest = tags[0]
    try:
        is_newer = _version_tuple(latest) > _version_tuple(current_version)
    except Exception:
        is_newer = False
    return latest, is_newer


class _Spinner:
    def __init__(self, message: str = ""):
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.message = message

    def start(self):
        def _spin():
            chars = "|/-\\"
            i = 0
            while not self._stop.is_set():
                sys.stdout.write(f"\r{self.message} {chars[i % len(chars)]}")
                sys.stdout.flush()
                i += 1
                time.sleep(0.12)
            sys.stdout.write("\r" + " " * (len(self.message) + 4) + "\r")
            sys.stdout.flush()

        self._thread = threading.Thread(target=_spin, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1)


_VERSION_RE = re.compile(r"^v?(\d+)(?:\.(\d+))?(?:\.(\d+))?")


def _version_tuple(tag: str) -> tuple[int, int, int]:
    m = _VERSION_RE.match(tag.strip())
    if not m:
        return (0, 0, 0)
    major = int(m.group(1) or 0)
    minor = int(m.group(2) or 0)
    patch = int(m.group(3) or 0)
    return (major, minor, patch)


def get_latest_release(releases_api: str, allow_prerelease: bool) -> Release:
    raw = http_get_json(releases_api)
    if not isinstance(raw, list) or not raw:
        raise RuntimeError(f"Unexpected releases API response from {releases_api}")

    releases: list[Release] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        prerelease = bool(item.get("prerelease", False))
        if prerelease and not allow_prerelease:
            continue
        releases.append(
            Release(
                tag_name=str(item.get("tag_name", "")),
                name=str(item.get("name", "")),
                prerelease=prerelease,
                tarball_url=str(item.get("tarball_url", "")),
                zipball_url=str(item.get("zipball_url", "")),
            )
        )

    if not releases:
        raise RuntimeError("No releases found (after prerelease filtering)")

    releases.sort(key=lambda r: _version_tuple(r.tag_name), reverse=True)
    return releases[0]


def normalize_download_url(download_url: str, base_url: str) -> str:
    """Force downloads to use the same scheme/host as the API base.

    Some Gitea instances can be configured with a different ROOT_URL than the
    externally reachable hostname, which can leak into tarball_url/zipball_url.
    """

    if not download_url:
        return download_url

    base = urllib.parse.urlparse(base_url)
    dl = urllib.parse.urlparse(download_url)

    if dl.scheme == base.scheme and dl.netloc == base.netloc:
        return download_url

    return urllib.parse.urlunparse(
        (base.scheme, base.netloc, dl.path, dl.params, dl.query, dl.fragment)
    )


def _ensure_dirs() -> None:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    UPDATES_DIR.mkdir(parents=True, exist_ok=True)


def _download(url: str, dest: Path, *, force: bool = False) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and not force:
        print_info(f"Using cached download: {dest}")
        return

    print_info(f"Downloading: {url}")
    tmp = dest.with_suffix(dest.suffix + ".part")

    last_err: Optional[BaseException] = None
    for attempt in range(1, 4):
        try:
            if tmp.exists():
                tmp.unlink(missing_ok=True)

            with urllib.request.urlopen(url, timeout=180) as resp:
                total = resp.headers.get("Content-Length")
                total_int = int(total) if total and total.isdigit() else None
                downloaded = 0
                chunk_size = 1024 * 256
                with open(tmp, "wb") as f:
                    while True:
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_int:
                            pct = downloaded * 100.0 / total_int
                            sys.stdout.write(
                                f"\r  {downloaded/1e6:.1f}MB / {total_int/1e6:.1f}MB ({pct:.1f}%)"
                            )
                            sys.stdout.flush()

            if total_int:
                sys.stdout.write("\n")
            tmp.replace(dest)
            print_success(f"Downloaded to {dest}")
            return

        except Exception as e:
            last_err = e
            wait = 2**attempt
            print_warning(f"Download attempt {attempt}/3 failed: {e}. Retrying in {wait}s...")
            time.sleep(wait)

    if tmp.exists():
        tmp.unlink(missing_ok=True)
    raise RuntimeError(f"Download failed after 3 attempts: {last_err}")


def _extract(archive: Path, extract_dir: Path, *, force: bool = False) -> Path:
    if extract_dir.exists() and force:
        shutil.rmtree(extract_dir)

    if extract_dir.exists():
        print_info(f"Using cached extraction: {extract_dir}")
        return extract_dir

    extract_dir.mkdir(parents=True, exist_ok=True)
    print_info(f"Extracting {archive.name} ...")

    def _is_within(base: Path, target: Path) -> bool:
        try:
            target.resolve().relative_to(base.resolve())
            return True
        except Exception:
            return False

    if archive.suffixes[-2:] == [".tar", ".gz"] or archive.suffix == ".tgz":
        with tarfile.open(archive, "r:gz") as tf:
            for member in tf.getmembers():
                member_path = extract_dir / member.name
                if not _is_within(extract_dir, member_path):
                    raise RuntimeError(f"Unsafe path in tar archive: {member.name}")
            try:
                tf.extractall(extract_dir, filter="data")
            except TypeError:
                tf.extractall(extract_dir)
    elif archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as zf:
            for member in zf.infolist():
                member_path = extract_dir / member.filename
                if not _is_within(extract_dir, member_path):
                    raise RuntimeError(f"Unsafe path in zip archive: {member.filename}")
            zf.extractall(extract_dir)
    else:
        raise RuntimeError(f"Unsupported archive type: {archive}")

    print_success(f"Extracted to {extract_dir}")
    return extract_dir


def _iter_build_candidates(root: Path) -> Iterable[Path]:
    for path in root.rglob("build"):
        if path.is_dir():
            yield path


def _score_build_dir(path: Path) -> int:
    score = 0
    for name, weight in (("etc", 5), ("opt", 5), ("var", 2), ("usr", 2), ("lib", 1), ("bin", 1)):
        if (path / name).exists():
            score += weight
    parts = {p.lower() for p in path.parts}
    if any(re.fullmatch(r"v\d+(?:\.\d+)*", p, flags=re.IGNORECASE) for p in parts):
        score += 2
    return score


def find_build_dir(extract_root: Path, explicit: Optional[str]) -> Path:
    if explicit:
        p = (extract_root / explicit).resolve()
        if not p.exists() or not p.is_dir():
            raise RuntimeError(f"--build-path not found: {p}")
        return p

    candidates = list(_iter_build_candidates(extract_root))
    if not candidates:
        raise RuntimeError(
            "Could not find a 'build' folder in the extracted archive. "
            "Use --build-path to point to it (relative to the extracted root)."
        )

    candidates.sort(key=_score_build_dir, reverse=True)
    best = candidates[0]

    if _score_build_dir(best) == 0 and len(candidates) > 1:
        print_warning("Found build folders, but none look like a rootfs overlay (no etc/opt).")

    print_info(f"Using build folder: {best}")
    return best


def load_state(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text("utf-8"))
    except Exception:
        return {}


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def ssh_connect(host: str, user: str, password: str, timeout: int) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=host,
        username=user,
        password=password,
        look_for_keys=False,
        allow_agent=False,
        timeout=timeout,
        banner_timeout=timeout,
        auth_timeout=timeout,
    )
    return client


def ssh_exec(client: paramiko.SSHClient, command: str, timeout: int = 60) -> tuple[int, str, str]:
    stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    _ = stdin
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    return code, out, err


def ensure_remote_dir(sftp: paramiko.SFTPClient, remote_dir: str) -> None:
    parts = [p for p in remote_dir.split("/") if p]
    cur = "/"
    for part in parts:
        cur = posixpath.join(cur, part)
        try:
            sftp.stat(cur)
        except IOError:
            sftp.mkdir(cur)


def upload_tree(
    sftp: paramiko.SFTPClient,
    local_root: Path,
    remote_root: str = "/",
    *,
    dry_run: bool = False,
) -> None:
    local_root = local_root.resolve()

    paths = sorted(local_root.rglob("*"))
    total = len(paths)
    sent = 0

    for p in paths:
        rel = p.relative_to(local_root).as_posix()
        remote_path = posixpath.join(remote_root, rel)

        if p.is_dir():
            if dry_run:
                continue
            ensure_remote_dir(sftp, remote_path)
            try:
                sftp.chmod(remote_path, 0o777)
            except Exception:
                pass
            continue

        if p.is_symlink():
            target = os.readlink(p)
            if dry_run:
                sent += 1
                continue
            ensure_remote_dir(sftp, posixpath.dirname(remote_path))
            try:
                try:
                    sftp.remove(remote_path)
                except IOError:
                    pass
                sftp.symlink(target, remote_path)
            except Exception:
                real_path = p.resolve()
                sftp.put(str(real_path), remote_path)
            try:
                sftp.chmod(remote_path, 0o777)
            except Exception:
                pass
            sent += 1
            if sent % 200 == 0:
                print_info(f"Uploaded {sent}/{total} entries...")
            continue

        if p.is_file():
            if dry_run:
                sent += 1
                continue

            ensure_remote_dir(sftp, posixpath.dirname(remote_path))
            sftp.put(str(p), remote_path)
            try:
                sftp.chmod(remote_path, 0o777)
            except Exception:
                pass

            sent += 1
            if sent % 200 == 0:
                print_info(f"Uploaded {sent}/{total} entries...")

    print_success(f"Upload complete ({sent} files/links)")


def set_mode_json_to_normal(sftp: paramiko.SFTPClient) -> None:
    remote = "/var/jibo/mode.json"
    try:
        with sftp.open(remote, "r") as f:
            content = f.read().decode("utf-8", errors="replace")
    except IOError as e:
        raise RuntimeError(f"Failed to read {remote}: {e}")

    new_content: str
    try:
        data = json.loads(content)
        if not isinstance(data, dict):
            raise ValueError("mode.json is not a JSON object")
        data["mode"] = "normal"
        new_content = json.dumps(data, separators=(",", ": ")) + "\n"
    except Exception:
        new_content = re.sub(r'("mode"\s*:\s*")([^"]+)(")', r'\1normal\3', content)
        if new_content == content:
            new_content = '{"mode": "normal"}\n'

    with sftp.open(remote, "w") as f:
        f.write(new_content.encode("utf-8"))


def load_distributors_file(path: Path) -> dict:
    try:
        raw = json.loads(path.read_text("utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def measure_host_latency(url: str, timeout: int = 5) -> float:
    start = time.time()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "JiboUpdater/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp.read(512)
        return time.time() - start
    except Exception:
        return float("inf")


def get_releases_from_host(api_url: str) -> list[Release]:
    try:
        raw = http_get_json(api_url)
    except Exception:
        return []
    releases: list[Release] = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            releases.append(
                Release(
                    tag_name=str(item.get("tag_name", "")),
                    name=str(item.get("name", "")),
                    prerelease=bool(item.get("prerelease", False)),
                    tarball_url=str(item.get("tarball_url", "")),
                    zipball_url=str(item.get("zipball_url", "")),
                )
            )
    return releases


def list_local_archives() -> list[Release]:
    dl = UPDATES_DIR / "downloads"
    found: list[Release] = []
    if not dl.exists():
        return found
    for p in dl.iterdir():
        if not p.is_file():
            continue
        name = p.name
        if name.endswith((".tar.gz", ".tgz", ".zip")):
            tag = name.rsplit(".", 2)[0]
            found.append(Release(tag_name=tag, name=tag, prerelease=False, tarball_url=str(p), zipball_url=""))
    return found


def robots_config_path() -> Path:
    return WORK_DIR / "robots.json"


def load_robots() -> dict:
    p = robots_config_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text("utf-8"))
    except Exception:
        return {}


def save_robots(data: dict) -> None:
    p = robots_config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def fetch_robot_identity(host: str, user: str, password: str, timeout: int = 10) -> Optional[str]:
    try:
        client = ssh_connect(host, user, password, timeout=timeout)
        try:
            sftp = client.open_sftp()
            try:
                with sftp.open("/var/jibo/identity.json", "r") as f:
                    content = f.read().decode("utf-8", errors="replace")
                    data = json.loads(content)
                    name = None
                    if isinstance(data, dict):
                        name = data.get("name") or data.get("robot_name")
                        if isinstance(name, str):
                            return name
            finally:
                sftp.close()
        finally:
            client.close()
    except Exception:
        return None
    return None


def prompt_select_release_and_host(distributors_file: Path) -> tuple[Optional[Release], Optional[str], str]:
    d = load_distributors_file(distributors_file)
    hosts = d.get("UpdateHosts") or d.get("OfficialHosts") or []
    hosts = [h for h in hosts if isinstance(h, str)]

    print_info("Checking hosts for latency and available releases...")
    host_infos = []
    for h in hosts:
        lat = measure_host_latency(h)
        releases = get_releases_from_host(h)
        host_infos.append((h, lat, releases))

    local_releases = list_local_archives()
    if local_releases:
        host_infos.append(("local", 0.0, local_releases))

    print("Hosts (lower latency preferred):")
    host_infos.sort(key=lambda t: (t[1] if isinstance(t[1], float) else float("inf")))
    for idx, (h, lat, rels) in enumerate(host_infos, start=1):
        label = f"{h} ({'local' if h=='local' else f'{lat:.2f}s'}) - {len(rels)} releases"
        print(f"{idx}) {label}")

    chosen_host_idx = None
    while chosen_host_idx is None:
        ans = input("Choose host number to browse releases (or q to cancel): ").strip()
        if ans.lower() in {"q", "quit", "exit"}:
            return None, None, ""
        if not ans.isdigit():
            print("Enter a number.")
            continue
        i = int(ans)
        if i < 1 or i > len(host_infos):
            print("Out of range")
            continue
        chosen_host_idx = i - 1

    host, lat, releases = host_infos[chosen_host_idx]
    if not releases:
        print_warning("No releases found for that host.")
        return None, host, "remote"

    releases.sort(key=lambda r: _version_tuple(r.tag_name), reverse=True)
    for idx, r in enumerate(releases, start=1):
        pre = " [prerelease]" if r.prerelease else ""
        print(f"{idx}) {r.tag_name}{pre} - {r.name}")
    ans = input("Choose release number (or 'l' to list release notes, number to pick, q to cancel): ").strip()
    if ans.lower() == "q":
        return None, host, ""
    if ans.lower() == "l":
        sub = input("Release number to show notes: ").strip()
        if sub.isdigit():
            si = int(sub) - 1
            if 0 <= si < len(releases):
                print(releases[si].name)
                print(releases[si].tag_name)
        return None, host, ""
    if not ans.isdigit():
        return None, host, ""
    ri = int(ans) - 1
    if ri < 0 or ri >= len(releases):
        return None, host, ""
    chosen = releases[ri]
    source = "local" if host == "local" else "remote"
    return chosen, host, source


def main() -> int:
    _no_color_if_not_tty()

    parser = argparse.ArgumentParser(description="Update a modded Jibo with the latest JiboOs release")
    parser.add_argument("--ip", "--host", dest="host", required=True, help="Jibo IP/hostname")
    parser.add_argument("--user", default="root", help="SSH username (default: root)")
    parser.add_argument("--password", default="jibo", help="SSH password (default: jibo)")
    parser.add_argument("--releases-api", default=DEFAULT_RELEASES_API, help="Gitea releases API URL")
    parser.add_argument("--distributors", type=Path, default=Path("Distributors.json"), help="Path to Distributors.json to check multiple hosts")
    parser.add_argument("--tui", action="store_true", help="Run an interactive text UI to pick host/release")
    parser.add_argument("--updater-releases-api", default=DEFAULT_UPDATER_RELEASES_API, help="Releases API to check for updater updates")

    parser.add_argument("--stable", action="store_true", help="Ignore prereleases")
    parser.add_argument("--tag", help="Install a specific tag (e.g. v3.3.0) instead of latest")

    parser.add_argument("--build-path", help="Path to build folder inside extracted tree (relative)")

    parser.add_argument("--state-file", type=Path, default=STATE_FILE_DEFAULT, help="Where to store last applied version")
    parser.add_argument("--force", action="store_true", help="Re-download and re-install even if version matches")
    parser.add_argument("--yes", action="store_true", help="Don’t prompt for confirmation")
    parser.add_argument("--dry-run", action="store_true", help="Download/extract + connect, but don’t write files")

    parser.add_argument(
        "--return-normal",
        action="store_true",
        help="After update, set /var/jibo/mode.json mode back to normal (no prompt)",
    )
    parser.add_argument(
        "--no-return-normal",
        action="store_true",
        help="After update, do not ask to return to normal mode",
    )

    parser.add_argument("--ssh-timeout", type=int, default=15, help="SSH connect timeout seconds")

    args = parser.parse_args()

    _ensure_dirs()

    logp = WORK_DIR / "updater.log"
    logp.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s",
        handlers=[logging.FileHandler(logp, encoding="utf-8"), logging.StreamHandler(sys.stdout)],
    )
    logging.info("jibo_updater starting, version %s", __version__)

    spinner = _Spinner("Checking updater version...")
    spinner.start()
    try:
        latest_tag, is_newer = check_updater_version(args.updater_releases_api, __version__)
    finally:
        spinner.stop()

    if latest_tag:
        if is_newer:
            msg = f"Updater update available: {latest_tag} (current {__version__})"
            print_warning(msg)
            logging.info(msg)
        else:
            msg = f"Updater is up-to-date ({__version__})"
            print_info(msg)
            logging.info(msg)
    else:
        logging.info("Updater version check failed or no releases found")

    allow_prerelease = not args.stable

    print_info("Checking latest release...")
    chosen_remote_source: Optional[str] = None
    chosen_source_type = "remote"
    if args.tui:
        rel_choice, host_choice, source = prompt_select_release_and_host(args.distributors)
        if rel_choice is None:
            print_info("No release selected; aborting.")
            return 2
        release = rel_choice
        chosen_remote_source = host_choice
        chosen_source_type = source
    elif args.tag:
        raw = http_get_json(args.releases_api)
        if not isinstance(raw, list):
            raise RuntimeError("Unexpected releases API response")
        chosen: Optional[Release] = None
        for item in raw:
            if not isinstance(item, dict):
                continue
            if str(item.get("tag_name", "")) == args.tag:
                chosen = Release(
                    tag_name=str(item.get("tag_name", "")),
                    name=str(item.get("name", "")),
                    prerelease=bool(item.get("prerelease", False)),
                    tarball_url=str(item.get("tarball_url", "")),
                    zipball_url=str(item.get("zipball_url", "")),
                )
                break
        if not chosen:
            raise RuntimeError(f"Tag not found in releases: {args.tag}")
        release = chosen
    else:
        release = get_latest_release(args.releases_api, allow_prerelease=allow_prerelease)

    if not release.tag_name or not release.tarball_url:
        raise RuntimeError("Release JSON missing tag_name or tarball_url")

    state = load_state(args.state_file)
    last = str(state.get(args.host, "")) if isinstance(state, dict) else ""

    print_info(f"Latest: {release.tag_name} ({'prerelease' if release.prerelease else 'stable'})")
    if last:
        print_info(f"Last applied (from state): {last}")

    if (not args.force) and last and last == release.tag_name:
        print_success("Already at latest version (per local state). Use --force to reinstall.")
        return 0

    if not args.yes:
        if not prompt_yes_no(
            f"This will upload the release build overlay into / on {args.host} and overwrite files. Continue?",
            default=False,
        ):
            print_info("Aborted.")
            return 2

    archive_name = f"{release.tag_name}.tar.gz"
    archive_path = UPDATES_DIR / "downloads" / archive_name
    extract_dir = UPDATES_DIR / "extracted" / release.tag_name

    if chosen_remote_source and chosen_source_type == "remote":
        tarball_url = normalize_download_url(release.tarball_url, chosen_remote_source)
    elif chosen_source_type == "local":
        tarball_url = release.tarball_url
    else:
        tarball_url = normalize_download_url(release.tarball_url, args.releases_api)

    try:
        if isinstance(tarball_url, str) and Path(tarball_url).exists():
            archive_path = Path(tarball_url)
            print_info(f"Using local archive: {archive_path}")
        else:
            _download(tarball_url, archive_path, force=args.force)
    except urllib.error.URLError as e:
        raise RuntimeError(f"Download failed: {e}")

    _extract(archive_path, extract_dir, force=args.force)

    children = [p for p in extract_dir.iterdir() if p.is_dir()]
    search_root = children[0] if len(children) == 1 else extract_dir

    build_dir = find_build_dir(search_root, args.build_path)

    print_info(f"Connecting to {args.user}@{args.host} ...")
    client = ssh_connect(args.host, args.user, args.password, timeout=args.ssh_timeout)
    try:
        code, out, err = ssh_exec(client, "sh -c 'touch /.jibo_rw_test 2>/dev/null && rm /.jibo_rw_test 2>/dev/null && echo WRITABLE || echo READONLY'")
        if "WRITABLE" in out:
            print_info("Root FS already writable")
        else:
            print_info("Remounting / as read-write...")
            code, out, err = ssh_exec(client, "sh -c 'mount -o remount,rw /'", timeout=60)
            if code != 0:
                print_warning(f"Remount command returned {code}. stderr: {err.strip()}")
            code, out, err = ssh_exec(client, "sh -c 'touch /.jibo_rw_test 2>/dev/null && rm /.jibo_rw_test 2>/dev/null && echo WRITABLE || echo READONLY'")
            if "WRITABLE" not in out:
                raise RuntimeError("Failed to remount / as writable (still READONLY)")
            print_success("/ remounted writable")

        if args.dry_run:
            print_success("Dry-run: skipping upload")
        else:
            print_info("Starting SFTP upload (this can take a while)...")
            sftp = client.open_sftp()
            try:
                upload_tree(sftp, build_dir, remote_root="/", dry_run=False)
            finally:
                sftp.close()

        do_return = False
        if args.return_normal:
            do_return = True
        elif args.no_return_normal:
            do_return = False
        elif args.yes:
            do_return = False
        else:
            do_return = prompt_yes_no("Return Jibo to normal mode (mode.json: int-developer -> normal)?", default=False)

        if do_return:
            if args.dry_run:
                print_info("Dry-run: skipping mode.json change")
            else:
                sftp = client.open_sftp()
                try:
                    set_mode_json_to_normal(sftp)
                    print_success("Updated /var/jibo/mode.json to normal")
                finally:
                    sftp.close()

        if not args.dry_run:
            if isinstance(state, dict):
                state[args.host] = release.tag_name
                save_state(args.state_file, state)

        print_success(f"Update finished ({release.tag_name})")
        return 0

    finally:
        client.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrupted.")
        raise SystemExit(130)
    except Exception as e:
        print_error(str(e))
        raise SystemExit(1)
