import re
from typing import NamedTuple

from BaseClasses import Location

from . import flags
from .data import CARDS, CHOCOBO_FRIEND_IDS, STORYBOOK_GOALS
from .items import GAME_NAME, card_item_name
from .rewards import (CARD_GIFTS, card_gift_location_id, field_card_location_id, microgame_location_id,
                      rescue_location_id, storybook_location_id)


class ChocoboTalesLocation(Location):
    game = GAME_NAME


class StorybookGoal(NamedTuple):
    book: int
    goal_index: int  # 0-6, the goal's position in the in-game list
    mode: str  # "Trial" or "Battle"
    level: int  # battle mode level the goal is played at (0 for trial goals)


def battle_level(text: str) -> int:
    """The battle mode level a goal needs: the level it names, or level 1 for 'score ... in battle mode' goals."""
    if match := re.search(r"battle mode level (\d)", text):
        return int(match.group(1))
    return 1 if "battle mode" in text else 0


class MicrogameMedal(NamedTuple):
    game: int  # 1-23
    medal: str  # "Silver" or "Gold"


def _seconds_to_clock(text: str) -> str:
    minutes = re.search(r"(\d+) minutes?", text)
    seconds = re.search(r"(\d+) seconds?", text)
    total = (int(minutes.group(1)) * 60 if minutes else 0) + (int(seconds.group(1)) if seconds else 0)
    return f"{total // 60}:{total % 60:02d}"


def goal_short_name(text: str) -> str:
    """Shortens an in-game goal description, e.g. 'Finish trial mode within 30 seconds.' -> 'Trial Under 0:30'."""
    text = text.rstrip(".")
    if match := re.fullmatch(r"Conquer battle mode level (\d)", text):
        return f"Battle Level {match.group(1)}"
    if match := re.fullmatch(r"Conquer battle mode level (\d) with at least (\d+) points", text):
        return f"Battle Level {match.group(1)} With {match.group(2)}+ Points"
    if match := re.fullmatch(r"Conquer battle mode level (\d) without being hit", text):
        return f"Battle Level {match.group(1)} Without Being Hit"
    if match := re.fullmatch(r"Score at least (\d+) points in (trial|battle) mode", text):
        return f"{match.group(2).title()} {match.group(1)}+ Points"
    if match := re.fullmatch(r"Finish trial mode within (.+)", text):
        return f"Trial Under {_seconds_to_clock(match.group(1))}"
    if text == "Finish trial mode without taking any damage from boulders":
        return "Trial Without Boulder Damage"
    if text == "Finish trial mode without bumping into any walls":
        return "Trial Without Bumping Walls"
    if match := re.fullmatch(r"Climb to at least (\d+)m in trial mode", text):
        return f"Trial Climb {match.group(1)}m"
    if match := re.fullmatch(r"Swim at least (\d+)m in trial mode", text):
        return f"Trial Swim {match.group(1)}m"
    raise ValueError(f"No short name for storybook goal {text!r}")


STORYBOOK_LOCATIONS: dict[str, StorybookGoal] = {}
STORYBOOK_LOCATION_IDS: dict[str, int] = {}
for _book, _goals in enumerate(STORYBOOK_GOALS, 1):
    for _index, (_text, _, _) in enumerate(_goals):
        _name = f"Storybook {_book:02d} - {goal_short_name(_text)}"
        assert _name not in STORYBOOK_LOCATIONS, _name
        STORYBOOK_LOCATIONS[_name] = StorybookGoal(_book, _index, "Trial" if "trial" in _text else "Battle",
                                                   battle_level(_text))
        STORYBOOK_LOCATION_IDS[_name] = storybook_location_id(_book, _index)

# Rescuing a chocobo is a separate check, even when its storybook goal is not
# selected as a location. The goal completion flag proves the rescue happened;
# the chocobo ownership flag is reserved for its Archipelago item.
RESCUE_LOCATIONS: dict[str, StorybookGoal] = {
    f"Rescue Chocobo {name}": StorybookGoal(book, index, "Trial" if "trial" in text else "Battle",
                                             battle_level(text))
    for book, goals in enumerate(STORYBOOK_GOALS, 1)
    for index, (text, kind, name) in enumerate(goals)
    if kind == "chocobo"
}
RESCUE_LOCATION_IDS: dict[str, int] = {
    name: rescue_location_id(CHOCOBO_FRIEND_IDS[name.removeprefix("Rescue Chocobo ")])
    for name in RESCUE_LOCATIONS
}

# The 23 field microgames' in-game titles. They're only stored as images (/present/en/lg_title_lower.POBJ: an
# NCGR/NCER sprite bank, cells 0-22 in microgame order), read off a render of that bank.
# Each microgame awards a card for reaching Silver and another for Gold.
MICROGAME_NAMES: list[str] = [
    "Bomberwall",
    "Bubble Bounce",
    "Tap Tap Trap",
    "Cliffhanger",
    "Redeye Rampage",
    "Cheese Chase",
    "Blowgun Blitz",
    "Silly Scribbles",
    "Mystifying Magnets",
    "Jelly Jiggler",
    "Tome Raider",
    "Deadly Demon Wall",
    "Malboro Masher",
    "Job Juggler",
    "Rodeo Roundup",
    "Leaptoad",
    "Blizzardy Blocks",
    "Wacky Wall Climb",
    "Up, Up, and A-Kweh!",
    "Blazing Blocks",
    "Boggling Bridges",
    "Magic Pot Luck",
    "Crazy Credits",
]

MICROGAME_LOCATIONS: dict[str, MicrogameMedal] = {}
MICROGAME_LOCATION_IDS: dict[str, int] = {}
for _game, _title in enumerate(MICROGAME_NAMES, 1):
    for _medal_index, _medal in enumerate(("Silver", "Gold")):
        _name = f"Microgame {_game:02d} {_title} - {_medal}"
        MICROGAME_LOCATIONS[_name] = MicrogameMedal(_game, _medal)
        MICROGAME_LOCATION_IDS[_name] = microgame_location_id(_game, _medal)

# Story progress: each chapter (1-5) ends with a boss Pop-up Duel against Bebuzzu, then the next chapter opens
CHAPTER_LOCATIONS: dict[str, int] = {f"Chapter {chapter} Complete": chapter for chapter in flags.CHAPTER_COMPLETE_FLAGS}
CHAPTER_LOCATION_IDS: dict[str, int] = {name: 3000 + chapter for name, chapter in CHAPTER_LOCATIONS.items()}

# Optional: winning each boss Pop-up Duel
DUEL_LOCATIONS: dict[str, str] = {f"Pop-up Duel Win - {opponent}": opponent for opponent in flags.DUEL_WIN_FLAGS}
DUEL_LOCATION_IDS: dict[str, int] = {name: 3100 + index for index, name in enumerate(DUEL_LOCATIONS)}

# The nine cardget.act field scripts set a pickup flag separately from the card ownership flag.
# (card number, pickup flag, field map x/y). Their card flags remain Archipelago items.
FIELD_CARD_DATA: tuple[tuple[int, int, tuple[int, int]], ...] = (
    (13, 0x8D, (48, 51)),
    (14, 0x8E, (52, 51)),
    (28, 0x9E, (49, 51)),
    (32, 0xA0, (46, 52)),
    (33, 0xA1, (50, 49)),
    (48, 0xAF, (50, 52)),
    (61, 0xBD, (50, 50)),
    (103, 0xE7, (150, 49)),
    (108, 0xEA, (51, 50)),
)
_card_names = {number: card_item_name(monster, ability) for number, monster, ability in CARDS}
FIELD_CARD_LOCATIONS: dict[str, tuple[int, int, tuple[int, int]]] = {
    f"Find Card - {_card_names[number]}": (number, pickup_flag, map_tile)
    for number, pickup_flag, map_tile in FIELD_CARD_DATA
}
FIELD_CARD_LOCATION_IDS: dict[str, int] = {
    name: field_card_location_id(number) for name, (number, _, _) in FIELD_CARD_LOCATIONS.items()
}

# Cards field scripts give outside pickups and microgames (rewards.CARD_GIFTS): card number -> location name.
# The flag the script sets along with the card marks the check.
CARD_GIFT_LOCATIONS: dict[str, int] = {f"Card Gift - {_card_names[card]}": card for card in sorted(CARD_GIFTS)}
CARD_GIFT_LOCATION_IDS: dict[str, int] = {name: card_gift_location_id(card) for name, card in CARD_GIFT_LOCATIONS.items()}

location_name_to_id: dict[str, int] = {
    **STORYBOOK_LOCATION_IDS, **MICROGAME_LOCATION_IDS, **CHAPTER_LOCATION_IDS, **DUEL_LOCATION_IDS,
    **FIELD_CARD_LOCATION_IDS, **RESCUE_LOCATION_IDS, **CARD_GIFT_LOCATION_IDS,
}

location_name_groups: dict[str, set[str]] = {
    "Storybooks": set(STORYBOOK_LOCATIONS),
    "Microgames": set(MICROGAME_LOCATIONS),
    "Story": set(CHAPTER_LOCATIONS),
    "Pop-up Duels": set(DUEL_LOCATIONS),
    "Field Cards": set(FIELD_CARD_LOCATIONS),
    "Chocobo Rescues": set(RESCUE_LOCATIONS),
    "Card Gifts": set(CARD_GIFT_LOCATIONS),
}
for _name, _goal in STORYBOOK_LOCATIONS.items():
    location_name_groups.setdefault(f"Storybook {_goal.book:02d}", set()).add(_name)
