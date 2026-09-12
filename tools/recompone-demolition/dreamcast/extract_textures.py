#!/usr/bin/env python3
"""Extract every Dreamcast texture to PNG.

The .EXP archives are IFF FORM containers. Textures are PVRT chunks scattered
through them; the terrain set inside XBMP is 8bpp and shares one CL32 palette
stored at the head of that chunk, so the owning chunk has to be known before a
texture can be decoded.
"""
from __future__ import annotations

import argparse
import pathlib
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import gdi
import pvr

ARCHIVES = {
    "LEVELS": ["CLOUDCTY.EXP", "DAGOBAH.EXP", "DESERT.EXP", "DETHSTAR.EXP",
               "HOTH.EXP", "MOSEISLY.EXP", "NABOO.EXP", "YAVIN4.EXP"],
    "SHARED": ["COMMON.EXP"],
    "SHELL": ["SHELL.EXP"],
}


def chunks(data):
    """Top-level IFF chunks as (id, start, end)."""
    out = []
    off = 12
    while off + 8 <= len(data):
        cid = data[off:off + 4]
        if not cid.isalnum():
            break
        length = struct.unpack_from(">I", data, off + 4)[0]
        out.append((cid.decode("ascii", "replace"), off, off + 8 + length))
        off += 8 + length + (length & 1)
    return out


def extract(data, name, out_dir):
    table = chunks(data)
    palettes = {}
    for cid, start, end in table:
        # The CL32 header sits at the chunk's data start, past its 8-byte id.
        palette = pvr.read_cl32_palette(data, start + 8)
        if palette:
            palettes[(start, end)] = palette

    def palette_for(pos):
        for (start, end), palette in palettes.items():
            if start <= pos < end:
                return palette
        return None

    def owner(pos):
        for cid, start, end in table:
            if start <= pos < end:
                return cid
        return "ROOT"

    from PIL import Image
    out_dir.mkdir(parents=True, exist_ok=True)
    index = 0
    written = failed = 0
    offset = 0
    while True:
        i = data.find(b"PVRT", offset)
        if i < 0:
            break
        offset = i + 1
        width, height = struct.unpack_from("<HH", data, i + 12)
        if not (0 < width <= 2048 and 0 < height <= 2048):
            continue
        try:
            w, h, rgba = pvr.decode(data, i, palette_for(i))
        except Exception:
            failed += 1
            index += 1
            continue
        stem = f"{index:04d}_{owner(i)}_{w}x{h}"
        Image.frombytes("RGBA", (w, h), rgba).save(out_dir / f"{stem}.png")
        written += 1
        index += 1
    print(f"{name}: {written} written, {failed} undecoded")
    return written, failed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=pathlib.Path,
                        default=pathlib.Path("work/dreamcast/textures"))
    args = parser.parse_args()

    lba, size = gdi.root()
    directories = {name.strip(): (ext, sz)
                   for name, ext, sz, flags in gdi.parse_dir(lba, size)
                   if flags & 2}
    total_written = total_failed = 0
    for directory, names in ARCHIVES.items():
        if directory not in directories:
            continue
        ext, sz = directories[directory]
        entries = {n.split(";")[0]: (e, s)
                   for n, e, s, f in gdi.parse_dir(ext, sz) if not f & 2}
        for archive in names:
            if archive not in entries:
                print(f"{archive}: not on disc")
                continue
            lba_a, size_a = entries[archive]
            data = gdi.read_bytes(lba_a, size_a)
            written, failed = extract(
                data, archive, args.out / archive.split(".")[0])
            total_written += written
            total_failed += failed
    print(f"total: {total_written} written, {total_failed} undecoded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
