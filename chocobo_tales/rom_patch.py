"""
Builds the Archipelago version of Final Fantasy Fables: Chocobo Tales (Europe or USA) from the vanilla ROM.
No Archipelago imports, so it can be used and tested on its own.

What changes:
- The ARM9 binary is stored uncompressed (nds.build_rom re-lays out the ROM around it).
- Its ITCM autoload block grows by 0x260 bytes holding the flag-write hooks (hooks.py) and a bitmap of blocked
  flags. The game's set-flag and set-field wrappers jump to the hooks, so the game can no longer give itself
  anything Archipelago hands out (cards, rescued chocobos, most storybook mode unlocks, and optionally epilogues).
  Everything else is unchanged.
- A small Archipelago data block goes into the unused area between the header and the ARM9 binary: a magic
  marker and, written per seed by the patch tokens, the slot name the client logs in with.
- Reward messages and the storybook result screens announce the Archipelago item at each location instead of the
  vanilla reward (reward_patch.py), with an Archipelago card (ap_card.py) in place of the vanilla card picture.
"""
import struct
from collections.abc import Iterable
from typing import NamedTuple

from . import ap_card, flags, hooks
from .nds import NDSRom
from .reward_patch import reward_patches
from .text_patch import LANGUAGES


class Version(NamedTuple):
    """What differs between the supported releases. Everything else (files, flags, scripts) is the same."""
    region: str
    md5: str
    set_wrapper: int  # set(flag)
    set_field_wrapper: int  # set_field(flag, width, value)
    save_pointer: int  # global holding the save struct's address
    languages: tuple[str, ...]  # text languages the release has


VERSIONS: dict[str, Version] = {
    "AEHP": Version("Europe", "a392490af90e31f2ce68d18b11833080", 0x02001BE8, 0x02001C4C, 0x0209DDE0, LANGUAGES),
    # Same code shifted by 0x7C before the wrappers; English only (its .act text tables keep unused French, German
    # and Spanish leftovers, and Japanese)
    "AEHE": Version("USA", "06d12ca36fcd88c32c276affe792ae61", 0x02001B6C, 0x02001BD0, 0x0209DBF8, ("en",)),
}
VANILLA_MD5 = VERSIONS["AEHP"].md5  # the .apcts manifest's base checksum (informative only)
VANILLA_MD5S = [version.md5 for version in VERSIONS.values()]

AP_DATA_OFFSET = 0x1000
AP_MAGIC = b"APCHOCO\x01"  # last byte: patch format version
SLOT_NAME_OFFSET = 0x1010
SLOT_NAME_SIZE = 0x40

ARM9_BASE = 0x02000000
ITCM_BLOCK_SIZE = 0x260  # hook code at +0, blocked-flag bitmap (0x150 bytes) at +0x100
# First instructions of the wrappers in the vanilla game, checked before patching over them
SET_WRAPPER_ORIGINAL = bytes.fromhex("10209fe50010a0e1")
SET_FIELD_WRAPPER_ORIGINAL = bytes.fromhex("08402de91c309fe5")


# Blocked whatever the options: the Archipelago card's number is 0, so a result screen reward of it would set 0x400
ALWAYS_BLOCKED = frozenset({flags.card_flag(ap_card.NUMBER)})


def jump(target: int) -> bytes:
    """ldr pc, [pc, #-4] followed by the target address: an absolute jump in 8 bytes."""
    return struct.pack("<II", 0xE51FF004, target)


def blocked_bitmap(blocked_flags: Iterable[int]) -> bytes:
    bitmap = bytearray(hooks.FLAG_COUNT // 8)
    for flag in blocked_flags:
        if not 0 <= flag < hooks.FLAG_COUNT:
            raise ValueError(f"flag {flag:#x} is outside the hooks' range")
        bitmap[flag >> 3] |= 1 << (flag & 7)
    return bytes(bitmap)


def rom_version(rom: NDSRom) -> Version:
    if rom.game_code not in VERSIONS:
        raise ValueError(f"expected Chocobo Tales Europe (AEHP) or USA (AEHE), got {rom.game_code}")
    return VERSIONS[rom.game_code]


def patch_arm9(rom: NDSRom, blocked_flags: Iterable[int]) -> bytes:
    version = rom_version(rom)
    arm9 = bytearray(rom.arm9)  # decompressed, compressed_static_end already cleared
    params = rom.module_params
    if params is None:
        raise ValueError("ARM9 module params not found")

    def offset(address: int) -> int:
        return address - ARM9_BASE

    for address, original in ((version.set_wrapper, SET_WRAPPER_ORIGINAL),
                              (version.set_field_wrapper, SET_FIELD_WRAPPER_ORIGINAL)):
        if arm9[offset(address):offset(address) + len(original)] != original:
            raise ValueError(f"unexpected code at {address:#010x}; is this a vanilla ROM?")

    list_start = offset(params["autoload_list_start"])
    itcm_destination, itcm_size, _ = struct.unpack_from("<III", arm9, list_start)
    if itcm_destination + itcm_size != hooks.BASE:
        raise ValueError("unexpected ITCM autoload block")

    assert hooks.BITMAP_OFFSET + hooks.FLAG_COUNT // 8 <= ITCM_BLOCK_SIZE and hooks.BASE + ITCM_BLOCK_SIZE <= 0x02000000
    block = bytearray(ITCM_BLOCK_SIZE)
    code = hooks.CODE[rom.game_code]
    block[:len(code)] = code
    bitmap = blocked_bitmap(blocked_flags)
    block[hooks.BITMAP_OFFSET:hooks.BITMAP_OFFSET + len(bitmap)] = bitmap
    insert_at = offset(params["autoload_start"]) + itcm_size
    arm9[insert_at:insert_at] = block

    # Everything after the ITCM block (the DTCM block and the autoload list) moved by ITCM_BLOCK_SIZE
    list_start += ITCM_BLOCK_SIZE
    struct.pack_into("<I", arm9, list_start + 4, itcm_size + ITCM_BLOCK_SIZE)
    struct.pack_into("<II", arm9, params["offset"],
                     params["autoload_list_start"] + ITCM_BLOCK_SIZE, params["autoload_list_end"] + ITCM_BLOCK_SIZE)

    arm9[offset(version.set_wrapper):offset(version.set_wrapper) + 8] = jump(hooks.HOOK_SET)
    arm9[offset(version.set_field_wrapper):offset(version.set_field_wrapper) + 8] = jump(hooks.HOOK_SET_FIELD)
    return bytes(arm9)


def patch_rom(vanilla: bytes, blocked_flags: Iterable[int], location_items: dict[int, str] | None = None) -> bytes:
    """
    location_items: location id -> name of the item placed there, for every location of this slot. Reward messages
    for locations that aren't in it say there is nothing to get. None leaves every reward text unchanged.
    """
    rom = NDSRom(vanilla)
    version = rom_version(rom)
    blocked = frozenset(blocked_flags) | ALWAYS_BLOCKED
    files: dict[int, bytes] = {}
    new_files: dict[str, bytes] = {}
    overlays: dict[int, bytes] = {}
    if location_items is not None:
        replaced, new_files, overlays = reward_patches(rom, location_items, blocked, version.languages)
        files = {rom.files[path]: data for path, data in replaced.items()}
    return rom.build(arm9=patch_arm9(rom, blocked), files=files, new_files=new_files, overlays=overlays,
                     header_patches={AP_DATA_OFFSET: AP_MAGIC, SLOT_NAME_OFFSET: bytes(SLOT_NAME_SIZE)})


def read_ap_data(rom: bytes) -> tuple[bool, str]:
    """(is an Archipelago-patched ROM, slot name)"""
    patched = rom[AP_DATA_OFFSET:AP_DATA_OFFSET + len(AP_MAGIC)] == AP_MAGIC
    name = rom[SLOT_NAME_OFFSET:SLOT_NAME_OFFSET + SLOT_NAME_SIZE].split(b"\0", 1)[0].decode("utf-8", "replace")
    return patched, name
