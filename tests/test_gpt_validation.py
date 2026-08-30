import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from jibo_automod import EMMC_SECTOR_SIZE, validate_gpt_integrity


class GptValidationTests(unittest.TestCase):
    def _gpt_dump(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = Path(temp_dir.name) / "gpt.bin"
        data = bytearray(4096 * EMMC_SECTOR_SIZE)
        entries_offset = 2 * EMMC_SECTOR_SIZE
        entries = bytes(128 * 128)
        data[entries_offset:entries_offset + len(entries)] = entries

        header = bytearray(EMMC_SECTOR_SIZE)
        header[:8] = b"EFI PART"
        struct.pack_into("<I", header, 8, 0x00010000)
        struct.pack_into("<I", header, 12, 92)
        struct.pack_into("<Q", header, 24, 1)
        struct.pack_into("<Q", header, 32, 4095)
        struct.pack_into("<Q", header, 72, 2)
        struct.pack_into("<I", header, 80, 128)
        struct.pack_into("<I", header, 84, 128)
        struct.pack_into("<I", header, 88, zlib.crc32(entries) & 0xFFFFFFFF)
        header_crc = zlib.crc32(header[:92]) & 0xFFFFFFFF
        struct.pack_into("<I", header, 16, header_crc)
        data[EMMC_SECTOR_SIZE:2 * EMMC_SECTOR_SIZE] = header
        path.write_bytes(data)
        return path

    def test_valid_primary_gpt(self):
        validate_gpt_integrity(self._gpt_dump())

    def test_header_crc_failure_is_rejected(self):
        path = self._gpt_dump()
        data = bytearray(path.read_bytes())
        data[EMMC_SECTOR_SIZE + 24] ^= 1
        path.write_bytes(data)
        with self.assertRaisesRegex(ValueError, "header CRC mismatch"):
            validate_gpt_integrity(path)

    def test_entry_crc_failure_is_rejected(self):
        path = self._gpt_dump()
        data = bytearray(path.read_bytes())
        data[2 * EMMC_SECTOR_SIZE] ^= 1
        path.write_bytes(data)
        with self.assertRaisesRegex(ValueError, "entry-array CRC mismatch"):
            validate_gpt_integrity(path)


if __name__ == "__main__":
    unittest.main()
