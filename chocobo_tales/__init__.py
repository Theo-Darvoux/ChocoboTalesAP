from typing import Any, ClassVar

import settings
from BaseClasses import ItemClassification, Tutorial
from worlds.AutoWorld import WebWorld, World

from . import client  # noqa: F401 -- registers the BizHawk client
from .items import (
    CARD_ITEMS, CARD_PACK_ITEMS, CHOCOBO_ITEMS, EPILOGUE_ITEMS, FILLER_ITEM, GAME_NAME, MODE_ITEMS,
    STORY_COMPLETE_EVENT, ChocoboTalesItem,
    item_name_groups, item_name_to_id,
)
from .locations import location_name_groups, location_name_to_id
from .options import GAME_OPTION_NAMES, ChocoboTalesOptions
from .regions import can_goal, card_gift_hosts, create_regions
from .rewards import CARD_GIFTS
from .rom import ChocoboTalesProcedurePatch, write_patch
from .rom_patch import VANILLA_MD5

# Rescued chocobos that host microgames, and those that give card gifts
HOST_CHOCOBOS = frozenset({"Chocobo Dolly", "Chocobo Sweenie", "Chocobo Wakaba", "Chocobo Zavi"})
GIFT_CHOCOBOS = frozenset(f"Chocobo {host}" for card in CARD_GIFTS for host in card_gift_hosts(card))


class ChocoboTalesSettings(settings.Group):
    class RomFile(settings.UserFilePath):
        """File name of the Final Fantasy Fables: Chocobo Tales ROM (Europe)"""
        description = "Chocobo Tales (Europe) ROM File"
        copy_to = "FFF_ChocoboTales_Europe.nds"
        md5s = [VANILLA_MD5]

    rom_file: RomFile = RomFile(RomFile.copy_to)


class ChocoboTalesWeb(WebWorld):
    theme = "grassFlowers"
    bug_report_page = "https://github.com/Theo-Darvoux/ChocoboTalesAP/issues"
    tutorials = [Tutorial(
        "Multiworld Setup Guide",
        "A guide to setting up Chocobo Tales for Archipelago.",
        "English",
        "setup_en.md",
        "setup/en",
        ["Psders"],
    ), Tutorial(
        "Guide de configuration multimonde",
        "Un guide pour configurer Chocobo Tales pour Archipelago.",
        "Français",
        "setup_fr.md",
        "setup/fr",
        ["Psders"],
    )]


class ChocoboTalesWorld(World):
    """
    Final Fantasy Fables: Chocobo Tales is a Nintendo DS adventure where Chocobo jumps into storybooks,
    plays minigames and collects cards for Pop-up Duels to rescue the chocobos kidnapped by Bebuzzu.
    """
    game = GAME_NAME
    web = ChocoboTalesWeb()
    options_dataclass = ChocoboTalesOptions
    options: ChocoboTalesOptions
    settings: ClassVar[ChocoboTalesSettings]
    settings_key = "chocobo_tales_options"
    topology_present = False

    item_name_to_id = item_name_to_id
    location_name_to_id = location_name_to_id
    item_name_groups = item_name_groups
    location_name_groups = location_name_groups
    # Universal Tracker rebuilds the logic from slot data alone
    ut_can_gen_without_yaml = True

    @staticmethod
    def interpret_slot_data(slot_data: dict[str, Any]) -> dict[str, Any]:
        return slot_data

    def _regenerating(self) -> bool:
        return GAME_NAME in getattr(self.multiworld, "re_gen_passthrough", {})

    def generate_early(self) -> None:
        if self._regenerating():
            for key, value in self.multiworld.re_gen_passthrough[GAME_NAME].items():
                if key in GAME_OPTION_NAMES:
                    getattr(self.options, key).value = value

    def create_regions(self) -> None:
        create_regions(self)

    def create_items(self) -> None:
        from .items import CARD_PACK_NUMBERS

        cards = CARD_PACK_ITEMS if self.options.card_packs else CARD_ITEMS
        card_names = list(cards)
        self.random.shuffle(card_names)
        starting: set[str] = set()
        card_total = 0
        while card_names and card_total < self.options.starting_cards.value:
            name = card_names.pop()
            starting.add(name)
            card_total += len(CARD_PACK_NUMBERS[cards[name]]) if self.options.card_packs else 1
        chocobos = list(CHOCOBO_ITEMS)
        self.random.shuffle(chocobos)
        starting.update(chocobos[:self.options.starting_chocobos.value])
        if self.options.open_storybook_modes:
            starting.update(MODE_ITEMS)
        item_names = [*cards, *CHOCOBO_ITEMS, *MODE_ITEMS]
        if self.options.shuffle_epilogues:
            item_names.extend(EPILOGUE_ITEMS)
        unfilled = len(self.multiworld.get_unfilled_locations(self.player))
        if self.options.goal == self.options.goal.option_card_collection and card_total >= self.options.cards_required.value:
            raise ValueError("Card Collection goal is already complete with starting cards; raise Cards Required")
        if (self.options.goal == self.options.goal.option_chocobo_rescue
                and self.options.starting_chocobos.value >= self.options.chocobos_required.value):
            raise ValueError("Chocobo Rescue goal is already complete with starting chocobos; raise Chocobos Required")
        # The server sends the real starting items; this regeneration's random picks would differ
        for name in starting if not self._regenerating() else ():
            self.multiworld.push_precollected(self.create_item(name))
        pool = [self.create_item(name) for name in item_names if name not in starting]
        if len(pool) > unfilled:
            raise ValueError(f"Chocobo Tales: {len(pool)} items for {unfilled} checks. Use Card Packs, "
                             "enable more Storybook Goals Per Book or Microgame Medals, or turn off "
                             "Shuffle Epilogues; Starting Cards will not be silently increased.")
        pool += [self.create_filler() for _ in range(unfilled - len(pool))]
        self.multiworld.itempool += pool

    def set_rules(self) -> None:
        self.multiworld.completion_condition[self.player] = lambda state: can_goal(self, state)

    def create_item(self, name: str) -> ChocoboTalesItem:
        return ChocoboTalesItem(name, self._classification(name), self.item_name_to_id.get(name), self.player)

    def _classification(self, name: str) -> ItemClassification:
        if name in MODE_ITEMS or name == STORY_COMPLETE_EVENT:
            return ItemClassification.progression
        if name in EPILOGUE_ITEMS:
            return ItemClassification.useful
        if name in CHOCOBO_ITEMS:
            if (name in HOST_CHOCOBOS or (name in GIFT_CHOCOBOS and self.options.card_gift_checks)
                    or self.options.goal == self.options.goal.option_chocobo_rescue):
                return ItemClassification.progression
            return ItemClassification.useful
        if name in CARD_PACK_ITEMS:
            return ItemClassification.progression
        if name in CARD_ITEMS:
            # Any card can count toward a duel deck; many individual cards can overwhelm balancing.
            return ItemClassification.progression_skip_balancing
        return ItemClassification.filler

    def get_filler_item_name(self) -> str:
        return FILLER_ITEM

    def generate_output(self, output_directory: str) -> None:
        write_patch(self, output_directory)

    def fill_slot_data(self) -> dict[str, Any]:
        # Every option, so Universal Tracker can rebuild the logic; the client reads the goal settings
        return self.options.as_dict(*GAME_OPTION_NAMES)


__all__ = ["ChocoboTalesWorld", "ChocoboTalesProcedurePatch", "ChocoboTalesSettings"]
