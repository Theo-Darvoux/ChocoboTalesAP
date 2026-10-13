"""
The Archipelago card the storybook result screen shows for an Archipelago item. No Archipelago imports.

The result screen (overlay 53) draws a reward card from three things, all keyed by the card's image id:
- /card/card_<id>.pbg.z: the whole card face (frame, picture, icons, rarity), a D2KP container of an NCLR palette
  and 8 bpp NCGR tiles laid out by the shared /card/card.NSCR.z
- /card/<lang>/name_<id>.NCGR.z: the pre-drawn name (64x32, 8 bpp, drawn with the card's palette)
- an entry in /card/<lang>/card.bin.z: image id, card number, then offsets of the monster name, ability name,
  a caption and the description text (UTF-8, 0x1C n switches colors)
The Archipelago card gets its own image id and files, and an entry in a copy of card.bin that only overlay 53
reads (reward_patch points its path there). Its card number is 0: a type 3 reward sets flag 0x400 + number, and
the patch blocks flag 0x400 too.

Nothing of the game is shipped: the card is built from the player's ROM when patching. Its frame is the Chocobo
promo card's, its picture is the Archipelago logo drawn here as pixel art, and its name is written with letters cut
out of the game's own pre-drawn card names.
"""
import math
import struct

from .font import Font
from .nds import NDSRom, lz10_compress
from .text_patch import LANGUAGES

IMAGE_ID = 2700
NUMBER = 0
CARD_BIN_PATH = "card\\&\\apcd.bin.z"  # "&" is the language folder; same length as the vanilla path

MONSTER = "Archipelago"
ABILITY = {"en": "AP Item", "fr": "Objet AP", "de": "AP-Objekt", "it": "Oggetto AP", "es": "Objeto AP"}
DESCRIPTION = {
    "en": "A treasure from another world. The message below says what it is.",
    "fr": "Un trésor venu d'un autre monde. Le message ci-dessous dit ce que c'est.",
    "de": "Ein Schatz aus einer anderen Welt. Die Nachricht unten verrät, was es ist.",
    "it": "Un tesoro da un altro mondo. Il messaggio qui sotto dice cos'è.",
    "es": "Un tesoro de otro mundo. El mensaje de abajo dice qué es.",
}
DESCRIPTION_WIDTH = 100
DESCRIPTION_LINES = 8
RED, NORMAL = "\x1c\x04", "\x1c\x01"

TEMPLATE_IMAGE_ID = 2600  # the Chocobo promo card: plain icon circles and a holographic frame
CARD_WIDTH, CARD_HEIGHT = 128, 192
NAME_WIDTH, NAME_HEIGHT = 64, 32
NAME_TOP_ROWS, NAME_BOTTOM_ROWS = (0, 11), (11, 28)  # monster name, ability name
NAME_RAMP = range(0xE0, 0xF0)  # palette entries of the black-to-white ramp the names are drawn with

# The Archipelago logo: six orbs in a ring, drawn bottom to top, in a 512-unit square with radius-100 orbs.
# (centre, (shade, base, light) colors)
LOGO_ORBS = (
    ((256, 100), ((176, 48, 72), (232, 88, 104), (255, 168, 168))),  # red
    ((110, 182), ((208, 152, 32), (248, 216, 72), (255, 248, 176))),  # yellow
    ((400, 182), ((40, 136, 64), (96, 200, 88), (184, 240, 152))),  # green
    ((110, 325), ((56, 64, 160), (104, 120, 224), (176, 192, 255))),  # blue
    ((400, 325), ((152, 72, 160), (216, 128, 208), (248, 200, 240))),  # pink
    ((256, 410), ((200, 96, 48), (248, 152, 88), (255, 216, 168))),  # orange
)
LOGO_ORB_RADIUS = 100
LOGO_CENTER = (64, 51)  # in card pixels: between the top icon circle and the name box
LOGO_SIZE = 42  # pixels across
BLACK, WHITE = (0, 0, 0), (255, 255, 255)
GLOW = (255, 255, 236)
RAYS = ((255, 240, 184), (255, 222, 128))
RAY_COUNT = 16
GLOW_RADIUS = 27


def card_path(image_id: int) -> str:
    return f"/card/card_{image_id:04d}.pbg.z"


def name_path(language: str, image_id: int) -> str:
    return f"/card/{language}/name_{image_id:04d}.NCGR.z"


# ---- the card picture ------------------------------------------------------------------------------------------

def in_picture(x: int, y: int) -> bool:
    """Whether a card pixel belongs to the picture window (checked against all 127 cards: the pixels that differ)."""
    if not (16 <= y <= 75 and 16 <= x <= 111):
        return False
    if math.hypot(x + 0.5 - 64, y + 0.5 - 15.5) <= 14.6:  # the top icon circle
        return False
    if y == 16:
        return 17 <= x <= 110
    if y == 72:
        return not 32 <= x <= 95  # the name box
    if y == 73:
        return not 31 <= x <= 96
    if y == 74:
        return 18 <= x <= 29 or 98 <= x <= 109
    if y == 75:
        return 21 <= x <= 28 or 99 <= x <= 106
    return True


def logo_pixel(x: int, y: int) -> tuple[int, int, int]:
    """Color of a picture pixel: the logo on a sunburst."""
    scale = LOGO_SIZE / 512
    fx, fy = x + 0.5, y + 0.5
    radius = LOGO_ORB_RADIUS * scale
    centers = [((ox - 256) * scale + LOGO_CENTER[0], (oy - 256) * scale + LOGO_CENTER[1]) for (ox, oy), _ in LOGO_ORBS]
    distances = [math.hypot(fx - cx, fy - cy) for cx, cy in centers]
    for i in reversed(range(len(LOGO_ORBS))):  # topmost orb first
        distance = distances[i]
        if radius < distance <= radius + 1:
            if any(d <= radius for d in distances[:i]):
                return WHITE  # the gap a higher orb leaves on a lower one
            continue
        if distance <= radius:
            if distance > radius - 1:
                return BLACK
            shade, base, light = LOGO_ORBS[i][1]
            u, v = (fx - centers[i][0]) / radius, (fy - centers[i][1]) / radius
            if (u + 0.42) ** 2 + (v + 0.46) ** 2 < 0.035:
                return WHITE
            if (u + 0.3) ** 2 + (v + 0.3) ** 2 < 0.16:
                return light
            if u * 0.55 + v * 0.83 > 0.42:
                return shade
            return base
    if math.hypot(fx - LOGO_CENTER[0], fy - LOGO_CENTER[1]) < GLOW_RADIUS:
        return GLOW
    angle = math.atan2(fy - LOGO_CENTER[1], fx - LOGO_CENTER[0])
    return RAYS[int((angle + math.pi) / (2 * math.pi) * RAY_COUNT) % 2]


def rgb555(color: tuple[int, int, int]) -> int:
    r, g, b = ((c * 31 + 127) // 255 for c in color)
    return r | g << 5 | b << 10


class Pbg:
    """A D2KP container holding an NCLR palette and 8 bpp NCGR tiles, edited in place."""

    def __init__(self, data: bytes):
        self.data = bytearray(data)
        ttlp = self.data.find(b"TTLP")
        size, offset = struct.unpack_from("<II", self.data, ttlp + 0x10)
        self.palette_offset = ttlp + 8 + offset
        self.palette = list(struct.unpack_from(f"<{min(size, 512) // 2}H", self.data, self.palette_offset))
        rahc = self.data.find(b"RAHC")
        _, _, depth, _, _, size, offset = struct.unpack_from("<HHIIIII", self.data, rahc + 8)
        if depth != 4:
            raise ValueError("expected 8 bpp tiles")
        self.tiles_offset = rahc + 8 + offset
        self.tiles_size = size

    def to_bytes(self) -> bytes:
        struct.pack_into(f"<{len(self.palette)}H", self.data, self.palette_offset, *self.palette)
        return bytes(self.data)


def card_pixel_offsets(screen: bytes) -> dict[tuple[int, int], int]:
    """Card pixel -> offset of its byte in the NCGR tile data, through the shared card.NSCR layout."""
    nrcs = screen.find(b"NRCS")
    width = struct.unpack_from("<H", screen, nrcs + 8)[0] // 8
    offsets = {}
    for ty in range(CARD_HEIGHT // 8):
        for tx in range(CARD_WIDTH // 8):
            entry = struct.unpack_from("<H", screen, nrcs + 0x14 + 2 * (ty * width + tx))[0]
            if entry & 0xFC00:
                raise ValueError("unexpected flipped or banked tile in card.NSCR")
            for y in range(8):
                for x in range(8):
                    offsets[tx * 8 + x, ty * 8 + y] = (entry & 0x3FF) * 64 + y * 8 + x
    return offsets


def card_image(rom: NDSRom) -> bytes:
    card = Pbg(rom.read(card_path(TEMPLATE_IMAGE_ID)))
    offsets = card_pixel_offsets(rom.read("/card/card.NSCR.z"))
    tiles = card.data[card.tiles_offset:card.tiles_offset + card.tiles_size]
    picture = {pixel for pixel in offsets if in_picture(*pixel)}
    if len({offsets[pixel] for pixel in picture}) != len(picture):
        raise ValueError("the picture shares tiles with something else")

    kept = {tiles[offset] for pixel, offset in offsets.items() if pixel not in picture}
    kept |= {0, *NAME_RAMP}
    free = [index for index in range(len(card.palette)) if index not in kept]
    by_color = {card.palette[index]: index for index in sorted(kept, reverse=True)}
    for pixel in sorted(picture):
        color = rgb555(logo_pixel(*pixel))
        if color not in by_color:
            if not free:
                raise ValueError("no palette entries left for the Archipelago card")
            index = free.pop(0)
            card.palette[index] = color
            by_color[color] = index
        tiles[offsets[pixel]] = by_color[color]
    card.data[card.tiles_offset:card.tiles_offset + card.tiles_size] = tiles
    return card.to_bytes()


# ---- the card name ---------------------------------------------------------------------------------------------

def _card_names(rom: NDSRom, language: str) -> dict[int, tuple[str, str]]:
    """image id -> (monster, ability) from card.bin"""
    data = rom.read(f"/card/{language}/card.bin.z")
    header = struct.unpack_from("<10I", data, 0)

    def text(section: int, offset: int) -> str:
        start = header[2 * section + 1] + offset
        return data[start:data.index(b"\0", start)].decode("utf-8")

    names = {}
    for i in range(header[0]):
        image_id, _, monster, ability, _, _ = struct.unpack_from("<6I", data, header[1] + 24 * i)
        names[image_id] = (text(1, monster), text(2, ability))
    return names


def _palette_rgb(palette: list[int]) -> list[tuple[int, int, int]]:
    return [((c & 31) * 255 // 31, (c >> 5 & 31) * 255 // 31, (c >> 10 & 31) * 255 // 31) for c in palette]


def _ncgr_pixels(data: bytes) -> tuple[int, list[list[int]]]:
    """(offset of the tile data, rows of palette indices) of a 64x32 8 bpp name NCGR"""
    rahc = data.find(b"RAHC")
    height, width, depth, _, _, _, offset = struct.unpack_from("<HHIIIII", data, rahc + 8)
    if (width * 8, height * 8, depth) != (NAME_WIDTH, NAME_HEIGHT, 4):
        raise ValueError("unexpected name image")
    start = rahc + 8 + offset
    rows = [[0] * NAME_WIDTH for _ in range(NAME_HEIGHT)]
    for tile in range(width * height):
        tx, ty = tile % width, tile // width
        for y in range(8):
            for x in range(8):
                rows[ty * 8 + y][tx * 8 + x] = data[start + tile * 64 + y * 8 + x]
    return start, rows


def _segments(rows: list[list[int]], line: tuple[int, int], threshold: int) -> list[tuple[int, int]]:
    columns = [max(rows[y][x] for y in range(*line)) for x in range(NAME_WIDTH)] + [0]
    segments, start = [], None
    for x, value in enumerate(columns):
        if value >= threshold and start is None:
            start = x
        elif value < threshold and start is not None:
            segments.append((start, x))
            start = None
    return segments


def harvest_letters(rom: NDSRom, languages: tuple[str, ...] = LANGUAGES
                    ) -> dict[tuple[int, str], list[list[list[int]]]]:
    """
    (line, letter) -> letter images (columns of brightness 0-255) cut out of the game's pre-drawn card names, for
    line 0 (monster names) and 1 (ability names). A name's line is split at dark columns; it is only used when that
    gives exactly one piece per letter. A letter no such name has falls back on the first piece of the names it starts
    whose letters touch, when that piece is no wider than a letter: the USA release's only monster name with an "A"
    is the condensed "Adamantoise".
    """
    palettes = {}
    letters: dict[tuple[int, str], list[list[list[int]]]] = {}
    first_letters: dict[tuple[int, str], list[list[list[int]]]] = {}
    for language in languages:
        for image_id, texts in _card_names(rom, language).items():
            if image_id not in palettes:
                palettes[image_id] = _palette_rgb(Pbg(rom.read(card_path(image_id))).palette)
            palette = palettes[image_id]
            _, indices = _ncgr_pixels(rom.read(name_path(language, image_id)))
            rows = [[(palette[i][0] * 30 + palette[i][1] * 59 + palette[i][2] * 11) // 100 for i in row]
                    for row in indices]
            for line, (rows_range, text) in enumerate(zip((NAME_TOP_ROWS, NAME_BOTTOM_ROWS), texts)):
                chars = [c for c in text if c != " "]
                for threshold in range(240, 63, -16):
                    segments = _segments(rows, rows_range, threshold)
                    if len(segments) == len(chars):
                        break
                else:
                    segments = _segments(rows, rows_range, 240)
                    if chars and segments:
                        start, end = segments[0]
                        first_letters.setdefault((line, chars[0]), []).append(
                            [[rows[y][x] for y in range(*rows_range)] for x in range(start, end)])
                    continue
                for char, (start, end) in zip(chars, segments):
                    columns = [[rows[y][x] for y in range(*rows_range)]
                               for x in range(max(0, start - 1), min(NAME_WIDTH, end + 1))]
                    while columns and max(columns[0]) < 40:
                        columns.pop(0)
                    while columns and max(columns[-1]) < 40:
                        columns.pop()
                    letters.setdefault((line, char), []).append(columns)
    for (line, char), pieces in first_letters.items():
        widest = max((len(columns) for (other_line, _), cut in letters.items() if other_line == line
                      for columns in cut), default=0)
        pieces = [columns for columns in pieces if len(columns) <= widest]
        if (line, char) not in letters and pieces:
            letters[(line, char)] = pieces
    return letters


def _letter(letters: dict, line: int, char: str) -> list[list[int]]:
    """
    The usual drawing of a letter: among its cut-outs of the most common width (the uncondensed one), the median of
    each pixel, which leaves out the odd mis-cut piece.
    """
    candidates = letters[(line, char)]
    widths: dict[int, int] = {}
    for columns in candidates:
        widths[len(columns)] = widths.get(len(columns), 0) + 1
    width = max(widths, key=lambda w: (widths[w], w))
    same = [columns for columns in candidates if len(columns) == width]
    height = len(same[0][0])
    return [[sorted(columns[x][y] for columns in same)[len(same) // 2] for y in range(height)] for x in range(width)]


def _write_line(letters: dict, line: int, text: str, height: int, max_width: int) -> list[list[int]]:
    for gap in (1, 0):
        columns: list[list[int]] = []
        for char in text:
            columns += [[0] * height] * 3 if char == " " else _letter(letters, line, char) + [[0] * height] * gap
        columns = columns[:len(columns) - gap] if gap and columns else columns
        if len(columns) <= max_width:
            return columns
    return [columns[i * len(columns) // max_width] for i in range(max_width)]  # condense, as the game does


def name_image(rom: NDSRom, letters: dict, language: str, ramp: list[tuple[int, int, int]]) -> bytes:
    data = bytearray(rom.read(name_path(language, TEMPLATE_IMAGE_ID)))
    start, rows = _ncgr_pixels(bytes(data))
    brightness = [[0] * NAME_WIDTH for _ in range(NAME_BOTTOM_ROWS[1])]
    top = _write_line(letters, 0, MONSTER, NAME_TOP_ROWS[1] - NAME_TOP_ROWS[0], NAME_WIDTH - 2)
    bottom = _write_line(letters, 1, ABILITY[language], NAME_BOTTOM_ROWS[1] - NAME_BOTTOM_ROWS[0], NAME_WIDTH - 2)
    for columns, x0, y0 in ((top, 2, NAME_TOP_ROWS[0]), (bottom, (NAME_WIDTH - len(bottom)) // 2, NAME_BOTTOM_ROWS[0])):
        for x, column in enumerate(columns):
            for y, value in enumerate(column):
                brightness[y0 + y][x0 + x] = max(brightness[y0 + y][x0 + x], value)
    levels = [sum(c) // 3 for c in ramp]
    for y in range(NAME_BOTTOM_ROWS[1]):
        for x in range(NAME_WIDTH):
            value = brightness[y][x]
            index = NAME_RAMP[min(range(len(levels)), key=lambda i: abs(levels[i] - value))]
            tile = (y // 8) * (NAME_WIDTH // 8) + x // 8
            data[start + tile * 64 + (y % 8) * 8 + x % 8] = index
    return bytes(data)


# ---- card.bin --------------------------------------------------------------------------------------------------

def extend_card_bin(data: bytes, monster: str, ability: str, description: str) -> bytes:
    """card.bin with one more entry, for the Archipelago card, at the end of the card table."""
    header = list(struct.unpack_from("<10I", data, 0))
    count, table = header[0], header[1]
    entry_end = table + 24 * count
    out = bytearray(data[:entry_end]) + bytes(24) + bytearray(data[entry_end:])
    for section in range(1, 5):
        header[2 * section + 1] += 24
    header[0] = count + 1
    struct.pack_into("<10I", out, 0, *header)

    def append(text: str, section: int) -> int:
        offset = len(out) - header[2 * section + 1]
        out.extend(text.encode("utf-8") + b"\0")
        return offset

    entry = (IMAGE_ID, NUMBER, append(monster, 1), append(ability, 2), append("", 3), append(description, 4))
    struct.pack_into("<6I", out, entry_end, *entry)
    while len(out) % 4:
        out.append(0)
    return bytes(out)


def new_files(rom: NDSRom, languages: tuple[str, ...] = LANGUAGES) -> dict[str, bytes]:
    card = card_image(rom)
    ramp = _palette_rgb(Pbg(card).palette)[NAME_RAMP.start:NAME_RAMP.stop]
    letters = harvest_letters(rom, languages)
    card_font = Font(rom.read("/card/cardfont.nftr.z"))
    files = {card_path(IMAGE_ID): lz10_compress(card)}
    for language in languages:
        description = "\n".join(card_font.wrap(card_font.clean(DESCRIPTION[language]),
                                                DESCRIPTION_WIDTH, DESCRIPTION_LINES))
        card_bin = extend_card_bin(rom.read(f"/card/{language}/card.bin.z"), MONSTER, ABILITY[language],
                                   f"{RED}{MONSTER}{NORMAL}\n{description}")
        files[f"/card/{language}/{CARD_BIN_PATH.rsplit(chr(92), 1)[1]}"] = lz10_compress(card_bin)
        files[name_path(language, IMAGE_ID)] = lz10_compress(name_image(rom, letters, language, ramp))
    return files
