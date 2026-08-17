"""Fail-closed detection and byte-preserving patch helpers for S21firewall.

The functions in this module operate on a root filesystem partition image.
They deliberately require the known Jibo firewall control-flow context instead
of matching the common ``jibo-getmode`` assignment by itself.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterable, Tuple


SECTOR_SIZE = 512
EXT_SUPERBLOCK_OFFSET = 1024
EXT_MAGIC_OFFSET = EXT_SUPERBLOCK_OFFSET + 56
EXT_MAGIC = b"\x53\xef"

ASSIGNMENT_ORIGINAL = b'    my_mode=$(/usr/bin/jibo-getmode)\n'
ASSIGNMENT_PATCHED = b'    my_mode="int-developer"         \n'

if len(ASSIGNMENT_ORIGINAL) != len(ASSIGNMENT_PATCHED):  # pragma: no cover
    raise AssertionError("firewall patch must preserve the assignment line length")

PROFILE_PATH = Path(__file__).resolve().parent / "profiles" / "S21firewall.v1"
SIGNATURE_ORIGINAL = PROFILE_PATH.read_bytes()
KNOWN_PROFILE_SHA256 = "cb34db864fee2e6725fa09a293c60fff003b87348a16553419926ee7cc1a1cc8"
if hashlib.sha256(SIGNATURE_ORIGINAL).hexdigest() != KNOWN_PROFILE_SHA256:  # pragma: no cover
    raise AssertionError("S21firewall profile bytes were altered or line-ending translated")
if SIGNATURE_ORIGINAL.count(ASSIGNMENT_ORIGINAL) != 1:  # pragma: no cover
    raise AssertionError("firewall profile must contain exactly one original assignment")
ASSIGNMENT_OFFSET_IN_SIGNATURE = SIGNATURE_ORIGINAL.index(ASSIGNMENT_ORIGINAL)
SIGNATURE_PATCHED = (
    SIGNATURE_ORIGINAL[:ASSIGNMENT_OFFSET_IN_SIGNATURE]
    + ASSIGNMENT_PATCHED
    + SIGNATURE_ORIGINAL[ASSIGNMENT_OFFSET_IN_SIGNATURE + len(ASSIGNMENT_ORIGINAL):]
)
FILE_SHA256_ORIGINAL = hashlib.sha256(SIGNATURE_ORIGINAL).hexdigest()
FILE_SHA256_PATCHED = hashlib.sha256(SIGNATURE_PATCHED).hexdigest()


class FirewallPatchError(RuntimeError):
    """Raised when an image cannot be proven safe to patch."""


@dataclass(frozen=True)
class FirewallImageMatch:
    image_path: Path
    image_size: int
    image_sha256: str
    firewall_file_sha256: str
    state: str
    signature_offset: int
    assignment_offset: int


@dataclass(frozen=True)
class FirewallFileMatch:
    state: str
    file_size: int
    file_sha256: str
    assignment_offset: int


@dataclass(frozen=True)
class SectorPatch:
    start_sector: int
    sector_count: int
    before: bytes
    after: bytes
    assignment_offset: int

    @property
    def before_sha256(self) -> str:
        return hashlib.sha256(self.before).hexdigest()

    @property
    def after_sha256(self) -> str:
        return hashlib.sha256(self.after).hexdigest()


def inspect_firewall_file(data: bytes) -> FirewallFileMatch:
    """Validate a path-resolved S21firewall file against the full profile."""
    if data == SIGNATURE_ORIGINAL:
        state = "original"
        digest = FILE_SHA256_ORIGINAL
    elif data == SIGNATURE_PATCHED:
        state = "patched"
        digest = FILE_SHA256_PATCHED
    else:
        raise FirewallPatchError(
            "path-resolved S21firewall does not match the known original or patched profile"
        )
    return FirewallFileMatch(
        state=state,
        file_size=len(data),
        file_sha256=digest,
        assignment_offset=ASSIGNMENT_OFFSET_IN_SIGNATURE,
    )


def build_sector_patch_from_reader(
    match: FirewallFileMatch,
    physical_assignment_offset: int,
    read_at,
    restore: bool = False,
) -> SectorPatch:
    """Build a minimal patch using a partition-relative byte reader."""
    expected = ASSIGNMENT_PATCHED if match.state == "patched" else ASSIGNMENT_ORIGINAL
    replacement = ASSIGNMENT_ORIGINAL if restore else ASSIGNMENT_PATCHED
    start_byte = (physical_assignment_offset // SECTOR_SIZE) * SECTOR_SIZE
    end_byte = physical_assignment_offset + len(expected)
    end_byte = ((end_byte + SECTOR_SIZE - 1) // SECTOR_SIZE) * SECTOR_SIZE
    before = read_at(start_byte, end_byte - start_byte)
    if len(before) != end_byte - start_byte:
        raise FirewallPatchError("could not read the complete patch sector range")
    relative_offset = physical_assignment_offset - start_byte
    if before[relative_offset:relative_offset + len(expected)] != expected:
        raise FirewallPatchError("physical assignment bytes differ from the validated file")
    after = bytearray(before)
    after[relative_offset:relative_offset + len(expected)] = replacement
    return SectorPatch(
        start_sector=start_byte // SECTOR_SIZE,
        sector_count=len(after) // SECTOR_SIZE,
        before=before,
        after=bytes(after),
        assignment_offset=physical_assignment_offset,
    )


def preserve_recovery_payload(path: Path, original_payload: bytes) -> bool:
    """Create an immutable original-sector recovery file.

    Return ``True`` when the file is created and ``False`` when an identical
    recovery file already exists. A conflicting file is never overwritten.
    """
    path = Path(path)
    if not original_payload or len(original_payload) % SECTOR_SIZE:
        raise FirewallPatchError("recovery payload must be non-empty and sector aligned")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(original_payload)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        if path.read_bytes() != original_payload:
            raise FirewallPatchError(
                f"existing recovery payload differs; refusing to overwrite: {path}"
            )
        return False
    return True


def _find_all(buffer: bytes, needle: bytes) -> Iterable[int]:
    start = 0
    while True:
        found = buffer.find(needle, start)
        if found < 0:
            return
        yield found
        start = found + 1


def _scan_stream(
    stream: BinaryIO,
    patterns: Tuple[bytes, ...],
    chunk_size: int = 4 * 1024 * 1024,
) -> Tuple[str, Tuple[Tuple[int, ...], ...]]:
    """Hash a stream and return absolute offsets for every requested pattern."""
    if not patterns or any(not pattern for pattern in patterns):
        raise ValueError("scan patterns must be non-empty")

    overlap_size = max(len(pattern) for pattern in patterns) - 1
    overlap = b""
    consumed = 0
    digest = hashlib.sha256()
    matches = [[] for _ in patterns]

    while True:
        chunk = stream.read(chunk_size)
        if not chunk:
            break
        digest.update(chunk)
        window = overlap + chunk
        window_offset = consumed - len(overlap)
        for pattern_index, pattern in enumerate(patterns):
            for relative_offset in _find_all(window, pattern):
                absolute_offset = window_offset + relative_offset
                # A match fully contained in the prior overlap was reported in
                # the previous iteration. Cross-boundary matches are retained.
                if absolute_offset + len(pattern) > consumed:
                    matches[pattern_index].append(absolute_offset)
        consumed += len(chunk)
        overlap = window[-overlap_size:] if overlap_size else b""

    return digest.hexdigest(), tuple(tuple(offsets) for offsets in matches)


def _validate_ext_image(stream: BinaryIO, image_size: int) -> None:
    if image_size <= EXT_MAGIC_OFFSET + len(EXT_MAGIC):
        raise FirewallPatchError("rootfs image is too small to contain an ext superblock")
    if image_size % SECTOR_SIZE:
        raise FirewallPatchError("rootfs image size is not sector aligned")
    stream.seek(EXT_MAGIC_OFFSET)
    if stream.read(len(EXT_MAGIC)) != EXT_MAGIC:
        raise FirewallPatchError("rootfs image does not have the expected ext filesystem magic")
    stream.seek(0)


def inspect_firewall_image(image_path: Path) -> FirewallImageMatch:
    """Locate one known S21firewall instance or fail without guessing.

    Exactly one original or patched contextual signature must exist in the
    entire rootfs partition image. This rejects unrelated init scripts that
    contain the same mode assignment and rejects ambiguous/stale copies.
    """
    image_path = Path(image_path)
    image_size = image_path.stat().st_size
    with image_path.open("rb") as stream:
        _validate_ext_image(stream, image_size)
        image_sha256, (original_offsets, patched_offsets) = _scan_stream(
            stream, (SIGNATURE_ORIGINAL, SIGNATURE_PATCHED)
        )

    candidates = [
        *(('original', offset) for offset in original_offsets),
        *(('patched', offset) for offset in patched_offsets),
    ]
    if len(candidates) != 1:
        raise FirewallPatchError(
            "expected exactly one known S21firewall signature, "
            f"found original={len(original_offsets)}, patched={len(patched_offsets)}"
        )

    state, signature_offset = candidates[0]
    return FirewallImageMatch(
        image_path=image_path,
        image_size=image_size,
        image_sha256=image_sha256,
        firewall_file_sha256=(
            FILE_SHA256_ORIGINAL if state == "original" else FILE_SHA256_PATCHED
        ),
        state=state,
        signature_offset=signature_offset,
        assignment_offset=signature_offset + ASSIGNMENT_OFFSET_IN_SIGNATURE,
    )


def build_sector_patch(match: FirewallImageMatch, restore: bool = False) -> SectorPatch:
    """Build the smallest sector-aligned payload for a validated match."""
    expected = ASSIGNMENT_PATCHED if match.state == "patched" else ASSIGNMENT_ORIGINAL
    replacement = ASSIGNMENT_ORIGINAL if restore else ASSIGNMENT_PATCHED

    start_byte = (match.assignment_offset // SECTOR_SIZE) * SECTOR_SIZE
    end_byte = match.assignment_offset + len(expected)
    end_byte = ((end_byte + SECTOR_SIZE - 1) // SECTOR_SIZE) * SECTOR_SIZE

    with match.image_path.open("rb") as stream:
        stream.seek(start_byte)
        before = stream.read(end_byte - start_byte)
    if len(before) != end_byte - start_byte:
        raise FirewallPatchError("could not read the complete patch sector range")

    relative_offset = match.assignment_offset - start_byte
    if before[relative_offset:relative_offset + len(expected)] != expected:
        raise FirewallPatchError("validated assignment changed before patch construction")

    after = bytearray(before)
    after[relative_offset:relative_offset + len(expected)] = replacement
    return SectorPatch(
        start_sector=start_byte // SECTOR_SIZE,
        sector_count=len(after) // SECTOR_SIZE,
        before=before,
        after=bytes(after),
        assignment_offset=match.assignment_offset,
    )


def apply_patch_to_image(image_path: Path, restore: bool = False) -> FirewallImageMatch:
    """Patch an image in place, primarily for offline tests and recovery."""
    match = inspect_firewall_image(image_path)
    desired_state = "original" if restore else "patched"
    if match.state == desired_state:
        return match

    patch = build_sector_patch(match, restore=restore)
    with Path(image_path).open("r+b") as stream:
        stream.seek(patch.start_sector * SECTOR_SIZE)
        stream.write(patch.after)
        stream.flush()

    verified = inspect_firewall_image(image_path)
    if verified.state != desired_state:
        raise FirewallPatchError(f"image verification did not reach {desired_state} state")
    if verified.image_size != match.image_size:
        raise FirewallPatchError("image length changed during patch")
    return verified
