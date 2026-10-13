from dataclasses import dataclass

from Options import Choice, PerGameCommonOptions, Range, Toggle


class Goal(Choice):
    """
    What you need to do to finish.

    Story Complete: beat the story (the ending plays after the last Bebuzzu duel).
    Chocobo Rescue: receive the number of rescued chocobos set in Chocobos Required.
    Card Collection: receive the number of cards set in Cards Required.
    Storybook Goals: complete the number of storybook goals set below.
    Gold Medals: win the number of microgame Gold medals set below.
    """
    display_name = "Goal"
    option_story_complete = 0
    option_chocobo_rescue = 1
    option_card_collection = 2
    option_storybook_goals = 3
    option_gold_medals = 4
    default = 0


class ChocobosRequired(Range):
    """How many of the 15 rescued chocobos you need for the Chocobo Rescue goal."""
    display_name = "Chocobos Required"
    range_start = 1
    range_end = 15
    default = 12


class CardsRequired(Range):
    """How many of the 127 cards you need for the Card Collection goal."""
    display_name = "Cards Required"
    range_start = 1
    range_end = 127
    default = 100


class StorybookGoalsRequired(Range):
    """Number of storybook goals to complete for the Storybook Goals goal (1-112)."""
    display_name = "Storybook Goals Required"
    range_start = 1
    range_end = 112
    default = 75


class GoldMedalsRequired(Range):
    """Number of microgame Gold medals to win for the Gold Medals goal (1-23)."""
    display_name = "Gold Medals Required"
    range_start = 1
    range_end = 23
    default = 19


class CardsPerChapter(Range):
    """
    Each chapter ends with a boss Pop-up Duel, which needs a decent deck. Logic expects this many more cards for
    each chapter before it puts required items in the next one. 0 turns this off.
    """
    display_name = "Cards Per Chapter"
    range_start = 0
    range_end = 15
    default = 4


class StartingCards(Range):
    """
    How many random cards you start with. The game no longer gives you cards by itself, and every duel after
    the tutorial needs a 15-card deck, so with fewer than 15 the first chapter is mostly spent finding cards.
    """
    display_name = "Starting Cards"
    range_start = 0
    range_end = 40
    default = 15


class DuelSRankChecks(Toggle):
    """
    Adds a check for winning each of eight boss Pop-up Duels. The option key keeps its older name for existing
    YAML files; the game's S result script means success, not a separate S-rank performance requirement.
    """
    display_name = "Boss Duel Win Checks"


class OpenStorybookModes(Toggle):
    """Start with every storybook's battle and trial modes available."""
    display_name = "Open Storybook Modes"


class StartingChocobos(Range):
    """Number of randomly chosen rescued chocobos received at the start."""
    display_name = "Starting Chocobos"
    range_start = 0
    range_end = 15
    default = 0


class CardPacks(Toggle):
    """Bundle each monster's cards into one item. Starting Cards rounds up to whole packs."""
    display_name = "Card Packs"


class ExcludeHardestStorybookGoals(Toggle):
    """Remove goals 5-7 as listed by each storybook. The YAML key retains its older name."""
    display_name = "Exclude Later Storybook Goals"


class StorybookGoalsPerBook(Range):
    """Use the first 2-7 goals from each storybook as checks. The older exclusion option caps this at 4."""
    display_name = "Storybook Goals Per Book"
    range_start = 2
    range_end = 7
    default = 7


class MicrogameMedals(Choice):
    """Which microgame medals become locations. Gold includes the game's Silver threshold too."""
    display_name = "Microgame Medals"
    option_both = 0
    option_silver = 1
    option_gold = 2
    default = 0


class FieldCardChecks(Toggle):
    """Make each of the nine cards found on the field a check."""
    display_name = "Field Card Checks"
    default = 1


class ChocoboRescueChecks(Toggle):
    """Make each of the 15 chocobo rescues a check, independently of storybook goal checks."""
    display_name = "Chocobo Rescue Checks"
    default = 1


class CardGiftChecks(Toggle):
    """
    Make each pop-up card the game gives outside storybooks and microgames a check: gifts from characters (the six
    Carbuncles, Peachie, Becky, Grinn, Bruce, ...), the four Typhon chests, the cards beaten duelists hand over and
    the rewards for beating all four Pop-up Duel bosses and all four Bebuzzu duels (27 checks). Logic only expects
    them after the ending, plus the rescued chocobo when the gift comes from one.
    """
    display_name = "Card Gift Checks"
    default = 1


class ShuffleEpilogues(Toggle):
    """Shuffle the three epilogues of every storybook as Archipelago items."""
    display_name = "Shuffle Epilogues"


@dataclass
class ChocoboTalesOptions(PerGameCommonOptions):
    goal: Goal
    chocobos_required: ChocobosRequired
    cards_required: CardsRequired
    storybook_goals_required: StorybookGoalsRequired
    gold_medals_required: GoldMedalsRequired
    cards_per_chapter: CardsPerChapter
    starting_cards: StartingCards
    duel_s_rank_checks: DuelSRankChecks
    open_storybook_modes: OpenStorybookModes
    starting_chocobos: StartingChocobos
    card_packs: CardPacks
    exclude_hardest_storybook_goals: ExcludeHardestStorybookGoals
    storybook_goals_per_book: StorybookGoalsPerBook
    microgame_medals: MicrogameMedals
    field_card_checks: FieldCardChecks
    chocobo_rescue_checks: ChocoboRescueChecks
    card_gift_checks: CardGiftChecks
    shuffle_epilogues: ShuffleEpilogues


# This world's own options, without Archipelago's common ones (accessibility, local_items, ...)
GAME_OPTION_NAMES: tuple[str, ...] = tuple(name for name in ChocoboTalesOptions.type_hints
                                           if name not in PerGameCommonOptions.type_hints)
