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
