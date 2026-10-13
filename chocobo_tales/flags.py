"""
Save flag numbers in Final Fantasy Fables: Chocobo Tales (EU), found by static analysis (see NOTES.md).
Flag n is bit (31 - n % 32) of 32-bit word n // 32 of the flag bank (save struct + 0x24).
"""

# Story: set by the scripts that open each chapter (chapter N + 1 starts right after chapter N's boss duel)
CHAPTER_COMPLETE_FLAGS: dict[int, int] = {1: 0x43, 2: 0x45, 3: 0x47, 4: 0x49, 5: 0x4B}
STORY_COMPLETE_FLAG = 0x3DF  # set by the ending script

# Set by each boss's DuelResultS.act after a win. The S means success: overlay 19 sets 0x7C8 when the
# selected player is the surviving duelist, with no full-HP or performance check.
DUEL_WIN_FLAGS: dict[str, int] = {
    "Behemoth": 0x13E,
    "Golem": 0x13F,
    "Sahagin": 0x140,
    "Iron Giant": 0x141,
    "Bebuzzu (Chapter 2)": 0x142,
    "Bebuzzu (Chapter 3)": 0x143,
    "Bebuzzu (Chapter 4)": 0x144,
    "Bebuzzu (Chapter 5)": 0x145,
}


def storybook_goal_flag(book: int, goal: int) -> int:
    return 0x7EE + 32 * (book - 1) + goal


def battle_level_flag(book: int, level: int) -> int:
    return 0x7DD + 32 * (book - 1) + level - 1


def trial_mode_flag(book: int) -> int:
    return 0x7E2 + 32 * (book - 1)


def epilogue_flag(book: int, epilogue: int) -> int:
    return 0x7D7 + 32 * (book - 1) + epilogue


def microgame_flag(game: int, medal: str) -> int:
    return 0x9F8 + 3 * (game - 1) + (1 if medal == "Silver" else 2)


def card_flag(number: int) -> int:
    return 0x400 + number


def chocobo_flag(friend_id: int) -> int:
    return 0x3E6 + friend_id


def flag_position(flag: int) -> tuple[int, int]:
    """(byte offset inside the flag bank, bit mask) of a flag."""
    bit = 31 - flag % 32
    return 4 * (flag // 32) + bit // 8, 1 << (bit % 8)
