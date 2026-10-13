from BaseClasses import Item

from .data import CARDS, STORYBOOK_GOALS, STORYBOOK_REWARD_RECORDS

GAME_NAME = "Chocobo Tales"


class ChocoboTalesItem(Item):
    game = GAME_NAME


def card_item_name(monster: str, ability: str) -> str:
    return f"{monster} - {ability}"


# Card item ids are the in-game card numbers (1-127)
CARD_ITEMS: dict[str, int] = {card_item_name(monster, ability): number for number, monster, ability in CARDS}
MONSTER_CARDS: dict[str, tuple[int, ...]] = {}
for number, monster, _ in CARDS:
    MONSTER_CARDS[monster] = (*MONSTER_CARDS.get(monster, ()), number)
CARD_PACK_ITEMS: dict[str, int] = {
    f"{monster} Card Pack": 400 + index for index, monster in enumerate(MONSTER_CARDS, 1)
}
CARD_PACK_NUMBERS: dict[int, tuple[int, ...]] = {
    item_id: MONSTER_CARDS[name.removesuffix(" Card Pack")] for name, item_id in CARD_PACK_ITEMS.items()
}

# The chocobos you rescue by completing storybook goals, in storybook order
RESCUED_CHOCOBOS: list[str] = [
    str(value) for goals in STORYBOOK_GOALS for _, kind, value in goals if kind == "chocobo"
]
CHOCOBO_ITEMS: dict[str, int] = {f"Chocobo {name}": 200 + index for index, name in enumerate(RESCUED_CHOCOBOS)}


def _mode_unlocks(book: int) -> tuple[frozenset[int], bool]:
    """The battle mode levels, and whether trial mode, that the book's own goal rewards unlock in the vanilla game."""
    levels: set[int] = set()
    trial = False
    for records in STORYBOOK_REWARD_RECORDS[book - 1]:
        for kind, value in records:
            if kind == "battle_levels":
                levels |= {level for level in range(1, 6) if value >> level & 1}
            elif kind == "trial_mode":
                trial = True
    return frozenset(levels), trial


# Storybook -> (battle levels, trial mode) that its goals unlock in the vanilla game. Most are blocked by the
# patch; book 1's battle levels still unlock through play because Irma won't let you leave the starting
# area before its first duel, so book 1 has no Modes item (id 301 stays retired).
MODE_UNLOCKS: dict[int, tuple[frozenset[int], bool]] = {book: _mode_unlocks(book) for book in range(1, 17)}
MODE_ITEMS: dict[str, int] = {
    f"Storybook {book:02d} Modes": 300 + book for book, (levels, trial) in MODE_UNLOCKS.items()
    if book != 1 and (levels or trial)
}
MODE_ITEM_BOOKS: dict[str, int] = {name: item_id - 300 for name, item_id in MODE_ITEMS.items()}
BOOK_MODE_ITEM: dict[int, str] = {book: name for name, book in MODE_ITEM_BOOKS.items()}
EPILOGUE_ITEMS: dict[str, int] = {
    f"Storybook {book:02d} Epilogue {epilogue}": 500 + 3 * (book - 1) + epilogue
    for book in range(1, 17) for epilogue in range(1, 4)
}

FILLER_ITEM = "Gysahl Greens"
STORY_COMPLETE_EVENT = "Story Complete"

item_name_to_id: dict[str, int] = {
    **CARD_ITEMS,
    **CARD_PACK_ITEMS,
    **CHOCOBO_ITEMS,
    **MODE_ITEMS,
    **EPILOGUE_ITEMS,
    FILLER_ITEM: 900,
}

item_name_groups: dict[str, set[str]] = {
    "Cards": set(CARD_ITEMS),
    "Card Packs": set(CARD_PACK_ITEMS),
    "Chocobos": set(CHOCOBO_ITEMS),
    "Mode Unlocks": set(MODE_ITEMS),
    "Epilogues": set(EPILOGUE_ITEMS),
}
for _, monster, ability in CARDS:
    item_name_groups.setdefault(f"{monster} Cards", set()).add(card_item_name(monster, ability))

assert len(CARD_ITEMS) == len(CARDS), "card item names must be unique"
assert len(set(item_name_to_id.values())) == len(item_name_to_id), "item ids must be unique"
