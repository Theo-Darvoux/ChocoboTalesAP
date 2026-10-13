"""
Test helper: shows a seed's reward texts and the Archipelago card in a savestate made on the vanilla ROM (BizHawk
only loads a state with the ROM it was made on). Builds the reward patch for made-up items, then injects the
changed files into the running research instance (NDSTools' ndstools/inject.py). New files can't be injected,
so the Archipelago card temporarily takes over image id 2600 (the Chocobo promo card) and card.bin itself.

    python3 -I tools/inject_ap_rewards.py STATE ITEM_NAME PATH_PART...

Only files whose path contains one of the PATH_PARTs are injected (the free space at the end of the ROM is
small), plus the Archipelago card's.
"""
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT.parent / "NDSTools"))

from load_world import load  # noqa: E402
from ndstools.bizhawk import BizHawk  # noqa: E402
from ndstools.inject import inject  # noqa: E402

VANILLA = Path.home() / "Applications/ROMs/NDS/FFF_ChocoboTales_Europe.nds"
STAND_IN = 2600


def main(state: str, item: str, *path_parts: str) -> None:
    world = load()
    ap_card = world.ap_card
    ap_card.IMAGE_ID = STAND_IN
    rom = world.nds.NDSRom(VANILLA.read_bytes())
    items = {location: f"{item} #{location}" for location in world.locations.location_name_to_id.values()}
    items.update({world.rewards.card_gift_location_id(card): f"{item} (gift {card})"
                  for card in world.rewards.CARD_GIFTS})
    blocked = world.ram.BLOCKED_FLAGS | {world.flags.card_flag(0)}
    replaced, added, _ = world.reward_patch.reward_patches(rom, items, blocked)
    files = dict(replaced)
    for path, data in added.items():
        if path.endswith("apcd.bin.z"):
            # Stand in for card.bin: the vanilla stand-in entry gets another id so lookups find the new one
            card_bin = bytearray(world.nds.lz_decompress(data))
            count, table = struct.unpack_from("<II", card_bin, 0)
            for i in range(count - 1):
                if struct.unpack_from("<I", card_bin, table + 24 * i)[0] == STAND_IN:
                    struct.pack_into("<I", card_bin, table + 24 * i, 9999)
            files[path.replace("apcd.bin.z", "card.bin.z")] = world.nds.lz10_compress(bytes(card_bin))
        else:
            files[path] = data
    files = {path: data for path, data in files.items()
             if path.startswith("/card/") or any(part in path for part in path_parts)}
    bh = BizHawk().connect()
    bh.load_state(state)
    inject(bh, rom, files)
    print(f"injected {len(files)} files")


if __name__ == "__main__":
    main(*sys.argv[1:])
