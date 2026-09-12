#!/usr/bin/env python3
"""Build the arena terrain atlases of the texture pack from Dreamcast art.

Both versions store an arena's ground textures the same way: a chunk called
XBMP inside the .EXP holding an eight-bit-per-pixel image and its palette. The
PlayStation packs the whole set into one sheet - 480x192 for most arenas, a
grid of 48-pixel cells - while the Dreamcast keeps each cell as its own 64x64
texture. The counts agree exactly for every arena, and correlating the two sets
pairs them with the best score above 0.97 against a runner-up below 0.75, in
plain row-major order.

The renderer matches terrain by hashing the live index data against the tiles
of an atlas declared in the manifest, so the entry carries the PlayStation
indices and palette unchanged; only the image it points at is replaced.
"""
from __future__ import annotations

import argparse
import base64
import glob
import json
import pathlib
import re
import struct

# Two pixels per halfword at eight bits, and the renderer's depth code for it.
DEPTH_8BPP = 1
TILE = 48
# 64x64 of Dreamcast art into a 48-pixel cell needs a multiple of 48 that does
# not throw detail away; 2x gives 96x96 per cell, a 1.5x resample of the source.
SCALE = 2


def iff_chunks(data):
    if data[:4] != b"FORM":
        return
    off = 12
    while off + 8 <= len(data):
        tag = data[off:off + 4]
        length = struct.unpack_from(">I", data, off + 4)[0]
        yield tag.decode("latin-1"), off + 8, length
        off += 8 + length + (length & 1)


def read_tim(data, base):
    """Palette and indices of the TIM at base, as (palette, indices, w, h)."""
    flags = struct.unpack_from("<I", data, base + 4)[0]
    if flags & 3 != DEPTH_8BPP:
        raise ValueError(f"expected an eight-bit TIM, found flags {flags:#x}")
    off = base + 8
    clut_length, _cx, _cy, clut_w, clut_h = struct.unpack_from(
        "<IHHHH", data, off)
    palette = list(struct.unpack_from(f"<{clut_w * clut_h}H", data, off + 12))
    off += clut_length
    _length, _x, _y, width_words, height = struct.unpack_from(
        "<IHHHH", data, off)
    width = width_words * 2
    indices = data[off + 12: off + 12 + width * height]
    # The renderer requires 256 entries. Arenas that author fewer leave the
    # tail unreferenced, so zeros are never sampled.
    palette += [0] * (256 - len(palette))
    return palette[:256], indices, width, height


def to_rgb(entry):
    r, g, b = (entry & 31) << 3, ((entry >> 5) & 31) << 3, ((entry >> 10) & 31) << 3
    return r | r >> 5, g | g >> 5, b | b >> 5


def main() -> int:
    import numpy as np
    from PIL import Image

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--levels", type=pathlib.Path,
                        default=pathlib.Path("game/LEVELS"))
    parser.add_argument("--textures", type=pathlib.Path,
                        default=pathlib.Path("work/dreamcast/textures"))
    parser.add_argument("--out", type=pathlib.Path, default=pathlib.Path(
        "game/mods/enhanced_textures_2x"))
    parser.add_argument("--min-score", type=float, default=0.60)
    parser.add_argument("--flat-deviation", type=float, default=6.0)
    args = parser.parse_args()
    (args.out / "terrain").mkdir(parents=True, exist_ok=True)

    def normalize(block):
        block = block.astype(np.float32).mean(axis=2)
        return (block - block.mean()) / (block.std() + 1e-6)

    atlases = []
    for source in sorted(args.levels.glob("*.EXP")):
        name = source.stem
        data = source.read_bytes()
        base = next((start for tag, start, _ in iff_chunks(data)
                     if tag == "XBMP"), None)
        if base is None:
            print(f"{name}: no XBMP chunk")
            continue
        palette, indices, width, height = read_tim(data, base)
        lut = np.array([to_rgb(entry) for entry in palette], dtype=np.uint8)
        sheet = lut[np.frombuffer(indices, dtype=np.uint8)
                    .reshape(height, width)]

        if width % TILE or height % TILE:
            print(f"{name}: {width}x{height} is not a whole number of cells")
            continue
        columns, rows = width // TILE, height // TILE
        cells = [(x, y) for y in range(rows) for x in range(columns)]

        replacements = sorted(
            glob.glob(str(args.textures / name / "*_XBMP_*.png")))
        if len(replacements) != len(cells):
            print(f"{name}: {len(replacements)} Dreamcast textures for "
                  f"{len(cells)} cells, skipped")
            continue

        reference = {
            cell: normalize(sheet[cell[1] * TILE:(cell[1] + 1) * TILE,
                                  cell[0] * TILE:(cell[0] + 1) * TILE])
            for cell in cells}
        image = Image.new("RGB", (width * SCALE, height * SCALE))
        kept = []
        for index, path in enumerate(replacements):
            cell = cells[index]
            original = Image.fromarray(
                sheet[cell[1] * TILE:(cell[1] + 1) * TILE,
                      cell[0] * TILE:(cell[0] + 1) * TILE])
            source_image = Image.open(path).convert("RGB")
            probe = normalize(np.asarray(
                source_image.resize((TILE, TILE), Image.LANCZOS)))
            score = float((probe * reference[cell]).mean())
            # A cell with no structure correlates with nothing, so a low score
            # there says only that there was nothing to compare. A cell that
            # does have structure and still disagrees is art the Dreamcast
            # drew differently, and substituting it would put the wrong
            # picture on the ground.
            flat = float(np.asarray(original).astype(np.float32)
                         .mean(axis=2).std()) < args.flat_deviation
            replaced = flat or score >= args.min_score
            if not replaced:
                kept.append((cell, score))
            image.paste(
                (source_image if replaced else original).resize(
                    (TILE * SCALE, TILE * SCALE), Image.LANCZOS),
                (cell[0] * TILE * SCALE, cell[1] * TILE * SCALE))

        if kept:
            print(f"{name}: kept the original art for {len(kept)} cells the "
                  "Dreamcast draws differently: " +
                  ", ".join(f"{cell} {score:.2f}" for cell, score in kept[:6]) +
                  (" ..." if len(kept) > 6 else ""))
        relative = f"terrain/{name.lower()}.png"
        image.save(args.out / relative)

        digest = 14695981039346656037
        def add(value):
            nonlocal digest
            digest = ((digest ^ value) * 1099511628211) & 0xFFFFFFFFFFFFFFFF
        for value in (width & 0xFF, width >> 8, height & 0xFF, height >> 8):
            add(value)
        for value in indices:
            add(value)

        atlases.append({
            "name": name.lower(),
            "image": relative,
            "width": width,
            "height": height,
            "tileSize": TILE,
            "imageX": 0,
            "imageY": 0,
            "depth": DEPTH_8BPP,
            "indexHash": f"{digest:016x}",
            "indices": base64.b64encode(indices).decode("ascii"),
            "palette": [f"{entry:04x}" for entry in palette],
        })
        print(f"{name}: {columns}x{rows} cells of {TILE}px -> {relative} "
              f"({width * SCALE}x{height * SCALE}), "
              f"{len(cells) - len(kept)}/{len(cells)} cells replaced")

    manifest_path = args.out / "manifest.json"
    manifest = (json.loads(manifest_path.read_text())
                if manifest_path.is_file() else {})
    # The renderer reads "format", accepts 2 or 3, and requires "entries" to
    # be present even when every replacement is a terrain atlas.
    manifest.setdefault("format", 3)
    manifest.setdefault("entries", [])
    manifest["terrainAtlases"] = atlases
    manifest_path.write_text(json.dumps(manifest, indent=1))
    print(f"{len(atlases)} terrain atlases written to {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
