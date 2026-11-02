"""Pure primary-GPT parsing; no device, filesystem, platform or exploit imports."""
import struct
import zlib

SECTOR_SIZE = 512
MAX_PREFIX_BYTES = 2 * 1024 * 1024


def parse_primary_gpt(data, total_sectors):
    """Existing writer's CRC/bounds contract, kept compatible during extraction."""
    if len(data) < 2 * SECTOR_SIZE or data[SECTOR_SIZE:SECTOR_SIZE + 8] != b'EFI PART':
        raise ValueError('primary GPT signature is missing')
    header = data[SECTOR_SIZE:2 * SECTOR_SIZE]
    header_size = struct.unpack_from('<I', header, 12)[0]
    if not 92 <= header_size <= SECTOR_SIZE:
        raise ValueError('invalid GPT header size')
    expected_header_crc = struct.unpack_from('<I', header, 16)[0]
    header_crc = bytearray(header[:header_size]); header_crc[16:20] = b'\0' * 4
    if zlib.crc32(header_crc) & 0xFFFFFFFF != expected_header_crc:
        raise ValueError('GPT header CRC mismatch')
    entries_lba = struct.unpack_from('<Q', header, 72)[0]
    count = struct.unpack_from('<I', header, 80)[0]
    size = struct.unpack_from('<I', header, 84)[0]
    entries_start = entries_lba * SECTOR_SIZE; entries_length = count * size
    if count <= 0 or size < 128 or size % 8 or entries_start + entries_length > len(data):
        raise ValueError('GPT entry array is outside the bounded read')
    entries = data[entries_start:entries_start + entries_length]
    if zlib.crc32(entries) & 0xFFFFFFFF != struct.unpack_from('<I', header, 88)[0]:
        raise ValueError('GPT entry-array CRC mismatch')
    partitions = []
    for index in range(count):
        entry = entries[index * size:(index + 1) * size]
        if entry[:16] == b'\0' * 16:
            continue
        first, last = struct.unpack_from('<QQ', entry, 32)
        name = entry[56:128].decode('utf-16le', errors='ignore').rstrip('\0')
        if first > last or last >= total_sectors:
            raise ValueError('invalid GPT partition bounds')
        partitions.append(dict(name=name, start_sector=first, size_sectors=last-first+1))
    return partitions


def audit_primary_gpt(data, total_sectors):
    """Narrow offline 512-byte-sector profile, stricter than legacy writer admission."""
    def require(value):
        if not value: raise ValueError('unsupported_or_invalid_primary_gpt')
    require(type(data) is bytes and len(data) <= MAX_PREFIX_BYTES)
    require(type(total_sectors) is int and 68 <= total_sectors <= (1 << 48))
    partitions = parse_primary_gpt(data, total_sectors)
    header = data[SECTOR_SIZE:2 * SECTOR_SIZE]
    require(struct.unpack_from('<I', header, 8)[0] == 0x00010000)
    require(struct.unpack_from('<I', header, 12)[0] == 92 and struct.unpack_from('<I', header, 20)[0] == 0)
    current, backup, first_usable, last_usable = struct.unpack_from('<QQQQ', header, 24)
    require(current == 1 and backup == total_sectors-1 and header[56:72] != b'\0'*16)
    entries_lba, count, size = struct.unpack_from('<QII', header, 72)
    require(entries_lba >= 2 and 1 <= count <= 128 and size == 128)
    table_sectors = (count * size + SECTOR_SIZE-1) // SECTOR_SIZE
    require(entries_lba + table_sectors <= first_usable <= last_usable < backup-table_sectors)
    entries = data[entries_lba*SECTOR_SIZE:entries_lba*SECTOR_SIZE + count*size]
    unique_ids = set(); names = set(); ranges = []
    for index in range(count):
        entry = entries[index*size:(index+1)*size]
        if entry[:16] == b'\0'*16:
            # Unsupported dirty unused entries cannot hide unexamined ranges.
            require(entry == b'\0'*size)
            continue
        unique_id = entry[16:32]
        require(unique_id != b'\0'*16 and unique_id not in unique_ids); unique_ids.add(unique_id)
        name = entry[56:128].decode('utf-16le').rstrip('\0')
        require(name and all(c.isprintable() for c in name))
        normalized = ''.join(c for c in name.lower() if c.isalnum())
        require(normalized and normalized not in names); names.add(normalized)
        start, end = struct.unpack_from('<QQ', entry, 32)
        require(first_usable <= start <= end <= last_usable)
        ranges.append((start, end))
    ordered = sorted(ranges)
    require(all(left[1] < right[0] for left, right in zip(ordered, ordered[1:])))
    require(partitions)
    return dict(sectorSizeBytes=SECTOR_SIZE, suppliedDiskSectors=total_sectors,
                firstUsableSector=first_usable, lastUsableSector=last_usable,
                partitions=partitions, dualRootfsNamesPresent={'rootfsa', 'rootfsb'}.issubset(names))
