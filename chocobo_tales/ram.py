"""
Memory map for Final Fantasy Fables: Chocobo Tales (Europe, AEHP) in BizHawk's melonDS core, found by static
analysis of the game's code (see NOTES.md). Offsets are into BizHawk's "Main RAM" domain (DS address - 0x02000000).

The game keeps its save data in one struct and reaches it through a global pointer (normally 0x020A35D8). The
struct holds a flag bank of 32-bit words at +0x24; flags.py has what each flag means. Every check and every item
is a flag.
"""

from . import flags
from .data import CHOCOBO_FRIEND_IDS, STORYBOOK_REWARD_RECORDS
from .items import (BOOK_MODE_ITEM, CARD_ITEMS, CARD_PACK_NUMBERS, CHOCOBO_ITEMS, EPILOGUE_ITEMS,
                    MODE_ITEMS, MODE_UNLOCKS)
from .locations import (
    CARD_GIFT_LOCATION_IDS, CARD_GIFT_LOCATIONS, CHAPTER_LOCATION_IDS, CHAPTER_LOCATIONS, DUEL_LOCATION_IDS,
    DUEL_LOCATIONS, FIELD_CARD_LOCATION_IDS, FIELD_CARD_LOCATIONS, MICROGAME_LOCATION_IDS, MICROGAME_LOCATIONS, RESCUE_LOCATION_IDS, RESCUE_LOCATIONS,
    STORYBOOK_LOCATION_IDS, STORYBOOK_LOCATIONS,
)
from .rewards import CARD_GIFTS
from .rom_patch import AP_DATA_OFFSET, AP_MAGIC, SLOT_NAME_OFFSET, SLOT_NAME_SIZE

MAIN_RAM = "Main RAM"
ROM = "ROM"
MAIN_RAM_BASE = 0x02000000
MAIN_RAM_SIZE = 0x400000

# The cartridge header is copied to 0x027FFE00 at boot: 12-byte title, then the 4-byte game code
CART_HEADER = 0x3FFE00
GAME_TITLE = b"CHOCOBOTALES"
SUPPORTED_GAME_CODES: dict[bytes, str] = {
    b"AEHP": "Europe",
}

# Global holding the save struct's address (0x0209DDE0); set by the new game / load code
SAVE_POINTER = 0x09DDE0
FLAG_BANK_OFFSET = 0x24
FLAG_BANK_SIZE = 0x150  # covers flags 0-0xA7F

flag_position = flags.flag_position

# location id -> flag set when it's done
LOCATION_FLAGS: dict[int, int] = {
    **{STORYBOOK_LOCATION_IDS[name]: flags.storybook_goal_flag(goal.book, goal.goal_index)
       for name, goal in STORYBOOK_LOCATIONS.items()},
    **{MICROGAME_LOCATION_IDS[name]: flags.microgame_flag(medal.game, medal.medal)
       for name, medal in MICROGAME_LOCATIONS.items()},
    **{CHAPTER_LOCATION_IDS[name]: flags.CHAPTER_COMPLETE_FLAGS[chapter] for name, chapter in CHAPTER_LOCATIONS.items()},
    **{DUEL_LOCATION_IDS[name]: flags.DUEL_WIN_FLAGS[opponent] for name, opponent in DUEL_LOCATIONS.items()},
    **{FIELD_CARD_LOCATION_IDS[name]: pickup_flag for name, (_, pickup_flag, _) in FIELD_CARD_LOCATIONS.items()},
    **{RESCUE_LOCATION_IDS[name]: flags.storybook_goal_flag(goal.book, goal.goal_index)
       for name, goal in RESCUE_LOCATIONS.items()},
    **{CARD_GIFT_LOCATION_IDS[name]: CARD_GIFTS[card][0] for name, card in CARD_GIFT_LOCATIONS.items()},
}


def mode_flags(book: int) -> list[int]:
    levels, trial = MODE_UNLOCKS[book]
    return [flags.battle_level_flag(book, level) for level in sorted(levels)] + ([flags.trial_mode_flag(book)] if trial else [])


# item id -> flags to set when it's received
ITEM_FLAGS: dict[int, list[int]] = {
    **{item_id: [flags.card_flag(item_id)] for item_id in CARD_ITEMS.values()},
    **{item_id: [flags.card_flag(number) for number in numbers]
       for item_id, numbers in CARD_PACK_NUMBERS.items()},
    **{item_id: [flags.chocobo_flag(CHOCOBO_FRIEND_IDS[name.removeprefix("Chocobo ")])]
       for name, item_id in CHOCOBO_ITEMS.items()},
    **{MODE_ITEMS[name]: mode_flags(book) for book, name in BOOK_MODE_ITEM.items()},
    **{item_id: [flags.epilogue_flag((item_id - 501) // 3 + 1, (item_id - 501) % 3 + 1)]
       for item_id in EPILOGUE_ITEMS.values()},
}

# The first Adamantoise race unlocks Battle Level 1, which the story needs next.
# Book 1's battle-level rewards have no item and stay available through normal play. The
# client also restores them for saves made while an older patch blocked those rewards.
STORYBOOK_01_VANILLA_MODE_UNLOCKS: dict[int, int] = {
    flags.battle_level_flag(1, level): flags.storybook_goal_flag(1, goal_index)
    for goal_index, rewards in enumerate(STORYBOOK_REWARD_RECORDS[0])
    for kind, value in rewards if kind == "battle_levels"
    for level in range(1, 6) if value & (1 << level)
}

# Flags the patched game may no longer set by itself: they only come from Archipelago items.
EPILOGUE_FLAGS: frozenset[int] = frozenset(flag for item_id in EPILOGUE_ITEMS.values()
                                        for flag in ITEM_FLAGS[item_id])
BLOCKED_FLAGS: frozenset[int] = frozenset(flag for item_id, item_flags in ITEM_FLAGS.items()
                                       if item_id not in EPILOGUE_ITEMS.values() for flag in item_flags)

assert max(*LOCATION_FLAGS.values(), *BLOCKED_FLAGS) < FLAG_BANK_SIZE * 8
