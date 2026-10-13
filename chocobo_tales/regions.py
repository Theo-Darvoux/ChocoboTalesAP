from typing import TYPE_CHECKING

from BaseClasses import CollectionState, ItemClassification, Region

from . import flags
from .access import (CARD_GIFT_ACCESS, FIELD_CARD_EPILOGUES, MICROGAME_ACCESS, POST_GAME, STORY_EPILOGUES, Access)
from .data import STORYBOOK_REWARD_RECORDS, STORYBOOK_STORY_CHAPTER
from .items import (BOOK_MODE_ITEM, CARD_ITEMS, CARD_PACK_ITEMS, CARD_PACK_NUMBERS, MODE_UNLOCKS,
                    STORY_COMPLETE_EVENT, ChocoboTalesItem, epilogue_item_name)
from .locations import (
    CARD_GIFT_LOCATION_IDS, CARD_GIFT_LOCATIONS, CHAPTER_LOCATION_IDS, CHAPTER_LOCATIONS, DUEL_LOCATION_IDS,
    DUEL_LOCATIONS, FIELD_CARD_LOCATION_IDS, FIELD_CARD_LOCATIONS, MICROGAME_LOCATION_IDS, MICROGAME_LOCATIONS,
    RESCUE_LOCATION_IDS, RESCUE_LOCATIONS, STORYBOOK_LOCATION_IDS, STORYBOOK_LOCATIONS, ChocoboTalesLocation,
    StorybookGoal,
)

if TYPE_CHECKING:
    from . import ChocoboTalesWorld

CHAPTERS = 6
# Every duel after the tutorial (whose 3-card deck the game builds itself) needs a 15-card deck of owned cards
DECK_SIZE = 15

# The 9 field card pickups' map tiles -> chapter, from the field map layout. The 150/49 interior is left in chapter 6
# until its earlier access has been confirmed in game.
FIELD_CARD_ACCESS: dict[tuple[int, int], int] = {
    (50, 50): 1,
    (48, 51): 2, (52, 51): 2, (49, 51): 2, (46, 52): 2,
    (50, 49): 2, (50, 52): 2, (51, 50): 2,
    (150, 49): 6,
}
# Bebuzzu rematches (whose wins set these duel flags) are only offered after the ending (their text1.act tests 0x3DF)
POST_GAME_DUELS = frozenset(name for name in flags.DUEL_WIN_FLAGS if name.startswith("Bebuzzu"))
# (book, epilogue) -> the storybook goal that unlocks it in the vanilla game
EPILOGUE_GOALS: dict[tuple[int, int], StorybookGoal] = {
    (goal.book, value): goal for name, goal in STORYBOOK_LOCATIONS.items()
    for kind, value in STORYBOOK_REWARD_RECORDS[goal.book - 1][goal.goal_index] if kind == "epilogue"
}


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


def has_epilogue(world: "ChocoboTalesWorld", state: CollectionState, book: int, epilogue: int) -> bool:
    """
    Whether the epilogue can be unlocked: its Archipelago item, or else the vanilla goal awarding it (with that book's
    Modes item when the goal needs one). Callers place the location no earlier than the book's chapter.
    """
    if world.options.shuffle_epilogues:
        return state.has(epilogue_item_name(book, epilogue), world.player)
    goal = EPILOGUE_GOALS[(book, epilogue)]
    return (not needs_mode_item(goal) or bool(world.options.open_storybook_modes)
            or state.has(BOOK_MODE_ITEM[goal.book], world.player))


def access_rule(world: "ChocoboTalesWorld", access: Access):
    """The rule for an Access entry's chocobos and epilogues (its chapter is the location's region), or None."""
    chocobos = [f"Chocobo {name}" for name in (*access.chocobos, *access.owned)]
    epilogues = access.epilogues
    if not chocobos and not epilogues:
        return None
    player = world.player
    return lambda state: (state.has_all(chocobos, player)
                          and all(has_epilogue(world, state, book, e) for book, e in epilogues))


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

    def add(name: str, location_id: int, access: Access) -> None:
        region = regions[access.chapter]
        location = ChocoboTalesLocation(player, name, location_id, region)
        rule = access_rule(world, access)
        if rule:
            location.access_rule = rule
        region.locations.append(location)

    for name in selected_microgame_names(world):
        add(name, MICROGAME_LOCATION_IDS[name], MICROGAME_ACCESS[MICROGAME_LOCATIONS[name].game])

    if options.field_card_checks:
        for name, (_, _, map_tile) in FIELD_CARD_LOCATIONS.items():
            add(name, FIELD_CARD_LOCATION_IDS[name],
                Access(FIELD_CARD_ACCESS[map_tile], epilogues=FIELD_CARD_EPILOGUES.get(map_tile, ())))

    if options.card_gift_checks:
        for name, card in CARD_GIFT_LOCATIONS.items():
            add(name, CARD_GIFT_LOCATION_IDS[name], CARD_GIFT_ACCESS[card])

    for name, chapter in CHAPTER_LOCATIONS.items():
        region = regions[chapter]
        location = ChocoboTalesLocation(player, name, CHAPTER_LOCATION_IDS[name], region)
        # The boss duel needs a bigger deck each chapter, and the field changes the chapter's storybook epilogues make
        location.access_rule = (lambda state, n=DECK_SIZE + (chapter - 1) * cards_per_chapter,
                                epilogues=STORY_EPILOGUES[chapter]:
                                card_count(world, state) >= n
                                and all(has_epilogue(world, state, book, e) for book, e in epilogues))
        region.locations.append(location)

    if options.duel_s_rank_checks:
        for name, opponent in DUEL_LOCATIONS.items():
            region = regions[POST_GAME if opponent in POST_GAME_DUELS else CHAPTERS]
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
