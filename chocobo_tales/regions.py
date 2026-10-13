from typing import TYPE_CHECKING

from BaseClasses import CollectionState, ItemClassification, Region

from . import flags
from .data import CHOCOBO_FRIEND_IDS, STORYBOOK_STORY_CHAPTER
from .items import (BOOK_MODE_ITEM, CARD_ITEMS, CARD_PACK_ITEMS, CARD_PACK_NUMBERS, MODE_UNLOCKS,
                    STORY_COMPLETE_EVENT, ChocoboTalesItem)
from .locations import (
    CARD_GIFT_LOCATION_IDS, CARD_GIFT_LOCATIONS, CHAPTER_LOCATION_IDS, CHAPTER_LOCATIONS, DUEL_LOCATION_IDS,
    DUEL_LOCATIONS, FIELD_CARD_LOCATION_IDS, FIELD_CARD_LOCATIONS, MICROGAME_LOCATION_IDS, MICROGAME_LOCATIONS,
    RESCUE_LOCATION_IDS, RESCUE_LOCATIONS, STORYBOOK_LOCATION_IDS, STORYBOOK_LOCATIONS, ChocoboTalesLocation,
    StorybookGoal,
)
from .rewards import CARD_GIFTS

if TYPE_CHECKING:
    from . import ChocoboTalesWorld

CHAPTERS = 6
# Every duel after the tutorial (whose 3-card deck the game builds itself) needs a 15-card deck of owned cards
DECK_SIZE = 15
POST_GAME = 7  # region after the ending

# Microgame -> (chapter it's played from, rescued chocobo hosting it). Each microgame's map tile comes from the
# field map markers and its launch script (see NOTES.md); the chapter is the earliest chapter whose storybooks are
# in that part of the map, rounded later when unsure. Four microgames are run by rescued chocobos (dolly.act,
# swinny.act, wakaba.act, zavi.act), so logic also expects that chocobo. Microgame 23 only opens after the ending.
MICROGAME_ACCESS: dict[int, tuple[int, str | None]] = {
    1: (2, None),    # 47/52, next to storybook 5
    2: (2, None),    # 52/49, farm area
    3: (3, None),    # 50/53, south
    4: (3, None),    # 46/52, north-west
    5: (6, None),    # 45/45, west
    6: (2, None),    # farm house
    7: (2, None),    # barn
    8: (2, "Dolly"),  # farm house
    9: (2, None),    # farm house
    10: (2, None),   # 51/50, farm area
    11: (2, "Sweenie"),
    12: (5, None),   # 48/45, west
    13: (3, None),   # 50/54, south
    14: (2, None),   # barn
    15: (2, "Wakaba"),
    16: (5, None),   # 56/50, east
    17: (4, None),   # 55/50, east
    18: (5, None),   # 49/45, west
    19: (2, "Zavi"),
    20: (2, None),   # 47/52, next to storybook 5
    21: (4, None),   # 55/52, east
    22: (3, None),   # house room south of the farm
    23: (POST_GAME, None),  # in the ending script
}

# The field map layout puts eight pickups in the farm area. The 150/49 interior is
# left in chapter 6 until its earlier access has been confirmed in game.
FIELD_CARD_ACCESS: dict[tuple[int, int], int] = {
    (50, 50): 1,
    (48, 51): 2, (52, 51): 2, (49, 51): 2, (46, 52): 2,
    (50, 49): 2, (50, 52): 2, (51, 50): 2,
    (150, 49): 6,
}


# Card gifts handed out by rescued chocobos, by the script giving them (the chocobo is only there once rescued)
CARD_GIFT_SCRIPT_HOSTS: dict[str, str] = {"glynn.act": "Grinn", "bekky.act": "Becky", "momo.act": "Peachie",
                                          "blues.act": "Bruce"}


def card_gift_hosts(card: int) -> set[str]:
    """Rescued chocobos a card gift needs: its giver, and any chocobo its message's condition tests."""
    _, scripts, condition = CARD_GIFTS[card]
    hosts = {CARD_GIFT_SCRIPT_HOSTS[name] for name in (script.rsplit("/", 1)[1] for script in scripts)
             if name in CARD_GIFT_SCRIPT_HOSTS}
    hosts |= {name for name, friend_id in CHOCOBO_FRIEND_IDS.items() if flags.chocobo_flag(friend_id) in condition}
    return hosts


def chapter_region_name(chapter: int) -> str:
    return "Post Game" if chapter == POST_GAME else f"Chapter {chapter}"


def needs_mode_item(goal: StorybookGoal) -> bool:
    """Whether the goal's battle level / trial mode is one the game unlocked through that book's own rewards."""
    if goal.book == 1:
        return False  # The story needs book 1's battles, so its rewards still unlock them in play.
    levels, trial = MODE_UNLOCKS[goal.book]
    return goal.level in levels if goal.mode == "Battle" else trial


def card_count(world: "ChocoboTalesWorld", state: CollectionState) -> int:
    if world.options.card_packs:
        return sum(len(CARD_PACK_NUMBERS[item_id]) for name, item_id in CARD_PACK_ITEMS.items()
                   if state.has(name, world.player))
    return sum(state.has(name, world.player) for name in CARD_ITEMS)


def selected_storybook_names(world: "ChocoboTalesWorld") -> list[str]:
    per_book = min(world.options.storybook_goals_per_book.value,
                   4 if world.options.exclude_hardest_storybook_goals else 7)
    return [name for name, goal in STORYBOOK_LOCATIONS.items()
            if goal.goal_index < per_book]


def selected_microgame_names(world: "ChocoboTalesWorld") -> list[str]:
    choice = world.options.microgame_medals.value
    return [name for name, medal in MICROGAME_LOCATIONS.items()
            if choice == 0 or (choice == 1 and medal.medal == "Silver")
            or (choice == 2 and medal.medal == "Gold")]


def create_regions(world: "ChocoboTalesWorld") -> None:
    player = world.player
    options = world.options
    menu = Region("Menu", player, world.multiworld)
    regions = {chapter: Region(chapter_region_name(chapter), player, world.multiworld)
               for chapter in range(1, POST_GAME + 1)}
    world.multiworld.regions += [menu, *regions.values()]

    menu.connect(regions[1])
    cards_per_chapter = options.cards_per_chapter.value
    for chapter in range(2, CHAPTERS + 1):
        cards_needed = DECK_SIZE + (chapter - 2) * cards_per_chapter
        previous_boss = f"Chapter {chapter - 1} Complete"
        regions[chapter - 1].connect(
            regions[chapter],
            # Chapter N's title/flag follows the previous boss duel. Tie the transition to that
            # check, so any later refinement of its access rule also gates the next chapter.
            rule=lambda state, n=cards_needed, boss=previous_boss:
                state.can_reach(boss, "Location", player) and card_count(world, state) >= n,
        )
    regions[CHAPTERS].connect(regions[POST_GAME], rule=lambda state: state.has(STORY_COMPLETE_EVENT, player))

    storybook_names = selected_storybook_names(world)
    if options.goal == options.goal.option_storybook_goals and options.storybook_goals_required.value > len(storybook_names):
        raise ValueError("Storybook Goals Required exceeds the enabled storybook checks")
    for name in storybook_names:
        goal = STORYBOOK_LOCATIONS[name]
        region = regions[STORYBOOK_STORY_CHAPTER[goal.book]]
        location = ChocoboTalesLocation(player, name, STORYBOOK_LOCATION_IDS[name], region)
        if needs_mode_item(goal) and not options.open_storybook_modes:
            location.access_rule = lambda state, item=BOOK_MODE_ITEM[goal.book]: state.has(item, player)
        region.locations.append(location)

    if options.chocobo_rescue_checks:
        for name, goal in RESCUE_LOCATIONS.items():
            region = regions[STORYBOOK_STORY_CHAPTER[goal.book]]
            location = ChocoboTalesLocation(player, name, RESCUE_LOCATION_IDS[name], region)
            if needs_mode_item(goal) and not options.open_storybook_modes:
                location.access_rule = lambda state, item=BOOK_MODE_ITEM[goal.book]: state.has(item, player)
            region.locations.append(location)

    for name in selected_microgame_names(world):
        medal = MICROGAME_LOCATIONS[name]
        chapter, host = MICROGAME_ACCESS[medal.game]
        region = regions[chapter]
        location = ChocoboTalesLocation(player, name, MICROGAME_LOCATION_IDS[name], region)
        if host:
            location.access_rule = lambda state, item=f"Chocobo {host}": state.has(item, player)
        region.locations.append(location)

    if options.field_card_checks:
        for name, (_, _, map_tile) in FIELD_CARD_LOCATIONS.items():
            region = regions[FIELD_CARD_ACCESS[map_tile]]
            region.locations.append(ChocoboTalesLocation(player, name, FIELD_CARD_LOCATION_IDS[name], region))

    if options.card_gift_checks:
        # Gifts are unavailable during the last chapter (flag 0x7F, set after the chapter 5 Bebuzzu duel, until the
        # ending), and when each first becomes available isn't established yet, so logic waits for the ending.
        region = regions[POST_GAME]
        for name, card in CARD_GIFT_LOCATIONS.items():
            location = ChocoboTalesLocation(player, name, CARD_GIFT_LOCATION_IDS[name], region)
            hosts = sorted(card_gift_hosts(card))
            if hosts:
                location.access_rule = lambda state, items=[f"Chocobo {host}" for host in hosts]: \
                    state.has_all(items, player)
            region.locations.append(location)

    for name, chapter in CHAPTER_LOCATIONS.items():
        region = regions[chapter]
        location = ChocoboTalesLocation(player, name, CHAPTER_LOCATION_IDS[name], region)
        location.access_rule = (lambda state, n=DECK_SIZE + (chapter - 1) * cards_per_chapter:
                                card_count(world, state) >= n)
        region.locations.append(location)

    if options.duel_s_rank_checks:
        region = regions[CHAPTERS]
        for name in DUEL_LOCATIONS:
            region.locations.append(ChocoboTalesLocation(player, name, DUEL_LOCATION_IDS[name], region))

    # The ending: beat the last Bebuzzu duel at the end of chapter 6
    ending = ChocoboTalesLocation(player, STORY_COMPLETE_EVENT, None, regions[CHAPTERS])
    ending.access_rule = (lambda state, n=DECK_SIZE + (CHAPTERS - 1) * cards_per_chapter:
                          card_count(world, state) >= n)
    ending.place_locked_item(ChocoboTalesItem(STORY_COMPLETE_EVENT, ItemClassification.progression, None, player))
    regions[CHAPTERS].locations.append(ending)


def can_goal(world: "ChocoboTalesWorld", state: CollectionState) -> bool:
    options = world.options
    if options.goal == options.goal.option_card_collection:
        return card_count(world, state) >= options.cards_required.value
    if options.goal == options.goal.option_chocobo_rescue:
        return state.has_group("Chocobos", world.player, options.chocobos_required.value)
    if options.goal == options.goal.option_storybook_goals:
        return sum(state.can_reach(name, "Location", world.player) for name in selected_storybook_names(world)) >= options.storybook_goals_required.value
    if options.goal == options.goal.option_gold_medals:
        names = selected_microgame_names(world)
        medal_by_game = {MICROGAME_LOCATIONS[name].game: name for name in names}
        return sum(state.can_reach(name, "Location", world.player) for name in medal_by_game.values()) >= options.gold_medals_required.value
    return state.has(STORY_COMPLETE_EVENT, world.player)
