"""
Nintendo DS NFTR fonts: which characters a font has, text widths, word wrapping, and drawing text with the
font's own glyphs (for fitting new text in a game's text boxes, or making images in its style).

NFTR: "RTFN" header, then FINF (font info: offsets of CGLP glyphs, CWDH widths, first CMAP), CWDH (per glyph:
left bearing, glyph width, advance width) and a chain of CMAP blocks mapping characters to glyph indices.
"""
import struct
import unicodedata

# Letters NFKD doesn't reduce to ASCII
TRANSLITERATIONS = {"Ł": "L", "ł": "l", "Đ": "D", "đ": "d", "Ħ": "H", "ħ": "h", "ı": "i", "Ŀ": "L", "ŀ": "l",
                    "ẞ": "SS", "Ŧ": "T", "ŧ": "t"}


class Font:
    def __init__(self, data: bytes):
        finf = data.find(b"FNIF")
        if finf < 0:
            raise ValueError("not an NFTR font")
        self.data = data
        self.default_advance = data[finf + 0x0E]
        cglp_offset, cwdh_offset, cmap_offset = struct.unpack_from("<III", data, finf + 0x10)
        (self.cell_width, self.cell_height, self.glyph_size, self.baseline, _,
         self.bpp) = struct.unpack_from("<BBHBBB", data, cglp_offset)
        self.glyphs_offset = cglp_offset + 8
        first, last = struct.unpack_from("<HH", data, cwdh_offset)
        # glyph -> (left bearing, glyph width, advance)
        self.metrics = {first + i: tuple(data[cwdh_offset + 8 + 3 * i:cwdh_offset + 11 + 3 * i])
                        for i in range(last - first + 1)}
        advances = {glyph: metrics[2] for glyph, metrics in self.metrics.items()}
        self.glyph_index: dict[str, int] = {}
        self.advances: dict[str, int] = {}
        offset = cmap_offset
        while offset:
            first_char, last_char, kind, next_offset = struct.unpack_from("<HHII", data, offset)
            kind &= 0xFFFF
            body = offset + 12
            if kind == 0:
                first_glyph = struct.unpack_from("<H", data, body)[0]
                pairs = [(c, first_glyph + c - first_char) for c in range(first_char, last_char + 1)]
            elif kind == 1:
                pairs = [(c, struct.unpack_from("<H", data, body + 2 * (c - first_char))[0])
                         for c in range(first_char, last_char + 1)]
            else:
                count = struct.unpack_from("<H", data, body)[0]
                pairs = [struct.unpack_from("<HH", data, body + 2 + 4 * i) for i in range(count)]
            for char, glyph in pairs:
                if glyph != 0xFFFF:
                    self.glyph_index[chr(char)] = glyph
                    self.advances[chr(char)] = advances.get(glyph, self.default_advance)
            offset = next_offset

    def has(self, char: str) -> bool:
        return char in self.advances

    def width(self, text: str) -> int:
        return sum(self.advances.get(char, self.default_advance) for char in text)

    def clean(self, text: str) -> str:
        """Text with every character the font lacks replaced: accents dropped when that helps, else '?'."""
        out = []
        for char in text:
            if self.has(char) or char == "\n":
                out.append(char)
                continue
            plain = TRANSLITERATIONS.get(char) or "".join(
                c for c in unicodedata.normalize("NFKD", char) if not unicodedata.combining(c))
            out.append(plain if plain and all(self.has(c) for c in plain) else "?")
        return "".join(out)

    def wrap(self, text: str, max_width: int, max_lines: int) -> list[str]:
        """Word-wraps text into at most max_lines lines, cutting long words and ending with '…' if it doesn't fit."""
        lines: list[str] = []
        current = ""
        for word in text.split(" "):
            candidate = f"{current} {word}" if current else word
            if self.width(candidate) <= max_width:
                current = candidate
                continue
            if current:
                lines.append(current)
            current = word
            while self.width(current) > max_width:  # a single word longer than a line
                cut = len(current)
                while cut > 1 and self.width(current[:cut]) > max_width:
                    cut -= 1
                lines.append(current[:cut])
                current = current[cut:]
        if current:
            lines.append(current)
        if len(lines) > max_lines:
            last = lines[max_lines - 1]
            ellipsis = "…" if self.has("…") else "..."
            while last and self.width(last + ellipsis) > max_width:
                last = last[:-1]
            lines = lines[:max_lines - 1] + [last.rstrip() + ellipsis]
        return lines

    def render(self, text: str) -> list[list[int]]:
        """Rows of pixel levels (0 = background, 2 ** bpp - 1 = full ink) of the text drawn on one line."""
        width = self.width(text)
        rows = [[0] * width for _ in range(self.cell_height)]
        x = 0
        for char in text:
            glyph = self.glyph_index.get(char)
            if glyph is None:
                x += self.default_advance
                continue
            left, _, advance = self.metrics.get(glyph, (0, 0, self.default_advance))
            bits = self.data[self.glyphs_offset + glyph * self.glyph_size:
                             self.glyphs_offset + (glyph + 1) * self.glyph_size]
            for y in range(self.cell_height):
                for cx in range(self.cell_width):
                    bit = (y * self.cell_width + cx) * self.bpp
                    level = bits[bit >> 3] >> (8 - self.bpp - (bit & 7)) & ((1 << self.bpp) - 1)
                    if level and 0 <= x + left + cx < width:
                        rows[y][x + left + cx] = max(rows[y][x + left + cx], level)
            x += advance
        return rows
