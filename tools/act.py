"""
Chocobo Tales field event scripts (.act): u32 offset of the string area, then commands until that offset.
Command: u16 opcode, u16 byte length (header included), then 8-byte arguments: u16 type, u16 0, u32 value.
Argument types seen in the field overlay's interpreter: 1 immediate, 2 code offset, 4 flag field
(value = flag | width << 16, read with get_field / written with set_field), 8 variable, 0x40 indirect.
"""
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "NDSTools"))
from ndstools.rom import NDSRom  # noqa: E402

FLAG = 4


def parse(data: bytes) -> list[tuple[int, int, list[tuple[int, int]]]]:
    """[(offset, opcode, [(type, value), ...])]"""
    end = struct.unpack_from("<I", data, 0)[0]
    p = 4
    commands = []
    while p < end:
        opcode, length = struct.unpack_from("<HH", data, p)
        if length < 4:
            raise ValueError(f"bad command length {length} at {p:#x}")
        args = [struct.unpack_from("<HxxI", data, q) for q in range(p + 4, p + length - 7, 8)]
        commands.append((p, opcode, args))
        p += length
    return commands


def all_scripts(rom: NDSRom) -> dict[str, list]:
    scripts = {}
    for path in rom.files:
        if path.endswith(".act"):
            try:
                scripts[path] = parse(rom.read(path))
            except (ValueError, struct.error) as error:
                print(f"skip {path}: {error}", file=sys.stderr)
    return scripts


if __name__ == "__main__":
    rom = NDSRom(sys.argv[1])
    scripts = all_scripts(rom)
    patterns = defaultdict(Counter)
    for path, commands in scripts.items():
        for _, opcode, args in commands:
            patterns[opcode][tuple(t for t, _ in args)] += 1
    for opcode in sorted(patterns):
        common = ", ".join(f"{p}x{n}" for p, n in patterns[opcode].most_common(3))
        print(f"op {opcode:#06x}: {sum(patterns[opcode].values()):5d} uses  {common}")
