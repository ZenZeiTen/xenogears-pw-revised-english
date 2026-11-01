"""EDC/ECC regeneration for raw 2352-byte Mode 2 Form 1 sectors (ECMA-130)."""

EDC_LUT = []
for i in range(256):
    e = i
    for _ in range(8):
        e = (e >> 1) ^ (0xD8018001 if e & 1 else 0)
    EDC_LUT.append(e)

ECC_F = [((i << 1) ^ (0x11D if i & 0x80 else 0)) & 0xFF for i in range(256)]
ECC_B = [0] * 256
for i in range(256):
    ECC_B[i ^ ECC_F[i]] = i


def edc(data):
    e = 0
    for b in data:
        e = (e >> 8) ^ EDC_LUT[(e ^ b) & 0xFF]
    return e


def _ecc_block(src, major_count, minor_count, major_mult, minor_inc):
    size = major_count * minor_count
    out = bytearray(major_count * 2)
    for major in range(major_count):
        index = (major >> 1) * major_mult + (major & 1)
        a = b = 0
        for _ in range(minor_count):
            t = src[index]
            index += minor_inc
            if index >= size:
                index -= size
            a ^= t
            b ^= t
            a = ECC_F[a]
        a = ECC_B[ECC_F[a] ^ b]
        out[major] = a
        out[major + major_count] = a ^ b
    return out


def fix_mode2_form1(sector):
    """Recompute EDC and P/Q ECC in place. sector: bytearray of 2352 bytes."""
    assert len(sector) == 2352
    assert sector[0x12] & 0x20 == 0, "Form 2 sector"
    sector[0x818:0x81C] = edc(sector[0x10:0x818]).to_bytes(4, "little")
    header = bytes(sector[0x0C:0x10])
    sector[0x0C:0x10] = b"\0\0\0\0"  # Mode 2 ECC is computed with a zeroed header
    sector[0x81C:0x8C8] = _ecc_block(sector[0x0C:], 86, 24, 2, 86)
    sector[0x8C8:0x930] = _ecc_block(sector[0x0C:], 52, 43, 86, 88)
    sector[0x0C:0x10] = header
    return sector
