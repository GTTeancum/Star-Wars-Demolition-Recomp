# Dreamcast reference tooling

The Dreamcast build is the reference for Demolition's intended visuals, so these
read it directly rather than inferring behaviour from the PS1 port.

`gdi.py` reads the GDI image in `Dreamcast disc`. The filesystem lives on
track 3 but file extents are absolute disc LBAs that also reach into track 15,
so it maps an LBA onto whichever data track contains it and returns the 2048
user bytes out of each 2352-byte raw sector.

```python
import sys; sys.path.insert(0, "tools/recompone-demolition/dreamcast")
from gdi import root, parse_dir, read_bytes
lba, size = root()
for name, ext, sz, flags in parse_dir(lba, size):
    print(name, ext, sz)
# 1ST_READ.BIN is the SH-4 executable; it loads at 0x8C010000.
```

`sh4.py` is a partial SH-4 disassembler - loads, stores, arithmetic, branches
and the PC-relative literal forms, which is what following a setup routine
needs. It annotates `mov.l/mov.w @(disp,pc)` with the literal it resolves to,
which is how the fog chain below was read.

## What has been read out of it so far

Fog, traced from the register write backwards:

- `0x8C0CCA28` writes a PVR register: offset in r4, value in r5, base
  `0xA05F8000`.
- `0x8C0CB9D0` flushes dirty fog state - bit 0 writes `FOG_COL_RAM` (+0xB0)
  from `0x8C1B409C`, bit 1 writes `FOG_DENSITY` (+0xB8) from `0x8C1B40A0`,
  bit 3 writes `FOG_COL_VERT` (+0xB4) from `0x8C1B4098`.
- `0x8C0C63F8` is the fog table colour setter: stores its stack argument to
  `0x8C1B409C` and raises dirty bit 0. `0x8C0C6388` is the density setter.
- `0x8C058A20` is the arena installer. It reads three consecutive bytes at
  `0x8C1F1A44`, packs them `b0 << 16 | b1 << 8 | b2`, and passes that as the
  fog table colour.

Three consecutive bytes as R, G, B is the shape the PS1 port reads from its own
COLS block, which is what `ColsFogOffset` in V82Compat.cs is based on.

## Texture extraction

`pvr.py` decodes Dreamcast PVR textures to RGBA and `extract_textures.py`
writes every one in the game to PNG:

```powershell
python tools\recompone-demolition\dreamcast\extract_textures.py
```

2,413 of 2,423 come out. The remaining ten are 4bpp mipmapped, which nothing in
the game appears to use.

Textures are not only in the .EXP level archives, and the ones that are not are
the interesting ones. `SHELL/LOAD.TBL`, `SHELL/RESOURCE.TBL` and
`SHARED/HUD.TBL` are plain tables - a count, then offsets - rather than FORM
containers, and they hold four complete font atlases (256x256 4bpp, ASCII plus
the controller button glyphs), the title art, the radar and HUD plates, and the
loading background gradient. The loading screens are the `XLSC` chunk in each level archive, one per level.
Each is a 640x256 image the disc stores as a 512-wide and a 128-wide texture,
because 640 is not a power of two; the extractor rejoins them into
`loading_screen.png`. Split in half they read as scenery and are easy to miss.

Those 4bpp and 8bpp plates carry no palette of their own - no CL32, no PVPL -
so `pvr.decode` renders their indices as a grey ramp unless a palette is passed.
That is enough to identify an image but not to use it; the palette source has
not been found yet.

What the format needed, none of which is guessable:

- `.EXP` is an IFF `FORM` container with big-endian chunk lengths and form type
  `TERR`. The PS1 and Dreamcast builds carry the *same chunk list in the same
  order* - `TITL TEXT XLSC HEAD XBGM SUNA COLS XBMP XTIN ZONE... ZMAP FORM` -
  which is what makes matching the two texture sets tractable.
- Textures are `PVRT` chunks scattered through the archive. Pixel formats seen
  are ARGB1555 and ARGB4444; layouts are square-twiddled, rectangle-twiddled and
  VQ, each with or without a mip chain, plus 8bpp palettised for terrain.
- Twiddled addressing interleaves **x into the low bit** of each pair. The other
  way round decodes to a transposed image that still looks plausible, so check
  against `SHARED/FILLER.PVR`, which is the title screen and reads as text.
- The terrain set in `XBMP` is 8bpp sharing one palette: a `CL32` header at the
  chunk's data start, then 256 entries stored **B,G,R,A**. Reading those as RGBA
  turns Tatooine blue, which is an easy tell.
- `COLS` is 32 bytes, eight colour words. Word one is the atmosphere colour the
  fog fades toward - `63 3C 32` in DESERT.EXP, matching what the PS1 build holds
  at gp+0xCF0 and confirming `ColsFogOffset` from the disc side.
