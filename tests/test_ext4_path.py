import struct
import unittest

from ext4_path import EXT4_EXTENTS_FL, EXT4_FEATURE_INCOMPAT_EXTENTS, Ext4PathReader
from firewall_patch import SIGNATURE_ORIGINAL, build_sector_patch_from_reader, inspect_firewall_file


class Ext4PathReaderTests(unittest.TestCase):
    BLOCK = 1024

    def _inode(self, image, number, mode, size, physical_block, block_count=1):
        offset = 3 * self.BLOCK + (number - 1) * 128
        struct.pack_into("<H", image, offset, mode)
        struct.pack_into("<I", image, offset + 4, size)
        struct.pack_into("<I", image, offset + 32, EXT4_EXTENTS_FL)
        struct.pack_into("<HHHHI", image, offset + 40, 0xF30A, 1, 4, 0, 0)
        struct.pack_into("<IHHI", image, offset + 52, 0, block_count, 0, physical_block)

    def _directory(self, *entries):
        block = bytearray(self.BLOCK)
        offset = 0
        all_entries = [(2, ".", 2), (2, "..", 2), *entries]
        for index, (inode, name, file_type) in enumerate(all_entries):
            encoded = name.encode()
            minimum = (8 + len(encoded) + 3) & ~3
            record_length = self.BLOCK - offset if index == len(all_entries) - 1 else minimum
            struct.pack_into("<IHBB", block, offset, inode, record_length, len(encoded), file_type)
            block[offset + 8:offset + 8 + len(encoded)] = encoded
            offset += record_length
        return block

    def _image(self):
        image = bytearray(64 * self.BLOCK)
        superblock = 1024
        struct.pack_into("<I", image, superblock + 4, 64)
        struct.pack_into("<I", image, superblock + 24, 0)
        struct.pack_into("<I", image, superblock + 32, 64)
        struct.pack_into("<I", image, superblock + 40, 16)
        struct.pack_into("<H", image, superblock + 56, 0xEF53)
        struct.pack_into("<H", image, superblock + 88, 128)
        struct.pack_into("<I", image, superblock + 96, EXT4_FEATURE_INCOMPAT_EXTENTS)
        image[superblock + 104:superblock + 120] = bytes(range(16))
        struct.pack_into("<I", image, 2 * self.BLOCK + 8, 3)

        self._inode(image, 2, 0x41ED, self.BLOCK, 10)
        self._inode(image, 3, 0x41ED, self.BLOCK, 11)
        self._inode(image, 4, 0x41ED, self.BLOCK, 12)
        self._inode(image, 5, 0x81A4, len(SIGNATURE_ORIGINAL), 13, 4)
        image[10 * self.BLOCK:11 * self.BLOCK] = self._directory((3, "etc", 2))
        image[11 * self.BLOCK:12 * self.BLOCK] = self._directory((4, "init.d", 2))
        image[12 * self.BLOCK:13 * self.BLOCK] = self._directory((5, "S21firewall", 1))
        image[13 * self.BLOCK:13 * self.BLOCK + len(SIGNATURE_ORIGINAL)] = SIGNATURE_ORIGINAL
        return bytes(image)

    def test_resolves_profile_and_maps_patch_sector(self):
        image = self._image()
        reader = Ext4PathReader(lambda offset, length: image[offset:offset + length], len(image))
        inode = reader.resolve("/etc/init.d/S21firewall")
        match = inspect_firewall_file(reader.read_file(inode))
        physical = reader.physical_offset(inode, match.assignment_offset)
        patch = build_sector_patch_from_reader(
            match,
            physical,
            lambda offset, length: image[offset:offset + length],
        )
        self.assertEqual(inode.number, 5)
        self.assertEqual(match.state, "original")
        self.assertEqual(physical, 13 * self.BLOCK + match.assignment_offset)
        self.assertEqual(len(patch.before), 512)
        self.assertNotEqual(patch.before, patch.after)


if __name__ == "__main__":
    unittest.main()
