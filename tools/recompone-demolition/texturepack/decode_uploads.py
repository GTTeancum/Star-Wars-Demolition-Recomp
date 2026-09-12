#!/usr/bin/env python3
"""Decode the VRAM upload blocks a run dumps into viewable images.

RECOMPONE_VRAM_UPLOAD_DUMP_DIR writes one .bin per distinct upload, holding the
raw little-endian halfwords, plus uploads.txt listing every upload in order as
"hash x y widthWords height". The PlayStation uploads a colour lookup table
immediately before the image that uses it, so the table for an image is the
most recent 16- or 256-entry upload ahead of it in that list.

Colour depth is not in the stream. A 16-entry table means four bits per pixel
and a 256-entry table means eight, which covers everything this game uploads
through a table; blocks with no table ahead of them are direct 16-bit colour.
"""
from __future__ import annotations

import argparse
import pathlib
import struct


def parse_index(path: pathlib.Path):
    rows = []
    for line in path.read_text().splitlines():
        parts = line.split()
        if len(parts) != 5:
            continue
        rows.append((parts[0], int(parts[1]), int(parts[2]),
                     int(parts[3]), int(parts[4])))
    return rows


def words(path: pathlib.Path):
    raw = path.read_bytes()
    return struct.unpack(f"<{len(raw) // 2}H", raw)


def rgba(word: int):
    r = (word & 0x1F) << 3
    g = ((word >> 5) & 0x1F) << 3
    b = ((word >> 10) & 0x1F) << 3
    # Bit 15 is the semi-transparency flag, not alpha. A fully zero halfword
    # is the transparent colour; everything else is opaque.
    return (r | r >> 5, g | g >> 5, b | b >> 5, 0 if word == 0 else 255)


def decode(block, width_words, height, clut, depth):
    pixels = []
    if depth == 16:
        for word in block:
            pixels.append(rgba(word))
        return width_words, height, pixels
    per_word = 4 if depth == 4 else 2
    mask = 0xF if depth == 4 else 0xFF
    shift = 4 if depth == 4 else 8
    for word in block:
        for lane in range(per_word):
            index = (word >> (lane * shift)) & mask
            pixels.append(clut[index] if index < len(clut)
                          else (255, 0, 255, 255))
    return width_words * per_word, height, pixels


def main() -> int:
    from PIL import Image
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("blocks", type=pathlib.Path)
    parser.add_argument("--out", type=pathlib.Path, required=True)
    parser.add_argument("--min-words", type=int, default=64,
                        help="skip uploads smaller than this many halfwords")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    rows = parse_index(args.blocks / "uploads.txt")
    clut_for: dict[str, tuple[str, int]] = {}
    pending: tuple[str, int] | None = None
    for digest, _x, _y, width, height in rows:
        if height == 1 and width in (16, 256):
            pending = (digest, width)
            continue
        if digest not in clut_for and pending is not None:
            clut_for[digest] = pending

    written = 0
    for path in sorted(args.blocks.glob("*.bin")):
        digest, _, shape = path.stem.partition("_")
        width, _, height = shape.partition("x")
        width, height = int(width), int(height)
        if width * height < args.min_words:
            continue
        table = clut_for.get(digest)
        if table is None:
            depth, clut = 16, []
        else:
            clut_path = next(
                args.blocks.glob(f"{table[0]}_*.bin"), None)
            if clut_path is None:
                continue
            clut = [rgba(word) for word in words(clut_path)]
            depth = 4 if table[1] == 16 else 8
        out_w, out_h, pixels = decode(
            words(path), width, height, clut, depth)
        image = Image.new("RGBA", (out_w, out_h))
        image.putdata(pixels)
        image.save(args.out / f"{digest}_{out_w}x{out_h}_{depth}bpp.png")
        written += 1
    print(f"{written} upload blocks decoded to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
