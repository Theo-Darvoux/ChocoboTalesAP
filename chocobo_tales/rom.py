"""Archipelago patch file (.apcts) for Chocobo Tales: rebuilds the user's ROM with rom_patch, then writes the slot name."""
import json
import os
from typing import TYPE_CHECKING

import settings
from worlds.Files import APPatchExtension, APProcedurePatch, APTokenMixin, APTokenTypes

from . import ram
from .rom_patch import SLOT_NAME_OFFSET, SLOT_NAME_SIZE, VANILLA_MD5, patch_rom

if TYPE_CHECKING:
    from . import ChocoboTalesWorld


class ChocoboTalesPatchExtension(APPatchExtension):
    game = "Chocobo Tales"

    @staticmethod
    def build_ap_rom(caller: APProcedurePatch, rom: bytes) -> bytes:
        try:
            shuffle_epilogues = caller.get_file("shuffle_epilogues.bin") == b"\x01"
        except (KeyError, FileNotFoundError):
            # Patches generated before this option existed contain only token_data.bin.
            shuffle_epilogues = False
        blocked = ram.BLOCKED_FLAGS | (ram.EPILOGUE_FLAGS if shuffle_epilogues else frozenset())
        try:
            # Location id -> name of the item there, for the in-game reward messages
            location_items = {int(location): item for location, item in
                              json.loads(caller.get_file("location_items.json").decode("utf-8")).items()}
        except (KeyError, FileNotFoundError):
            # Patches from before reward messages named items keep the vanilla texts
            return patch_rom(rom, blocked)
        return patch_rom(rom, blocked, location_items)


class ChocoboTalesProcedurePatch(APProcedurePatch, APTokenMixin):
    game = "Chocobo Tales"
    hash = VANILLA_MD5
    patch_file_ending = ".apcts"
    result_file_ending = ".nds"
    procedure = [
        ("build_ap_rom", []),
        ("apply_tokens", ["token_data.bin"]),
    ]

    @classmethod
    def get_source_data(cls) -> bytes:
        with open(settings.get_settings().chocobo_tales_options.rom_file, "rb") as rom:
            return rom.read()


def write_patch(world: "ChocoboTalesWorld", output_directory: str) -> None:
    patch = ChocoboTalesProcedurePatch(player=world.player, player_name=world.player_name)
    name = world.player_name.encode("utf-8")[:SLOT_NAME_SIZE - 1]
    patch.write_token(APTokenTypes.WRITE, SLOT_NAME_OFFSET, name + bytes(SLOT_NAME_SIZE - len(name)))
    patch.write_file("token_data.bin", patch.get_token_binary())
    patch.write_file("shuffle_epilogues.bin", bytes([bool(world.options.shuffle_epilogues)]))
    location_items = {location.address: location.item.name
                      for location in world.multiworld.get_locations(world.player)
                      if location.address is not None and location.item is not None}
    patch.write_file("location_items.json", json.dumps(location_items).encode("utf-8"))
    out_file = os.path.join(output_directory,
                            f"{world.multiworld.get_out_file_name_base(world.player)}{patch.patch_file_ending}")
    patch.write(out_file)
