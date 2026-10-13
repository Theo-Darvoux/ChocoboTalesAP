"""
What the game requires before a location can be checked, read from the field event scripts (see NOTES.md, "Access
rules"). No Archipelago imports.

Requirements are expressed as a story chapter (1-6, 7 = after the ending), rescued chocobos whose field presence
(or only ownership) the location needs, and storybook epilogues (book, epilogue) whose field change (a "gimmick") it
needs.
"""
from typing import NamedTuple

from .data import STORYBOOK_GOALS, STORYBOOK_STORY_CHAPTER

POST_GAME = 7


class Access(NamedTuple):
    chapter: int
    chocobos: tuple[str, ...] = ()  # must be on the field
    epilogues: tuple[tuple[int, int], ...] = ()
    owned: tuple[str, ...] = ()  # only their ownership flags are tested


# Rescued chocobo -> storybook it is rescued in. A rescued chocobo only appears on the field once its ownership flag is
# set (the Archipelago item) and you come back from that storybook (the book's bookret.act plays its cNN.act scene,
# which sets its field presence flag 0x107 + friend id).
CHOCOBO_BOOK: dict[str, int] = {
    str(value): book for book, goals in enumerate(STORYBOOK_GOALS, 1) for _, kind, value in goals if kind == "chocobo"
}

# Storybook book's bookret.act runs Gimmick<(book + 1) // 2><A if book is odd else B><e>.act when epilogue e is unlocked;
# each gimmick changes the field (frozen sea, opened passages, revealed objects) and sets a flag.
GIMMICK_FLAGS: dict[tuple[int, int], int] = {
    (book, epilogue): (3 * (book - 1) if book <= 10 else 0x54 + 3 * (book - 11)) + epilogue - 1
    for book in range(1, 17) for epilogue in range(1, 4)
}

# Gimmicks the developer skip scripts (/field/50/50/skip*.act, saves of points in the story) already have: the story
# needs these field changes (chapter 4's Technolith trip crosses the sea Gimmick2B1 freezes, for instance). Chapter ->
# epilogues set in its last snapshot (skip2, skip3, skip4, skip5, skipN being the state right after chapter N - 1's
# Bebuzzu duel; skip5pb for chapter 5) that an earlier chapter's doesn't have, plus BOSS_EPILOGUES.
STORY_EPILOGUES: dict[int, tuple[tuple[int, int], ...]] = {
    1: ((1, 1),),
    2: ((1, 2), (5, 1), (5, 2), (7, 1), (8, 1)),
    3: ((6, 1), (9, 1), (3, 2), (10, 1)),
    4: ((4, 1), (11, 1), (12, 1), (13, 3)),
    5: ((2, 2), (15, 1), (16, 1)),
}
# The skip script whose flags show each chapter's last known state
STORY_SNAPSHOTS: dict[int, str] = {1: "skip2", 2: "skip3", 3: "skip4", 4: "skip5", 5: "skip5pb"}
# Chapter -> the epilogue whose gimmick (on the boss tile) starts the scene spawning that chapter's Bebuzzu duel.
# skip5pb precedes chapter 5's: Gimmick8B1 warps into 44/45/a1.act, which sets 0x7D, the guard of 44/45's bebuz.act.
BOSS_EPILOGUES: dict[int, tuple[int, int]] = {2: (8, 1), 3: (10, 1), 4: (12, 1), 5: (16, 1)}

# Microgame -> what its host needs. The chapter is the earliest chapter of its map area (see NOTES.md); hosts and
# epilogues come from the launch scripts and the conditions creating their objects in map.act.
_MICROGAME_BASE: dict[int, Access] = {
    1: Access(2),                       # 47/52 LG_BOM.act
    2: Access(2),                       # 52/49
    3: Access(3, ("Moggy",), ((6, 2),)),  # 50/53: the Goblin wants Moggy's gold needle (51/51 moggy.act, Gimmick3B2)
    4: Access(3),                       # 46/52
    5: Access(6),                       # 45/45, Technolith
    6: Access(2, ("Belle",)),           # 149/54: Chip waits for Granny Belle (flag 0x10F)
    7: Access(2),                       # 150/50 LG_BALL.act
    8: Access(2, ("Dolly",)),           # 149/55 dolly.act
    9: Access(2, ("Indy",)),            # 149/55 aiai.act is only created with Indy present (0x113)
    10: Access(2, ("Jarro",)),          # 51/50: Jerry waits for Big Jarro (0x111)
    11: Access(POST_GAME, ("Sweenie",)),  # 49/49 swinny.act only offers it once the ending flag 0x3DF is set
    12: Access(5, (), ((14, 3),)),      # 48/45: created once Gimmick7B3 is done
    13: Access(3),                      # 50/54
    14: Access(2),                      # 150/50 LG_JOB.act
    15: Access(POST_GAME, ("Wakaba",)),  # 49/49 wakaba.act: ending flag 0x3DF, like Sweenie
    16: Access(5),                      # 56/50
    17: Access(4),                      # 55/50
    18: Access(5, ("Belle",)),          # 49/45: created with Belle present
    19: Access(2, ("Zavi",)),           # 51/50 zavi.act
    20: Access(2),                      # 47/52 LG_IF.act
    21: Access(4, ("Belle",)),          # 55/52: created with Belle present
    22: Access(3),                      # 149/61
    23: Access(POST_GAME),              # ending1.act launches it during the finale; logically after the last duel
}

# Field card pickups that need a gimmick: the 50/49 card is only created after Gimmick1A3
FIELD_CARD_EPILOGUES: dict[tuple[int, int], tuple[tuple[int, int], ...]] = {(50, 49): ((1, 3),)}

# Card gift (card number) -> what its giver needs. See NOTES.md for the script evidence of each.
_CARD_GIFT_BASE: dict[int, Access] = {
    22: Access(2, ("Peachie",), ((9, 2),)),   # momo.act: show Peachie the fireflower (50/55 flower.act, Gimmick5A2)
    42: Access(1, ("Becky",)),                # bekky.act
    60: Access(2, ("Bruce",), ((12, 2),)),    # blues.act tests Gimmick6B2
    62: Access(2, (), ((7, 3),)),             # 48/51 ana.act, the hole Gimmick4A3 opens
    73: Access(2),                            # 46/52 carbuncle.act
    74: Access(2, (), ((10, 3),)),            # 52/52 carbuncle.act, created after Gimmick5B3
    75: Access(4),                            # 56/51 carbuncle.act
    76: Access(6, (), ((10, 3),)),            # 149/52: after all five other Carbuncles, including 44/45's
    77: Access(3),                            # 149/49 carbuncle.act needs 0x34, set by 45/51/a3.act after chapter 2's boss
    78: Access(6),                            # 44/45 map.act creates it when 0x7F is set (chapter 6)
    82: Access(1, ("Grinn",)),                # glynn.act
    91: Access(2),                            # first win against Behemoth (147/51 a3.act), chapter 2
    92: Access(3),                            # Golem (49/55 a2.act), chapter 3
    93: Access(4),                            # Sahagin (56/50 a1.act), chapter 4
    95: Access(5),                            # Iron Giant (47/45 a2.act), chapter 5
    99: Access(2, (), ((7, 2),)),             # 149/50 DEBU.act tests Gimmick4A2
    100: Access(5),                           # DuelResultS awards it when all four have been beaten, by chapter 5
    101: Access(2, (), ((12, 3),)),           # 52/49 chocz.act tests Gimmick6B3
    102: Access(5, owned=tuple(CHOCOBO_BOOK)),  # mogu2.act: all 15 item chocobos plus fixed rescues, including Rose
    113: Access(POST_GAME),                   # rematch wins against Bebuzzu, offered after the ending
    114: Access(2), 116: Access(2), 117: Access(2),  # Dueler X's Goblins, forced event in chapter 2
    119: Access(2, (), ((4, 3),)),            # 52/50 Typhon chests open after their gimmick
    120: Access(2, (), ((2, 3),)),
    121: Access(2, (), ((11, 3),)),
    122: Access(2, (), ((16, 2),)),
}


def _resolve(access: Access) -> Access:
    """Raises the chapter to when the chocobos can appear and the epilogues' storybooks are available."""
    books = [CHOCOBO_BOOK[name] for name in access.chocobos if access.chapter != POST_GAME] + \
            [book for book, _ in access.epilogues]
    return access._replace(chapter=max([access.chapter, *(STORYBOOK_STORY_CHAPTER[book] for book in books)]))


MICROGAME_ACCESS: dict[int, Access] = {game: _resolve(access) for game, access in _MICROGAME_BASE.items()}
CARD_GIFT_ACCESS: dict[int, Access] = {card: _resolve(access) for card, access in _CARD_GIFT_BASE.items()}
