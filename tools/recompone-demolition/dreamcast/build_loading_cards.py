#!/usr/bin/env python3
"""Turn the Dreamcast loading screens into PC loading-card overlays.

The renderer takes these as P6 PPM at 1280x448 named
"<level>_loading_card_4x.ppm", which it resolves to the LEVELS_<LEVEL> overlay.

The Dreamcast art is 640x256 and is exactly twice the PlayStation band: the
PlayStation loading screen draws its picture into native rows 16..127, which is
320x112, and the Dreamcast picture is the same 640x224 image with sixteen
native rows of letterbox below it. Correlating a captured PlayStation band
against every vertical crop of the Dreamcast art picks rows 0..223 with no
horizontal adjustment, so the two line up pixel for pixel once doubled.

That exact alignment is what lets the renderer keep the engine-drawn arena
title: it compares the original frame against the card and preserves the
pixels that disagree, which are the title glyphs and nothing else.
"""
from __future__ import annotations

import argparse
import pathlib

# 640x224 of Dreamcast content at 2x. The renderer accepts 1280x384 and
# 1280x448; only the latter preserves the source aspect without resampling
# error, and the letterbox below row 224 is dropped rather than scaled.
CONTENT_ROWS = 224
TARGET = (1280, 448)


def main() -> int:
    from PIL import Image
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--textures", type=pathlib.Path,
                        default=pathlib.Path("work/dreamcast/textures"))
    parser.add_argument("--out", type=pathlib.Path, default=pathlib.Path(
        "game/mods/enhanced_textures_2x/loading_cards"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    written = 0
    for source in sorted(args.textures.glob("*/loading_screen.png")):
        level = source.parent.name
        image = Image.open(source).convert("RGB")
        if image.size != (640, 256):
            print(f"{level}: skipped, expected 640x256, found {image.size}")
            continue
        cropped = image.crop((0, 0, image.width, CONTENT_ROWS))
        fitted = cropped.resize(TARGET, Image.LANCZOS)
        path = args.out / f"{level.lower()}_loading_card_4x.ppm"
        with open(path, "wb") as handle:
            handle.write(f"P6\n{TARGET[0]} {TARGET[1]}\n255\n".encode("ascii"))
            handle.write(fitted.tobytes())
        print(f"{level}: rows 0..{CONTENT_ROWS - 1} -> {path.name}")
        written += 1
    print(f"{written} loading cards written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
