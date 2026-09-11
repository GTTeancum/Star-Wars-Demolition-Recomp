"""Minimal SH-4 disassembler - enough to read load/store/branch routines."""
import struct

def _n(o): return (o >> 8) & 0xF
def _m(o): return (o >> 4) & 0xF
def _d4(o): return o & 0xF
def _d8(o): return o & 0xFF
def _i8(o): return o & 0xFF
def _s8(o): return (o & 0xFF) - 256 if o & 0x80 else o & 0xFF
def _s12(o): return (o & 0xFFF) - 4096 if o & 0x800 else o & 0xFFF

def decode(op, pc, read32=None, read16=None):
    n, m, d4 = _n(op), _m(op), _d4(op)
    hi = op >> 12
    if op == 0x000B: return "rts"
    if op == 0x0009: return "nop"
    if op == 0x0028: return "clrmac"
    if hi == 0x6:
        t = {0:"mov.b @r%d,r%d",1:"mov.w @r%d,r%d",2:"mov.l @r%d,r%d",
             3:"mov r%d,r%d",4:"mov.b @r%d+,r%d",5:"mov.w @r%d+,r%d",
             6:"mov.l @r%d+,r%d",7:"not r%d,r%d",8:"swap.b r%d,r%d",
             9:"swap.w r%d,r%d",0xA:"negc r%d,r%d",0xB:"neg r%d,r%d",
             0xC:"extu.b r%d,r%d",0xD:"extu.w r%d,r%d",
             0xE:"exts.b r%d,r%d",0xF:"exts.w r%d,r%d"}.get(d4)
        if t: return t % (m, n)
    if hi == 0x2:
        t = {0:"mov.b r%d,@r%d",1:"mov.w r%d,@r%d",2:"mov.l r%d,@r%d",
             4:"mov.b r%d,@-r%d",5:"mov.w r%d,@-r%d",6:"mov.l r%d,@-r%d",
             8:"tst r%d,r%d",9:"and r%d,r%d",0xA:"xor r%d,r%d",0xB:"or r%d,r%d",
             0xE:"mulu.w r%d,r%d",0xF:"muls.w r%d,r%d"}.get(d4)
        if t: return t % (m, n)
    if hi == 0x3:
        t = {0:"cmp/eq r%d,r%d",2:"cmp/hs r%d,r%d",3:"cmp/ge r%d,r%d",
             4:"div1 r%d,r%d",5:"dmulu.l r%d,r%d",6:"cmp/hi r%d,r%d",
             7:"cmp/gt r%d,r%d",8:"sub r%d,r%d",0xA:"subc r%d,r%d",
             0xC:"add r%d,r%d",0xD:"dmuls.l r%d,r%d",0xE:"addc r%d,r%d"}.get(d4)
        if t: return t % (m, n)
    if hi == 0x1: return f"mov.l r{m},@({d4*4},r{n})"
    if hi == 0x5: return f"mov.l @({d4*4},r{m}),r{n}"
    if hi == 0xE: return f"mov #{_s8(op)},r{n}"
    if hi == 0x7: return f"add #{_s8(op)},r{n}"
    if hi == 0x9:
        addr = pc + 4 + _d8(op) * 2
        val = read16(addr) if read16 else None
        s = f"mov.w @({_d8(op)*2},pc),r{n}   ; [{addr:08X}]"
        if val is not None: s += f" = 0x{val:04X}"
        return s
    if hi == 0xD:
        addr = ((pc + 4) & ~3) + _d8(op) * 4
        val = read32(addr) if read32 else None
        s = f"mov.l @({_d8(op)*4},pc),r{n}   ; [{addr:08X}]"
        if val is not None: s += f" = 0x{val:08X}"
        return s
    if hi == 0xA: return f"bra {pc + 4 + _s12(op)*2:08X}"
    if hi == 0xB: return f"bsr {pc + 4 + _s12(op)*2:08X}"
    if hi == 0x8:
        sub = (op >> 8) & 0xF
        if sub == 0x9: return f"bt {pc + 4 + _s8(op)*2:08X}"
        if sub == 0xB: return f"bf {pc + 4 + _s8(op)*2:08X}"
        if sub == 0xD: return f"bt/s {pc + 4 + _s8(op)*2:08X}"
        if sub == 0xF: return f"bf/s {pc + 4 + _s8(op)*2:08X}"
        if sub == 0x0: return f"mov.b r0,@({d4},r{m})"
        if sub == 0x1: return f"mov.w r0,@({d4*2},r{m})"
        if sub == 0x4: return f"mov.b @({d4},r{m}),r0"
        if sub == 0x5: return f"mov.w @({d4*2},r{m}),r0"
        if sub == 0x8: return f"cmp/eq #{_s8(op)},r0"
    if hi == 0xC:
        sub = (op >> 8) & 0xF
        if sub == 0x8: return f"tst #{_i8(op)},r0"
        if sub == 0x9: return f"and #{_i8(op)},r0"
        if sub == 0xA: return f"xor #{_i8(op)},r0"
        if sub == 0xB: return f"or #{_i8(op)},r0"
        if sub == 0x7: return f"mova @({_d8(op)*4},pc),r0"
    if hi == 0x4:
        t = {0x0B:"jsr @r%d",0x2B:"jmp @r%d",0x0E:"ldc r%d,sr",0x1E:"ldc r%d,gbr",
             0x00:"shll r%d",0x01:"shlr r%d",0x04:"rotl r%d",0x05:"rotr r%d",
             0x08:"shll2 r%d",0x09:"shlr2 r%d",0x18:"shll8 r%d",0x19:"shlr8 r%d",
             0x28:"shll16 r%d",0x29:"shlr16 r%d",0x10:"dt r%d",0x11:"cmp/pz r%d",
             0x15:"cmp/pl r%d",0x0A:"lds r%d,mach",0x1A:"lds r%d,macl",
             0x2A:"lds r%d,pr",0x22:"sts.l pr,@-r%d",0x26:"lds.l @r%d+,pr",
             0x21:"shar r%d",0x20:"shal r%d"}.get(op & 0xFF)
        if t: return t % n
    if hi == 0x0:
        if (op & 0xFF) == 0x2A: return f"sts pr,r{n}"
        if (op & 0xFF) == 0x0A: return f"sts mach,r{n}"
        if (op & 0xFF) == 0x1A: return f"sts macl,r{n}"
        if (op & 0xF) == 0xC: return f"mov.b @(r0,r{m}),r{n}"
        if (op & 0xF) == 0xD: return f"mov.w @(r0,r{m}),r{n}"
        if (op & 0xF) == 0xE: return f"mov.l @(r0,r{m}),r{n}"
        if (op & 0xF) == 0x4: return f"mov.b r{m},@(r0,r{n})"
        if (op & 0xF) == 0x5: return f"mov.w r{m},@(r0,r{n})"
        if (op & 0xF) == 0x6: return f"mov.l r{m},@(r0,r{n})"
        if (op & 0xFF) == 0x23: return f"braf r{n}"
        if (op & 0xFF) == 0x03: return f"bsrf r{n}"
    return f".word 0x{op:04X}"

class Image:
    def __init__(self, data, base=0x8C010000):
        self.data, self.base = data, base
    def r16(self, addr):
        o = addr - self.base
        return struct.unpack_from("<H", self.data, o)[0] if 0 <= o < len(self.data)-1 else None
    def r32(self, addr):
        o = addr - self.base
        return struct.unpack_from("<I", self.data, o)[0] if 0 <= o < len(self.data)-3 else None
    def dis(self, addr, count=40):
        out = []
        for i in range(count):
            a = addr + i*2
            op = self.r16(a)
            if op is None: break
            out.append(f"{a:08X}  {op:04X}  {decode(op, a, self.r32, self.r16)}")
        return "\n".join(out)
