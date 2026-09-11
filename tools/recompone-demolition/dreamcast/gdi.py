import struct, pathlib
BASE = pathlib.Path("Dreamcast disc")
RAW = 2352
TRACKS = [(45000, BASE/"track03.bin"), (375479, BASE/"track15.bin")]
_handles = {}
def read_sector(lba):
    for start, path in TRACKS:
        n = path.stat().st_size // RAW
        if start <= lba < start + n:
            f = _handles.get(path) or _handles.setdefault(path, open(path, "rb"))
            f.seek((lba - start) * RAW)
            return f.read(RAW)[16:16+2048]
    raise KeyError(f"LBA {lba} not in any data track")

def read_bytes(lba, length):
    out = bytearray()
    while len(out) < length:
        out += read_sector(lba); lba += 1
    return bytes(out[:length])

def parse_dir(lba, size):
    data = read_bytes(lba, size)
    i = 0
    entries = []
    while i < len(data):
        ln = data[i]
        if ln == 0:
            i = (i // 2048 + 1) * 2048
            continue
        rec = data[i:i+ln]
        ext = struct.unpack_from("<I", rec, 2)[0]
        sz  = struct.unpack_from("<I", rec, 10)[0]
        flags = rec[25]
        nlen = rec[32]
        name = rec[33:33+nlen].decode("ascii", "replace")
        entries.append((name, ext, sz, flags))
        i += ln
    return entries

def root():
    pvd = read_sector(45000 + 16)
    rec = pvd[156:156+34]
    return struct.unpack_from("<I", rec, 2)[0], struct.unpack_from("<I", rec, 10)[0]
