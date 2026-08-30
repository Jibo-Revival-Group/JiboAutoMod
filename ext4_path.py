"""Minimal read-only ext4 path resolver over an arbitrary byte-range reader.

This intentionally implements only the features needed by the known Jibo
rootfs images. Unsupported layouts fail closed instead of guessing.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Callable, Iterator


EXT4_MAGIC = 0xEF53
EXT4_EXTENTS_FL = 0x00080000
EXT4_FEATURE_INCOMPAT_EXTENTS = 0x0040
EXT4_FEATURE_INCOMPAT_64BIT = 0x0080
EXTENT_MAGIC = 0xF30A


class Ext4PathError(RuntimeError):
    pass


@dataclass(frozen=True)
class Extent:
    logical_block: int
    block_count: int
    physical_block: int
    unwritten: bool = False


@dataclass(frozen=True)
class Inode:
    number: int
    mode: int
    size: int
    flags: int
    block_tree: bytes


class Ext4PathReader:
    """Resolve files by inode metadata using ``read_at(offset, length)``."""

    def __init__(self, read_at: Callable[[int, int], bytes], image_size: int):
        self._read_at = read_at
        self.image_size = image_size
        superblock = self._read_exact(1024, 1024)
        if struct.unpack_from("<H", superblock, 56)[0] != EXT4_MAGIC:
            raise Ext4PathError("ext filesystem magic is missing")
        self.block_size = 1024 << struct.unpack_from("<I", superblock, 24)[0]
        self.blocks_count = struct.unpack_from("<I", superblock, 4)[0]
        self.blocks_per_group = struct.unpack_from("<I", superblock, 32)[0]
        self.inodes_per_group = struct.unpack_from("<I", superblock, 40)[0]
        self.inode_size = struct.unpack_from("<H", superblock, 88)[0]
        self.feature_incompat = struct.unpack_from("<I", superblock, 96)[0]
        self.filesystem_uuid = superblock[104:120].hex()
        raw_desc_size = struct.unpack_from("<H", superblock, 254)[0]
        self.descriptor_size = max(32, raw_desc_size)

        if self.block_size not in (1024, 2048, 4096):
            raise Ext4PathError(f"unsupported ext block size: {self.block_size}")
        if self.inode_size < 128 or self.inode_size > self.block_size:
            raise Ext4PathError(f"unsupported inode size: {self.inode_size}")
        if not self.feature_incompat & EXT4_FEATURE_INCOMPAT_EXTENTS:
            raise Ext4PathError("filesystem does not use extents")
        if self.feature_incompat & EXT4_FEATURE_INCOMPAT_64BIT:
            raise Ext4PathError("64-bit ext block addressing is not supported")
        if self.blocks_count * self.block_size > image_size:
            raise Ext4PathError("filesystem block count exceeds partition bounds")

    def _read_exact(self, offset: int, length: int) -> bytes:
        if offset < 0 or length <= 0 or offset + length > self.image_size:
            raise Ext4PathError(f"read outside filesystem bounds: {offset}+{length}")
        data = self._read_at(offset, length)
        if len(data) != length:
            raise Ext4PathError(f"short filesystem read: expected {length}, got {len(data)}")
        return data

    def _read_block(self, block: int) -> bytes:
        if block <= 0 or block >= self.blocks_count:
            raise Ext4PathError(f"invalid ext block: {block}")
        return self._read_exact(block * self.block_size, self.block_size)

    def _group_descriptor(self, group: int) -> bytes:
        group_count = (self.blocks_count + self.blocks_per_group - 1) // self.blocks_per_group
        if group < 0 or group >= group_count:
            raise Ext4PathError(f"invalid inode group: {group}")
        table_block = 2 if self.block_size == 1024 else 1
        offset = table_block * self.block_size + group * self.descriptor_size
        return self._read_exact(offset, self.descriptor_size)

    def inode(self, number: int) -> Inode:
        if number < 1:
            raise Ext4PathError(f"invalid inode number: {number}")
        index = number - 1
        group, group_index = divmod(index, self.inodes_per_group)
        descriptor = self._group_descriptor(group)
        inode_table_block = struct.unpack_from("<I", descriptor, 8)[0]
        inode_offset = inode_table_block * self.block_size + group_index * self.inode_size
        raw = self._read_exact(inode_offset, self.inode_size)
        mode = struct.unpack_from("<H", raw, 0)[0]
        size_low = struct.unpack_from("<I", raw, 4)[0]
        size_high = struct.unpack_from("<I", raw, 108)[0] if mode & 0xF000 == 0x8000 else 0
        return Inode(
            number=number,
            mode=mode,
            size=size_low | (size_high << 32),
            flags=struct.unpack_from("<I", raw, 32)[0],
            block_tree=raw[40:100],
        )

    def _parse_extent_node(self, node: bytes, expected_depth: int | None = None) -> list[Extent]:
        if len(node) < 12:
            raise Ext4PathError("truncated extent node")
        magic, entries, maximum, depth = struct.unpack_from("<HHHH", node, 0)
        if magic != EXTENT_MAGIC or entries > maximum or 12 + entries * 12 > len(node):
            raise Ext4PathError("invalid extent node header")
        if expected_depth is not None and depth != expected_depth:
            raise Ext4PathError("extent tree depth changed unexpectedly")
        if depth > 5:
            raise Ext4PathError(f"unsupported extent depth: {depth}")

        extents: list[Extent] = []
        if depth == 0:
            for index in range(entries):
                offset = 12 + index * 12
                logical, raw_length, start_high, start_low = struct.unpack_from("<IHHI", node, offset)
                count = raw_length & 0x7FFF
                if count == 0:
                    raise Ext4PathError("zero-length extent")
                physical = start_low | (start_high << 32)
                if physical <= 0 or physical + count > self.blocks_count:
                    raise Ext4PathError("extent exceeds filesystem bounds")
                extents.append(Extent(logical, count, physical, bool(raw_length & 0x8000)))
            return extents

        for index in range(entries):
            offset = 12 + index * 12
            _logical, leaf_low, leaf_high = struct.unpack_from("<IIH", node, offset)
            leaf = leaf_low | (leaf_high << 32)
            extents.extend(self._parse_extent_node(self._read_block(leaf), depth - 1))
        return extents

    def extents(self, inode: Inode) -> list[Extent]:
        if not inode.flags & EXT4_EXTENTS_FL:
            raise Ext4PathError(f"inode {inode.number} does not use extents")
        extents = sorted(self._parse_extent_node(inode.block_tree), key=lambda item: item.logical_block)
        last_end = 0
        for extent in extents:
            if extent.logical_block < last_end:
                raise Ext4PathError("overlapping or unsorted extents")
            last_end = extent.logical_block + extent.block_count
        return extents

    def _inode_blocks(self, inode: Inode) -> Iterator[tuple[int, bytes]]:
        for extent in self.extents(inode):
            if extent.unwritten:
                continue
            for index in range(extent.block_count):
                logical = extent.logical_block + index
                if logical * self.block_size >= inode.size:
                    return
                yield logical, self._read_block(extent.physical_block + index)

    def directory_entries(self, inode: Inode) -> Iterator[tuple[str, int]]:
        if inode.mode & 0xF000 != 0x4000:
            raise Ext4PathError(f"inode {inode.number} is not a directory")
        for _logical, block in self._inode_blocks(inode):
            offset = 0
            while offset < self.block_size:
                if offset + 8 > self.block_size:
                    raise Ext4PathError("truncated directory entry")
                number, record_length, name_length = struct.unpack_from("<IHB", block, offset)
                if record_length < 8 or record_length % 4 or offset + record_length > self.block_size:
                    raise Ext4PathError("invalid directory record length")
                if name_length > record_length - 8:
                    raise Ext4PathError("invalid directory name length")
                if number:
                    name = block[offset + 8:offset + 8 + name_length].decode("utf-8", errors="strict")
                    yield name, number
                offset += record_length

    def resolve(self, path: str) -> Inode:
        parts = [part for part in path.split("/") if part]
        if any(part in (".", "..") for part in parts):
            raise Ext4PathError("relative path components are forbidden")
        current = self.inode(2)
        resolved = "/"
        for part in parts:
            if current.mode & 0xF000 != 0x4000:
                raise Ext4PathError(
                    f"cannot resolve {part!r}: {resolved} inode {current.number} "
                    f"has non-directory mode 0x{current.mode:04x}"
                )
            matches = [number for name, number in self.directory_entries(current) if name == part]
            if len(matches) != 1:
                raise Ext4PathError(
                    f"expected one {part!r} entry below {resolved}, found {len(matches)}"
                )
            current = self.inode(matches[0])
            resolved = resolved.rstrip("/") + "/" + part
        return current

    def read_file(self, inode: Inode, maximum_size: int = 1024 * 1024) -> bytes:
        if inode.mode & 0xF000 != 0x8000:
            raise Ext4PathError(f"inode {inode.number} is not a regular file")
        if inode.size > maximum_size:
            raise Ext4PathError(f"file is unexpectedly large: {inode.size}")
        output = bytearray(inode.size)
        for logical, block in self._inode_blocks(inode):
            start = logical * self.block_size
            output[start:min(start + self.block_size, inode.size)] = block[:max(0, inode.size - start)]
        return bytes(output)

    def physical_offset(self, inode: Inode, file_offset: int) -> int:
        if file_offset < 0 or file_offset >= inode.size:
            raise Ext4PathError("file offset is outside inode size")
        logical, within = divmod(file_offset, self.block_size)
        for extent in self.extents(inode):
            if extent.logical_block <= logical < extent.logical_block + extent.block_count:
                if extent.unwritten:
                    raise Ext4PathError("target byte is in an unwritten extent")
                physical = extent.physical_block + logical - extent.logical_block
                return physical * self.block_size + within
        raise Ext4PathError("target byte is in a sparse hole")
