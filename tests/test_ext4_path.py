import struct
import unittest

from ext4_path import EXT4_EXTENTS_FL, EXT4_FEATURE_INCOMPAT_EXTENTS, Ext4PathError, Ext4PathReader
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

    def test_resolve_reports_the_bad_path_component_and_inode_mode(self):
        image = bytearray(self._image())
        # Turn /etc's inode into a regular file while retaining the root entry.
        inode_offset = 3 * self.BLOCK + (3 - 1) * 128
        struct.pack_into("<H", image, inode_offset, 0x81A4)
        reader = Ext4PathReader(lambda offset, length: image[offset:offset + length], len(image))

        with self.assertRaisesRegex(
            Ext4PathError,
            "cannot resolve 'init.d': /etc inode 3 has non-directory mode 0x81a4",
        ):
            reader.resolve("/etc/init.d/S21firewall")


    def _legacy_inode(self, image, number, mode, size, pointers, flags=0):
        offset = 3 * self.BLOCK + (number - 1) * 128
        struct.pack_into("<H", image, offset, mode)
        struct.pack_into("<I", image, offset + 4, size)
        struct.pack_into("<I", image, offset + 32, flags)
        struct.pack_into("<15I", image, offset + 40, *(list(pointers) + [0] * (15 - len(pointers))))

    def test_resolves_legacy_direct_directory_and_regular_file(self):
        image = bytearray(self._image())
        self._legacy_inode(image, 2, 0x41ED, self.BLOCK, [10])
        self._legacy_inode(image, 5, 0x81A4, len(SIGNATURE_ORIGINAL), [13, 14, 15, 16])
        reader = Ext4PathReader(lambda offset, length: image[offset:offset + length], len(image))
        inode = reader.resolve("/etc/init.d/S21firewall")
        self.assertEqual(reader.read_file(inode), SIGNATURE_ORIGINAL)
        self.assertEqual(reader.physical_offset(inode, 0), 13 * self.BLOCK)

    def test_legacy_sparse_holes_stay_zero_and_have_no_physical_offset(self):
        image = bytearray(self._image())
        self._legacy_inode(image, 5, 0x81A4, 3 * self.BLOCK, [13, 0, 15])
        image[13 * self.BLOCK:14 * self.BLOCK] = b'a' * self.BLOCK
        image[15 * self.BLOCK:16 * self.BLOCK] = b'z' * self.BLOCK
        reader = Ext4PathReader(lambda offset, length: image[offset:offset + length], len(image))
        inode = reader.inode(5)
        self.assertEqual(reader.read_file(inode), b'a' * self.BLOCK + bytes(self.BLOCK) + b'z' * self.BLOCK)
        with self.assertRaisesRegex(Ext4PathError, "sparse hole"):
            reader.physical_offset(inode, self.BLOCK)

    def test_legacy_direct_boundary_and_empty_file(self):
        for count in (0, 12):
            with self.subTest(count=count):
                image = bytearray(self._image())
                pointers = list(range(13, 13 + count))
                self._legacy_inode(image, 5, 0x81A4, count * self.BLOCK, pointers)
                for logical, block in enumerate(pointers):
                    image[block * self.BLOCK:(block + 1) * self.BLOCK] = bytes([logical]) * self.BLOCK
                reader = Ext4PathReader(lambda offset, length: image[offset:offset + length], len(image))
                inode = reader.inode(5)
                self.assertEqual(reader.read_file(inode), b''.join(bytes([i]) * self.BLOCK for i in range(count)))
                if count:
                    self.assertEqual(reader.physical_offset(inode, 11 * self.BLOCK), 24 * self.BLOCK)

    def test_legacy_invalid_repeated_and_indirect_blocks_refuse(self):
        for size, pointers in ((self.BLOCK, [64]), (2 * self.BLOCK, [13, 13]),
                               (13 * self.BLOCK, [13]), (self.BLOCK, [13] + [0] * 11 + [14])):
            with self.subTest(size=size, pointers=pointers):
                image = bytearray(self._image())
                self._legacy_inode(image, 5, 0x81A4, size, pointers)
                reader = Ext4PathReader(lambda offset, length: image[offset:offset + length], len(image))
                with self.assertRaises(Ext4PathError):
                    reader.read_file(reader.inode(5))

    def test_legacy_encoded_data_and_symlink_maps_refuse(self):
        for mode, flags in ((0x81A4, 0x4), (0x81A4, 0x800), (0x81A4, 0x10000000), (0xA1FF, 0)):
            with self.subTest(mode=mode, flags=flags):
                image = bytearray(self._image())
                self._legacy_inode(image, 5, mode, 10, [13], flags)
                reader = Ext4PathReader(lambda offset, length: image[offset:offset + length], len(image))
                with self.assertRaises(Ext4PathError):
                    reader.extents(reader.inode(5))


if __name__ == "__main__":
    unittest.main()
