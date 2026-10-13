"""
Extracts the static game data used by the Chocobo Tales apworld straight from the ROM and writes
`chocobo_tales/data.py`. Uses NDSTools (../../NDSTools) to read the ROM.

Usage:
    python3 -I tools/extract_rom_data.py <rom.nds> <output data.py>

What is read:
  /card/en/card.bin.z                    -> the 127 Pop-up Duel cards (number, image id, monster, ability)
  /mgentryphase/text/en/secret/mgNNN.ptx -> the 7 hidden goals of each of the 16 storybook minigames
  /mgentryphase/text/en/secret/clNNN.ptx -> the reward text for each of those goals (same index order)
  /mgame/result/en/MGNNN.dat.z           -> the reward records the game actually applies for each goal
  /bookread/txt/en/B-C-title.txt.z       -> storybook chapter titles (B = book, C = chapter)
  /field/50/50/skipN[pb].act             -> developer "skip to chapter N (pre-boss)" scripts: which storybooks
                                            are available at each point of the story
  /field/*/*/*.act                       -> every pop-up card a field script gives, with its message and flags
"""
import importlib.util
import re
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "NDSTools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ndstools.rom import NDSRom  # noqa: E402
from act import parse as parse_script  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "text_patch", Path(__file__).resolve().parent.parent / "chocobo_tales" / "text_patch.py")
text_patch = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(text_patch)

# Each storybook has a block of 32 flags at 0x7C0 + 32 * (book - 1); +0x23 is set once the book is available
STORYBOOK_AVAILABLE_FLAG = 0x7E3
# Developer skip scripts in story order, with the chapter whose storybooks they show. skipN is the state right after
# chapter N - 1's Bebuzzu duel (it has that scene's story flags, e.g. 0x34 / 0x3F from 45/51/a3.act for skip3), so
# its books were found in chapter N - 1; skipNpb is a point inside chapter N. Their chapter flags (0x43 + 2(N - 2))
# aren't a reliable marker: skip3 / skip4 leave out the flag the boss scene sets, skip5 has it.
# The boss tile's storybook proves the convention: Gimmick4B1 (book 8, skip3), Gimmick5B1 (book 10, skip4) and
# Gimmick6B1 (book 12, skip5) each start the scene spawning the chapter's Bebuzzu duel.
SKIP_SCRIPTS = [("skip2", 1), ("skip2pb", 2), ("skip3", 2), ("skip3pb", 3), ("skip4", 3), ("skip4pb", 4),
                ("skip5", 4), ("skip5pb", 5)]
# Storybooks no skip script makes available: book 14's book object (47/45 map.act) is created once Gimmick8A1
# (book 15) sets flag 0x60, which skip5pb has; book 16's Gimmick8B1 starts the chapter 5 Bebuzzu scene (44/45/a1.act)
FIELD_ONLY_BOOKS = {14: 5, 16: 5}
LAST_CHAPTER = 6

# Reward record types in /mgame/result/*/MGNNN.dat (see NOTES.md for the code that applies them)
REWARD_TYPES = {
    0: "battle_levels",  # value: bitmask, bit L = battle mode level L unlocked
    1: "epilogue",       # value: epilogue number
    2: "trial_mode",     # value unused
    3: "card",           # value: card image id
    4: "chocobo",        # value: chocobo friend id
    5: "battle_levels",  # same as 0, used for a book's first clear
}


def read_ptx(data: bytes) -> list[str]:
    """.ptx = u32 count, then (u32 byte length, UTF-16LE string) entries. 0x1B is a formatting escape."""
    count = struct.unpack_from("<I", data, 0)[0]
    p = 4
    strings = []
    for _ in range(count):
        length = struct.unpack_from("<I", data, p)[0]
        p += 4
        text = data[p:p + length].decode("utf-16le")
        p += length
        text = text.replace("\x1b", "").replace("\x00", "").replace("﻿", "").replace("　", " ")
        strings.append(re.sub(r"\s*\n\s*", " ", text).strip())
    return strings


def read_cards(data: bytes) -> list[tuple[int, int, str, str]]:
    """
    card.bin header: 5 x (u32 count, u32 offset) -> card table, monster names, ability names, misc, descriptions.
    Card table entries are 24 bytes: image id, card number, monster name offset, ability name offset, 2 more fields.
    Returns (number, image id, monster, ability) sorted by number.
    """
    card_count, card_table, _, monster_names, _, ability_names = struct.unpack_from("<6I", data, 0)

    def string_at(base: int, offset: int) -> str:
        end = data.index(b"\0", base + offset)
        return data[base + offset:end].decode("latin1")

    cards = []
    for i in range(card_count):
        image_id, number, monster_off, ability_off, _, _ = struct.unpack_from("<6I", data, card_table + i * 24)
        cards.append((number, image_id, string_at(monster_names, monster_off), string_at(ability_names, ability_off)))
    return sorted(cards)


def read_rewards(data: bytes) -> list[list[tuple[str, int]]]:
    """
    MGNNN.dat: u32 text offset, then 7 x (u32 record count, u32 records offset, u32 text offset), then records of
    (u32 type, u32 text offset, u32 value). Entry i's records are goal i's rewards.
    """
    rewards = []
    for goal in range(7):
        count, records, _ = struct.unpack_from("<III", data, 4 + goal * 12)
        goal_rewards = []
        for record in range(count):
            kind, _, value = struct.unpack_from("<III", data, records + record * 12)
            goal_rewards.append((REWARD_TYPES[kind], value))
        rewards.append(goal_rewards)
    return rewards


def parse_reward_text(text: str) -> tuple[str, str | int | None]:
    """Turns 'CGObtained 034 Cactuar - Photosynthesis' / 'GRescued Sweenie' / ... into (kind, value)."""
    text = text.lstrip("CG").strip()
    if not text:
        return "nothing", None
    if match := re.fullmatch(r"Obtained (\d+) .*", text):
        return "card", int(match.group(1))
    if match := re.fullmatch(r"Rescued (\w+)", text):
        return "chocobo", match.group(1)
    if match := re.fullmatch(r"Unlocked Epilogue (\d)", text):
        return "epilogue", int(match.group(1))
    if text == "Unlocked Trial Mode":
        return "mode", "Trial"
    if text == "Unlocked Battle Mode":
        return "mode", "Battle"
    raise ValueError(f"Unknown reward text: {text!r}")


CARD_FLAGS = range(0x401, 0x480)  # 0x400 + card number
MEDAL_FLAGS = range(0x9F9, 0xA40)  # 0x9F8 + 3 * (microgame - 1) + 1 (Silver) / 2 (Gold)
# A flag reference inside a condition expression: u32 type 4 (flag field), then flag | width << 16
CONDITION_FLAG = re.compile(rb"\x04\x00\x00\x00(..)\x01\x00", re.S)


def read_field_card_grants(rom: NDSRom) -> list[tuple]:
    """
    Every pop-up card a field event script gives: (script, text table, card number, event flag, medal flag or 0,
    condition flags). The text table is the "You obtain the ... pop-up card" message. The event flag is the flag the
    script sets right before the card's ownership flag, so it records that this gift happened. Microgame result
    scripts guard each card's message with the medal flag that earns it.
    """
    grants = []
    for path in sorted(rom.files):
        if not path.endswith(".act") or path.startswith("/field/50/50/kuroma") or path.startswith("/field/50/50/skip"):
            continue
        script = text_patch.ActScript(rom.read(path))
        messages: dict[int, tuple[int, tuple[int, ...]]] = {}
        condition: tuple[int, ...] = ()
        last_flag = 0
        for _, opcode, args in script.commands():
            if opcode == 0x05 and args:
                start = script.base + args[0][0]
                condition = tuple(struct.unpack("<H", m.group(1))[0]
                                  for m in CONDITION_FLAG.finditer(bytes(script.data[start:start + 80])))
            elif opcode == 0x0B and args and args[0][0] == text_patch.ACT_TEXT_ARG:
                text = script.text(args[0][1], "en")
                if match := re.match(r"You obtain the\n(\d{3}) ", text):
                    messages[int(match.group(1))] = (args[0][1], condition)
            elif opcode == 0x00 and args and args[0][0] == 4 and args[0][1] >> 16 == 1:
                flag = args[0][1] & 0xFFFF
                if flag in CARD_FLAGS:
                    card = flag - 0x400
                    table, guard = messages.pop(card)
                    medal = next((f for f in guard if f in MEDAL_FLAGS and (f - 0x9F8) % 3), 0)
                    grants.append((path, table, card, last_flag, medal, guard))
                else:
                    last_flag = flag
        assert not messages, (path, messages)
    return grants


def main(rom_path: str, out_path: str) -> None:
    rom = NDSRom(rom_path)
    cards = read_cards(rom.read("/card/en/card.bin.z"))
    card_number_by_image = {image_id: number for number, image_id, _, _ in cards}

    books = []
    records = []
    friend_ids: dict[str, int] = {}
    for book in range(1, 17):
        conditions = read_ptx(rom.read(f"/mgentryphase/text/en/secret/mg{book:03d}.ptx"))
        reward_texts = read_ptx(rom.read(f"/mgentryphase/text/en/secret/cl{book:03d}.ptx"))
        assert len(conditions) == len(reward_texts) == 7, book
        goals = [(cond, *parse_reward_text(reward)) for cond, reward in zip(conditions, reward_texts)]
        book_records = read_rewards(rom.read(f"/mgame/result/en/MG{book:03d}.dat.z"))
        # Cross-check the shown reward text against the records the game applies, and pick up chocobo friend ids
        for (_, kind, value), goal_records in zip(goals, book_records):
            if kind == "card":
                assert ("card", value) in [(k, card_number_by_image[v]) for k, v in goal_records if k == "card"], book
            elif kind == "chocobo":
                friend_ids[str(value)] = next(v for k, v in goal_records if k == "chocobo")
        books.append(goals)
        records.append([[(k, card_number_by_image[v] if k == "card" else v) for k, v in goal_records]
                        for goal_records in book_records])

    storybook_chapters = {}
    for script, chapter in SKIP_SCRIPTS:
        for _, opcode, args in parse_script(rom.read(f"/field/50/50/{script}.act")):
            if opcode == 0 and args[0][0] == 4 and args[1][1]:
                flag = args[0][1] & 0xFFFF
                book = (flag - STORYBOOK_AVAILABLE_FLAG) // 32 + 1
                if (flag - STORYBOOK_AVAILABLE_FLAG) % 32 == 0 and 1 <= book <= 16:
                    storybook_chapters.setdefault(book, chapter)
    for book, chapter in FIELD_ONLY_BOOKS.items():
        assert book not in storybook_chapters, book
        storybook_chapters[book] = chapter
    for book in range(1, 17):
        storybook_chapters.setdefault(book, LAST_CHAPTER)

    chapters = {}
    for path in rom.files:
        if match := re.fullmatch(r"/bookread/txt/en/(\d+)-(\d+)-title\.txt\.z", path):
            # EU stores UTF-16LE without a BOM; US adds the BOM. Decode both as UTF-16LE.
            text = rom.read(path).removeprefix(b"\xff\xfe").decode("utf-16le").rstrip("\0").strip()
            chapters[(int(match.group(1)), int(match.group(2)))] = text

    grants = read_field_card_grants(rom)

    lines = [
        '"""',
        f"Generated by tools/extract_rom_data.py from {rom.title} ({rom.game_code}). Do not edit by hand.",
        '"""',
        "",
        "# (card number, monster, ability). The card number is the one shown in the in-game collection.",
        "CARDS: list[tuple[int, str, str]] = [",
        *(f"    ({number}, {monster!r}, {ability!r})," for number, _, monster, ability in cards),
        "]",
        "",
        "# STORYBOOK_GOALS[book - 1] = 7 x (goal text, vanilla reward kind, vanilla reward value), as the game lists them",
        "# Reward kinds: card (card number), chocobo (name), epilogue (number), mode (Trial / Battle), nothing",
        "STORYBOOK_GOALS: list[list[tuple[str, str, str | int | None]]] = [",
    ]
    for goals in books:
        lines.append("    [")
        lines.extend(f"        {goal!r}," for goal in goals)
        lines.append("    ],")
    lines += [
        "]",
        "",
        "# STORYBOOK_REWARD_RECORDS[book - 1][goal] = what the game applies when the goal is done: (kind, value) with",
        "# kinds battle_levels (bitmask, bit L = level L), epilogue (number), trial_mode, card (card number),",
        "# chocobo (friend id)",
        "STORYBOOK_REWARD_RECORDS: list[list[list[tuple[str, int]]]] = [",
        *(f"    {book_records!r}," for book_records in records),
        "]",
        "",
        "# Rescued chocobo name -> friend id (its flag is 0x3E6 + id)",
        f"CHOCOBO_FRIEND_IDS: dict[str, int] = {friend_ids!r}",
        "",
        "# Storybook -> story chapter (1-6) it becomes available in, from the developer skip scripts",
        "STORYBOOK_STORY_CHAPTER: dict[int, int] = {",
        *(f"    {book}: {storybook_chapters[book]}," for book in sorted(storybook_chapters)),
        "}",
        "",
        "# Every pop-up card a field script gives: (script, message text table, card number, event flag set just",
        "# before the card, microgame medal flag guarding the message or 0, flags in the message's condition)",
        "FIELD_CARD_GRANTS: list[tuple[str, int, int, int, int, tuple[int, ...]]] = [",
        *(f"    ({path!r}, {table:#x}, {card}, {event:#x}, {medal:#x}, ({''.join(f'{f:#x}, ' for f in guard).rstrip()})),"
          for path, table, card, event, medal, guard in grants),
        "]",
        "",
        "# (book, chapter) -> chapter title. Chapter 0 is each book's prologue.",
        "STORYBOOK_CHAPTER_TITLES: dict[tuple[int, int], str] = {",
        *(f"    {key!r}: {chapters[key]!r}," for key in sorted(chapters)),
        "}",
        "",
    ]
    with open(out_path, "w", encoding="utf-8") as out:
        out.write("\n".join(lines))
    print(f"{rom.title} {rom.game_code}: {len(cards)} cards, {sum(map(len, books))} storybook goals, "
          f"{len(friend_ids)} chocobos, {len(grants)} field card grants -> {out_path}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
