"""Tiny MIPS I disassembler for reading PS-X EXE code (enough for loops and memory ops)."""
import struct, sys
R = ["zero","at","v0","v1","a0","a1","a2","a3","t0","t1","t2","t3","t4","t5","t6","t7",
     "s0","s1","s2","s3","s4","s5","s6","s7","t8","t9","k0","k1","gp","sp","fp","ra"]
I_OPS = {0x08:"addi",0x09:"addiu",0x0A:"slti",0x0B:"sltiu",0x0C:"andi",0x0D:"ori",0x0E:"xori",
         0x20:"lb",0x21:"lh",0x23:"lw",0x24:"lbu",0x25:"lhu",0x28:"sb",0x29:"sh",0x2B:"sw"}
FUN = {0x00:"sll",0x02:"srl",0x03:"sra",0x04:"sllv",0x06:"srlv",0x08:"jr",0x09:"jalr",0x10:"mfhi",0x12:"mflo",
       0x18:"mult",0x19:"multu",0x1A:"div",0x1B:"divu",0x20:"add",0x21:"addu",0x22:"sub",0x23:"subu",
       0x24:"and",0x25:"or",0x26:"xor",0x27:"nor",0x2A:"slt",0x2B:"sltu"}
def dis(w, pc):
    op = w >> 26; rs, rt, rd = (w >> 21) & 31, (w >> 16) & 31, (w >> 11) & 31
    imm = w & 0xFFFF; simm = imm - 0x10000 if imm & 0x8000 else imm
    if w == 0: return "nop"
    if op == 0:
        f = w & 0x3F; n = FUN.get(f, f"special{f:#x}")
        if f in (0, 2, 3): return f"{n} {R[rd]}, {R[rt]}, {(w >> 6) & 31}"
        if f == 8: return f"jr {R[rs]}"
        if f in (0x10, 0x12): return f"{n} {R[rd]}"
        if f in (0x18, 0x19, 0x1A, 0x1B): return f"{n} {R[rs]}, {R[rt]}"
        return f"{n} {R[rd]}, {R[rs]}, {R[rt]}"
    if op in (2, 3): return f"{'j' if op == 2 else 'jal'} {((pc & 0xF0000000) | ((w & 0x3FFFFFF) << 2)):#010x}"
    if op in (4, 5): return f"{'beq' if op == 4 else 'bne'} {R[rs]}, {R[rt]}, {pc + 4 + simm * 4:#010x}"
    if op in (6, 7): return f"{'blez' if op == 6 else 'bgtz'} {R[rs]}, {pc + 4 + simm * 4:#010x}"
    if op == 1: return f"{['bltz','bgez'][rt & 1]} {R[rs]}, {pc + 4 + simm * 4:#010x}"
    if op == 0x0F: return f"lui {R[rt]}, {imm:#06x}"
    if op in I_OPS:
        n = I_OPS[op]
        if op >= 0x20: return f"{n} {R[rt]}, {simm}({R[rs]})"
        return f"{n} {R[rt]}, {R[rs]}, {imm:#x}" if op in (0x0C, 0x0D, 0x0E) else f"{n} {R[rt]}, {R[rs]}, {simm}"
    return f".word {w:#010x}"
def listing(exe, start, count, base=0x80010000):
    d = open(exe, "rb").read()
    for k in range(count):
        pc = start + 4 * k
        w = struct.unpack_from("<I", d, 0x800 + pc - base)[0]
        print(f"{pc:#010x}: {dis(w, pc)}")
if __name__ == "__main__":
    listing(sys.argv[1], int(sys.argv[2], 16), int(sys.argv[3]))
