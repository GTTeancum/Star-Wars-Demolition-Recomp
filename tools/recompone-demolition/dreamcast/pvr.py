"""Dreamcast PVR texture decoder -> RGBA.

Covers the formats Demolition actually ships: ARGB1555 / RGB565 / ARGB4444
pixels, in square-twiddled, rectangle-twiddled, VQ and palettised layouts,
each with or without a mip chain.
"""
import struct

PIXEL_ARGB1555, PIXEL_RGB565, PIXEL_ARGB4444 = 0x00, 0x01, 0x02

SQUARE_TWIDDLED        = 0x01
SQUARE_TWIDDLED_MIP    = 0x02
VQ                     = 0x03
VQ_MIP                 = 0x04
PALETTIZE4             = 0x05
PALETTIZE4_MIP         = 0x06
PALETTIZE8             = 0x07
PALETTIZE8_MIP         = 0x08
RECTANGLE              = 0x09
STRIDE                 = 0x0B
RECTANGLE_TWIDDLED     = 0x0D
SMALL_VQ               = 0x10
SMALL_VQ_MIP           = 0x11

MIPPED = {SQUARE_TWIDDLED_MIP, VQ_MIP, PALETTIZE4_MIP, PALETTIZE8_MIP,
          SMALL_VQ_MIP}
VQ_FORMATS = {VQ, VQ_MIP, SMALL_VQ, SMALL_VQ_MIP}


def unpack_pixel(value, pixel_format):
    if pixel_format == PIXEL_ARGB1555:
        a = 255 if value & 0x8000 else 0
        r = (value >> 10) & 0x1F
        g = (value >> 5) & 0x1F
        b = value & 0x1F
        return (r << 3 | r >> 2, g << 3 | g >> 2, b << 3 | b >> 2, a)
    if pixel_format == PIXEL_RGB565:
        r = (value >> 11) & 0x1F
        g = (value >> 5) & 0x3F
        b = value & 0x1F
        return (r << 3 | r >> 2, g << 2 | g >> 4, b << 3 | b >> 2, 255)
    if pixel_format == PIXEL_ARGB4444:
        a = (value >> 12) & 0xF
        r = (value >> 8) & 0xF
        g = (value >> 4) & 0xF
        b = value & 0xF
        return (r * 17, g * 17, b * 17, a * 17)
    raise ValueError(f"unsupported pixel format 0x{pixel_format:02X}")


def _twiddle_table(size):
    """Morton interleave for one axis, computed once per size."""
    table = [0] * size
    for i in range(size):
        v = 0
        for bit in range(16):
            if i & (1 << bit):
                v |= 1 << (2 * bit)
        table[i] = v
    return table


def _twiddled_index(x, y, table):
    # Interleave x into the low bit of each pair and y into the high bit.
    return (table[x] << 1) | table[y]


def read_cl32_palette(data, offset):
    """Read a CL32 colour list: 24-byte header then 256 RGBA entries."""
    if data[offset + 8:offset + 12] != b"CL32":
        return None
    # Entries are stored B,G,R,A - reading them as RGBA turns Tatooine blue.
    base = offset + 24
    out = []
    for i in range(256):
        b, g, r, a = data[base + i * 4: base + i * 4 + 4]
        out.append((r, g, b, a))
    return out


def decode(data, offset=0, palette=None):
    """Decode one PVRT chunk. Returns (width, height, rgba bytes)."""
    if data[offset:offset + 4] != b"PVRT":
        raise ValueError("not a PVRT chunk")
    chunk_size = struct.unpack_from("<I", data, offset + 4)[0]
    pixel_format = data[offset + 8]
    data_format = data[offset + 9]
    width, height = struct.unpack_from("<HH", data, offset + 12)
    body = offset + 16
    # The mip chain precedes the top level and carries a dummy entry whose size
    # differs per format, so counting forward gets it wrong by a byte or two and
    # shifts every texel - which decodes to a recognisable but speckled image.
    # The top level always ends at the chunk end, so count back from there.
    chunk_end = offset + 8 + chunk_size

    if data_format in VQ_FORMATS:
        entries = 256 if data_format in (VQ, VQ_MIP) else 64
        codebook = body
        body += entries * 8
        if data_format in MIPPED:
            body = chunk_end - (width >> 1) * (height >> 1)
        out = bytearray(width * height * 4)
        table = _twiddle_table(max(width, height) >> 1)
        bw, bh = width >> 1, height >> 1
        for by in range(bh):
            for bx in range(bw):
                index = data[body + _twiddled_index(bx, by, table)]
                base = codebook + index * 8
                for sub in range(4):
                    value = struct.unpack_from("<H", data, base + sub * 2)[0]
                    px, py = bx * 2 + (sub >> 1), by * 2 + (sub & 1)
                    o = (py * width + px) * 4
                    out[o:o + 4] = bytes(unpack_pixel(value, pixel_format))
        return width, height, bytes(out)

    if data_format in (PALETTIZE8, PALETTIZE8_MIP):
        if palette is None:
            raise NotImplementedError("palettised PVR needs its CL32 palette")
        if data_format in MIPPED:
            body = chunk_end - width * height
        out = bytearray(width * height * 4)
        table = _twiddle_table(min(width, height))
        block = min(width, height)
        for oy in range(0, height, block):
            for ox in range(0, width, block):
                base = body + oy * width + ox * block
                for y in range(block):
                    for x in range(block):
                        entry = data[base + _twiddled_index(x, y, table)]
                        o = ((oy + y) * width + ox + x) * 4
                        out[o:o + 4] = bytes(palette[entry])
        return width, height, bytes(out)

    if data_format in (PALETTIZE4, PALETTIZE4_MIP):
        raise NotImplementedError("4bpp palettised PVR not seen in this game")

    # 16-bit layouts.
    if data_format in MIPPED:
        body = chunk_end - width * height * 2

    out = bytearray(width * height * 4)
    if data_format in (RECTANGLE, STRIDE):
        for y in range(height):
            for x in range(width):
                value = struct.unpack_from(
                    "<H", data, body + (y * width + x) * 2)[0]
                o = (y * width + x) * 4
                out[o:o + 4] = bytes(unpack_pixel(value, pixel_format))
        return width, height, bytes(out)

    # Square- and rectangle-twiddled share the same addressing, with
    # rectangles handled as a row of square blocks.
    block = min(width, height)
    table = _twiddle_table(block)
    for oy in range(0, height, block):
        for ox in range(0, width, block):
            base = body + (oy * width + ox * block) * 2
            for y in range(block):
                for x in range(block):
                    value = struct.unpack_from(
                        "<H", data, base + _twiddled_index(x, y, table) * 2)[0]
                    o = ((oy + y) * width + ox + x) * 4
                    out[o:o + 4] = bytes(unpack_pixel(value, pixel_format))
    return width, height, bytes(out)
