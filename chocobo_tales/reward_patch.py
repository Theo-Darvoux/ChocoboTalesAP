"""
Makes the game announce Archipelago items instead of the vanilla rewards it no longer gives. No Archipelago imports.

- Field scripts: every "You obtain the ... pop-up card!" message names the item at its location instead (or says
  there is nothing to get, when that location isn't part of the seed).
- Storybook result screens (/mgame/result/<lang>/MGNNN.dat): each completed goal's blocked rewards are replaced by
  one Archipelago card per location the goal checks (the goal, then its chocobo rescue), with the item's name.
  Rewards the game still gives (e.g. book 1's battle levels, epilogues when they aren't shuffled) stay.
- Storybook goal lists (/mgentryphase/text/<lang>/secret/clNNN.ptx): the reward shown next to each goal.
- The Archipelago card itself: an extra card (ap_card.py) in a copy of card.bin that only the result screen
  (overlay 53) reads, so the collection, decks and duels never see it.
"""
import re
from collections.abc import Iterable

from . import ap_card, flags
from .data import FIELD_CARD_GRANTS, STORYBOOK_GOALS
from .font import Font
from .nds import NDSRom, lz10_compress
from .rewards import field_grant_location, goal_locations
from .text_patch import LANGUAGES, ActScript, ResultData, read_ptx, write_ptx

FOUND = {"en": "Item found:", "fr": "Objet trouvé :", "de": "Gegenstand gefunden:", "it": "Oggetto trovato:",
         "es": "Objeto encontrado:"}
NOTHING = {"en": "(There is nothing to obtain here.)", "fr": "(Il n'y a rien à obtenir ici.)",
           "de": "(Hier gibt es nichts zu holen.)", "it": "(Qui non c'è niente da ottenere.)",
           "es": "(Aquí no hay nada que obtener.)"}

# Text box widths in pixels of /text/font.nftr, a little under the widest vanilla line of each box
FIELD_WIDTH = 205
RESULT_WIDTH = 180
GOAL_LIST_WIDTH = 180

# Storybook result record types (see NOTES.md)
BATTLE_LEVELS, EPILOGUE, TRIAL_MODE, CARD, CHOCOBO, FIRST_CLEAR_LEVELS = range(6)

OVERLAY_RESULT = 53
OVERLAY_CARD_BIN_PATH = b"card\\&\\card.bin.z"


def item_text(font: Font, item: str, width: int, lines: int) -> list[str]:
    return font.wrap(font.clean(" ".join(item.split())), width, lines)


def found_message(font: Font, language: str, item: str | None, width: int) -> str:
    if item is None:
        return "\n".join(font.wrap(NOTHING[language], width, 3))
    return "\n".join([FOUND[language], *item_text(font, item, width, 2)])


def record_flags(book: int, kind: int, value: int) -> list[int]:
    """The flags a storybook result record sets."""
    if kind in (BATTLE_LEVELS, FIRST_CLEAR_LEVELS):
        return [flags.battle_level_flag(book, level) for level in range(1, 6) if value >> level & 1]
    if kind == EPILOGUE:
        return [flags.epilogue_flag(book, value)]
    if kind == TRIAL_MODE:
        return [flags.trial_mode_flag(book)]
    if kind == CARD:
        return [flags.card_flag(0)]  # every card flag is blocked; the number doesn't matter here
    if kind == CHOCOBO:
        return [flags.chocobo_flag(value)]
    raise ValueError(f"unknown reward record type {kind}")


def vanilla_goal_reward_blocked(book: int, goal_index: int, blocked: frozenset[int]) -> bool:
    """Whether the reward the goal list names for this goal is one the patched game no longer gives."""
    _, kind, value = STORYBOOK_GOALS[book - 1][goal_index]
    if kind in ("card", "chocobo"):
        return True
    if kind == "epilogue":
        return flags.epilogue_flag(book, int(value)) in blocked
    if kind == "mode":
        if value == "Trial":
            return flags.trial_mode_flag(book) in blocked
        return any(flags.battle_level_flag(book, level) in blocked for level in range(1, 6))
    return False


def patch_field_scripts(rom: NDSRom, font: Font, location_items: dict[int, str]) -> dict[str, bytes]:
    grants = {(script, card): field_grant_location(script, card, medal)
              for script, _, card, _, medal, _ in FIELD_CARD_GRANTS}
    files = {}
    for script_path in sorted({script for script, *_ in FIELD_CARD_GRANTS}):
        script = ActScript(rom.read(script_path))
        for table in sorted(set(script.text_tables())):
            match = re.match(r"You obtain the\n(\d{3}) ", script.text(table, "en"))
            if not match:
                continue
            item = location_items.get(grants[(script_path, int(match.group(1)))])
            script.set_text(table, {language: found_message(font, language, item, FIELD_WIDTH)
                                    for language in LANGUAGES})
        files[script_path] = script.to_bytes()
    return files


def patch_storybooks(rom: NDSRom, font: Font, location_items: dict[int, str],
                     blocked: frozenset[int]) -> dict[str, bytes]:
    files = {}
    for language in LANGUAGES:
        for book in range(1, 17):
            path = f"/mgame/result/{language}/MG{book:03d}.dat.z"
            result = ResultData(rom.read(path))
            for goal_index in range(ResultData.GOALS):
                items = [location_items[location] for location in goal_locations(book, goal_index)
                         if location in location_items]
                ap_records = [(CARD, "\n".join([FOUND[language], *item_text(font, item, RESULT_WIDTH, 2)]),
                               ap_card.IMAGE_ID) for item in items]
                records = []
                for kind, text, value in result.raw_records(goal_index):
                    if any(flag in blocked for flag in record_flags(book, kind, value)):
                        records += ap_records
                        ap_records = []
                    else:
                        records.append((kind, text, value))
                result.replace_records(goal_index, records + ap_records)
            files[path] = lz10_compress(result.to_bytes())

            path = f"/mgentryphase/text/{language}/secret/cl{book:03d}.ptx"
            texts = read_ptx(rom.read(path))
            for goal_index in range(len(texts)):
                items = [location_items[location] for location in goal_locations(book, goal_index)
                         if location in location_items]
                if items:
                    line = item_text(font, " / ".join(items), GOAL_LIST_WIDTH, 1)[0]
                    texts[goal_index] = f"\x1bC\x1bG{line}\x1b\x1b"
                elif vanilla_goal_reward_blocked(book, goal_index, blocked):
                    texts[goal_index] = ""
            files[path] = write_ptx(texts)
    return files


def patch_result_overlay(rom: NDSRom) -> bytes:
    """Overlay 53's code with its card.bin path pointing at the copy that also holds the Archipelago card."""
    overlay = next(o for o in rom.overlays if o.cpu == "arm9" and o.overlay_id == OVERLAY_RESULT)
    code = bytearray(rom.overlay_data(overlay))
    at = code.find(OVERLAY_CARD_BIN_PATH + b"\0")
    if at < 0 or code.count(OVERLAY_CARD_BIN_PATH) != 1:
        raise ValueError("unexpected overlay 53; is this the vanilla EU ROM?")
    new_path = ap_card.CARD_BIN_PATH.encode("ascii")
    assert len(new_path) == len(OVERLAY_CARD_BIN_PATH)
    code[at:at + len(new_path)] = new_path
    return bytes(code)


def reward_patches(rom: NDSRom, location_items: dict[int, str], blocked: Iterable[int]
                   ) -> tuple[dict[str, bytes], dict[str, bytes], dict[int, bytes]]:
    """(replaced files by path, new files by path, replaced overlays by id)"""
    blocked = frozenset(blocked)
    font = Font(rom.read("/text/font.nftr"))
    replaced = {**patch_field_scripts(rom, font, location_items),
                **patch_storybooks(rom, font, location_items, blocked)}
    added = ap_card.new_files(rom)
    return replaced, added, {OVERLAY_RESULT: patch_result_overlay(rom)}
