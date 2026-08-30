"""Inspect a failed firewall ext4 walk using only its cached sampled pages."""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

from ext4_path import Ext4PathError, Ext4PathReader


PAGE_SIZE = 64 * 1024


class CachedPageReader:
    def __init__(self, cache: Path, slot: str):
        self.cache = cache
        self.slot = slot

    def read_at(self, offset: int, length: int) -> bytes:
        output = bytearray()
        cursor = offset
        end = offset + length
        while cursor < end:
            page_start = cursor // PAGE_SIZE * PAGE_SIZE
            path = self.cache / f"{self.slot}.{page_start:08x}.bin"
            if not path.is_file():
                raise Ext4PathError(f"required cached page is missing: {path}")
            page = path.read_bytes()
            within = cursor - page_start
            take = min(end - cursor, len(page) - within)
            if take <= 0:
                raise Ext4PathError(f"cached page is too short: {path}")
            output.extend(page[within:within + take])
            cursor += take
        return bytes(output)


def inode_location(filesystem: Ext4PathReader, number: int) -> tuple[int, int, int]:
    index = number - 1
    group, group_index = divmod(index, filesystem.inodes_per_group)
    descriptor = filesystem._group_descriptor(group)
    inode_table = struct.unpack_from("<I", descriptor, 8)[0]
    offset = inode_table * filesystem.block_size + group_index * filesystem.inode_size
    return group, inode_table, offset


def inode_kind(mode: int) -> str:
    return {
        0x4000: "directory",
        0x8000: "regular file",
        0xA000: "symbolic link",
    }.get(mode & 0xF000, "unknown/unallocated")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, default=Path("Exploits/dump/firewall_sample_cache"))
    parser.add_argument("--slot", choices=("rootfsA", "rootfsB"), default="rootfsA")
    args = parser.parse_args()

    reader = CachedPageReader(args.cache.resolve(), args.slot)
    try:
        superblock = reader.read_at(1024, 1024)
        block_size = 1024 << struct.unpack_from("<I", superblock, 24)[0]
        blocks_count = struct.unpack_from("<I", superblock, 4)[0]
        filesystem = Ext4PathReader(reader.read_at, blocks_count * block_size)
        print(f"slot={args.slot}")
        print(f"uuid={filesystem.filesystem_uuid}")
        print(f"block_size={filesystem.block_size}")
        print(f"blocks_count={filesystem.blocks_count}")
        print(f"blocks_per_group={filesystem.blocks_per_group}")
        print(f"inodes_per_group={filesystem.inodes_per_group}")
        print(f"inode_size={filesystem.inode_size}")
        print(f"descriptor_size={filesystem.descriptor_size}")
        print(f"feature_compat=0x{struct.unpack_from('<I', superblock, 92)[0]:08x}")
        print(f"feature_incompat=0x{filesystem.feature_incompat:08x}")
        print(f"feature_ro_compat=0x{struct.unpack_from('<I', superblock, 100)[0]:08x}")
        print(f"raw_descriptor_size={struct.unpack_from('<H', superblock, 254)[0]}")
        print(f"first_meta_bg={struct.unpack_from('<I', superblock, 260)[0]}")

        current = filesystem.inode(2)
        resolved = "/"
        for part in ("etc", "init.d", "S21firewall"):
            group, table, offset = inode_location(filesystem, current.number)
            print(
                f"path={resolved} inode={current.number} mode=0x{current.mode:04x} "
                f"kind={inode_kind(current.mode)} group={group} "
                f"inode_table_block={table} inode_byte_offset=0x{offset:x}"
            )
            entries = [(name, number) for name, number in filesystem.directory_entries(current) if name == part]
            print(f"lookup={part!r} matches={entries}")
            if len(entries) != 1:
                return 2
            current = filesystem.inode(entries[0][1])
            resolved = resolved.rstrip("/") + "/" + part

        group, table, offset = inode_location(filesystem, current.number)
        print(
            f"path={resolved} inode={current.number} mode=0x{current.mode:04x} "
            f"kind={inode_kind(current.mode)} group={group} "
            f"inode_table_block={table} inode_byte_offset=0x{offset:x}"
        )
        return 0
    except (OSError, ValueError, Ext4PathError) as error:
        print(f"diagnostic stopped: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
