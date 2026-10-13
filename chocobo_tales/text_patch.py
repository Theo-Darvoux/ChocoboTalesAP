"""
Rewrites the game's reward texts (and other data files) in place. No Archipelago imports.

File formats (all found by reading the ROM, see NOTES.md):
- Field event scripts (.act): a u32 string-area offset, commands, then the string area. A per-language text
  argument (type 0x40) holds an offset, relative to the string area, of 7 u32 offsets (same base) to UTF-8
  strings: Japanese, English, French, German, Italian, Spanish, Japanese.
- Storybook result data (/mgame/result/<lang>/MGNNN.dat.z, LZ10): 7 x (u32 goal text, u32 record count,
  u32 records), then records of (u32 type, u32 text, u32 value). Text offsets are absolute UTF-8 strings.
- Text lists (.ptx): u32 count, then (u32 byte length, UTF-16LE string ending in a 0 code unit). 0x1B starts
  a formatting escape: 0x1B 'G' ... 0x1B 0x1B colors the text, 0x1B 'C' draws the card icon.
"""
import struct

LANGUAGES = ("en", "fr", "de", "it", "es")
# Index of each language in an .act text table; entries 0 and 6 are Japanese and are never shown in the EU game
ACT_LANGUAGE_INDEX = {"en": 1, "fr": 2, "de": 3, "it": 4, "es": 5}
ACT_TEXT_ARG = 0x40
# Opcodes whose type 0x40 arguments are text: 0x0B message, 0x24 three-way choice. (A condition's expression
# offset can also be 0x40 by coincidence.)
ACT_TEXT_OPCODES = (0x0B, 0x24)


def _align(buffer: bytearray) -> None:
    while len(buffer) % 4:
        buffer.append(0)


class ActScript:
    """A field event script whose per-language texts can be replaced."""

    def __init__(self, data: bytes):
        self.data = bytearray(data)
        self.base = struct.unpack_from("<I", data, 0)[0]

    def commands(self) -> list[tuple[int, int, list[tuple[int, int]]]]:
        """[(offset, opcode, [(argument type, value), ...])]"""
        commands = []
        p = 4
        while p < self.base:
            opcode, length = struct.unpack_from("<HH", self.data, p)
            if length < 4:
                raise ValueError(f"bad command length {length} at {p:#x}")
            args = [struct.unpack_from("<HxxI", self.data, q) for q in range(p + 4, p + length - 7, 8)]
            commands.append((p, opcode, args))
            p += length
        return commands

    def text_tables(self) -> list[int]:
        """String-area-relative offsets of every per-language text table, in command order."""
        return [value for _, opcode, args in self.commands() if opcode in ACT_TEXT_OPCODES
                for kind, value in args if kind == ACT_TEXT_ARG]

    def text(self, table: int, language: str) -> str:
        offset = self.base + struct.unpack_from("<I", self.data, self.base + table + 4 * ACT_LANGUAGE_INDEX[language])[0]
        return self.data[offset:self.data.index(0, offset)].decode("utf-8", "surrogateescape")

    def _append_string(self, text: str) -> int:
        _align(self.data)
        offset = len(self.data) - self.base
        self.data += text.encode("utf-8") + b"\0"
        return offset

    def set_text(self, table: int, texts: dict[str, str]) -> None:
        """Points the table's entries for these languages at new strings (English also replaces Japanese)."""
        for language, text in texts.items():
            offset = self._append_string(text)
            indices = [ACT_LANGUAGE_INDEX[language]] + ([0, 6] if language == "en" else [])
            for index in indices:
                struct.pack_into("<I", self.data, self.base + table + 4 * index, offset)

    def to_bytes(self) -> bytes:
        _align(self.data)
        return bytes(self.data)


class ResultData:
    """A storybook's result screen data (MGNNN.dat, decompressed)."""
    GOALS = 7

    def __init__(self, data: bytes):
        self.data = bytearray(data)

    def records(self, goal: int) -> list[tuple[int, int, int]]:
        """[(record offset, type, value)]"""
        _, count, start = struct.unpack_from("<III", self.data, goal * 12)
        return [(start + 12 * i, *struct.unpack_from("<I4xI", self.data, start + 12 * i)) for i in range(count)]

    def record_text(self, record_offset: int) -> str:
        offset = struct.unpack_from("<I", self.data, record_offset + 4)[0]
        return self.data[offset:self.data.index(0, offset)].decode("utf-8", "surrogateescape")

    def _append_string(self, text: str) -> int:
        offset = len(self.data)
        self.data += text.encode("utf-8") + b"\0"
        return offset

    def set_record(self, record_offset: int, text: str | None = None, value: int | None = None) -> None:
        if text is not None:
            struct.pack_into("<I", self.data, record_offset + 4, self._append_string(text))
        if value is not None:
            struct.pack_into("<I", self.data, record_offset + 8, value)

    def replace_records(self, goal: int, records: list[tuple[int, int | str, int]]) -> None:
        """Gives a goal a new record list: (type, existing text offset or new text, value)."""
        resolved = [(kind, self._append_string(text) if isinstance(text, str) else text, value)
                    for kind, text, value in records]
        _align(self.data)
        start = len(self.data)
        for record in resolved:
            self.data += struct.pack("<III", *record)
        struct.pack_into("<II", self.data, goal * 12 + 4, len(resolved), start)

    def raw_records(self, goal: int) -> list[tuple[int, int, int]]:
        """[(type, text offset, value)]"""
        _, count, start = struct.unpack_from("<III", self.data, goal * 12)
        return [struct.unpack_from("<III", self.data, start + 12 * i) for i in range(count)]

    def to_bytes(self) -> bytes:
        _align(self.data)
        return bytes(self.data)


def read_ptx(data: bytes) -> list[str]:
    """Raw strings (escapes kept, terminator removed)."""
    count = struct.unpack_from("<I", data, 0)[0]
    p = 4
    strings = []
    for _ in range(count):
        length = struct.unpack_from("<I", data, p)[0]
        strings.append(data[p + 4:p + 4 + length].decode("utf-16le").rstrip("\0"))
        p += 4 + length
    return strings


def write_ptx(strings: list[str]) -> bytes:
    out = bytearray(struct.pack("<I", len(strings)))
    for text in strings:
        encoded = (text + "\0").encode("utf-16le")
        out += struct.pack("<I", len(encoded)) + encoded
    return bytes(out)
