"""
Tests the reward messages and the Archipelago card the ROM patch adds. Needs the vanilla ROM (CHOCOBO_TALES_ROM,
default ~/Applications/ROMs/NDS/FFF_ChocoboTales_Europe.nds): cd tests && python3 -m unittest test_reward_patch
"""
import os
import re
import struct
import unittest
from pathlib import Path

from load_world import load

world = load()
ROM_PATH = Path(os.environ.get("CHOCOBO_TALES_ROM", Path.home() / "Applications/ROMs/NDS/FFF_ChocoboTales_Europe.nds"))
LANGUAGES = world.text_patch.LANGUAGES


def all_location_items() -> dict[int, str]:
    return {location: f"Item {location}" for location in world.locations.location_name_to_id.values()}


@unittest.skipUnless(ROM_PATH.exists(), "vanilla ROM not found")
class TestRewardPatch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vanilla_bytes = ROM_PATH.read_bytes()
        cls.vanilla = world.nds.NDSRom(cls.vanilla_bytes)
        cls.items = all_location_items()
        cls.patched = world.nds.NDSRom(world.rom_patch.patch_rom(cls.vanilla_bytes, world.ram.BLOCKED_FLAGS, cls.items))

    def test_rom_size_and_old_files_keep_their_ids(self):
        # The base patch already stores the ARM9 binary uncompressed (a 128 MB cartridge in the header)
        base = world.rom_patch.patch_rom(self.vanilla_bytes, world.ram.BLOCKED_FLAGS)
        self.assertLess(len(self.patched.data) - len(base), 256 * 1024)
        changed = {self.vanilla.files[path] for path in self.vanilla.files
                   if self.patched.read(path, decompress=False) != self.vanilla.read(path, decompress=False)}
        for file_id in range(self.vanilla.fat_size // 8):
            if file_id not in changed and file_id >= 79:  # overlays are rebuilt uncompressed
                self.assertEqual(self.patched.read_id(file_id), self.vanilla.read_id(file_id), file_id)

    def test_every_field_card_message_names_its_item(self):
        for script, _, card, _, medal, _ in world.data.FIELD_CARD_GRANTS:
            location = world.rewards.field_grant_location(script, card, medal)
            act = world.text_patch.ActScript(self.patched.read(script))
            texts = [act.text(table, language) for table in act.text_tables() for language in LANGUAGES]
            self.assertFalse([t for t in texts if re.search(r"\n\d{3} ", t) and "card" in t.lower()], script)
            self.assertTrue(any(t.startswith("Objet trouvé :\n") and f"Item {location}" in t for t in texts),
                            (script, card))

    def test_missing_locations_say_there_is_nothing(self):
        items = {location: item for location, item in self.items.items() if not 4000 <= location < 5000}
        rom = world.nds.NDSRom(world.rom_patch.patch_rom(self.vanilla_bytes, world.ram.BLOCKED_FLAGS, items))
        act = world.text_patch.ActScript(rom.read("/field/150/49/cardget.act"))
        texts = [act.text(table, "fr") for table in act.text_tables()]
        self.assertIn("(Il n'y a rien à obtenir ici.)", texts)

    def test_result_screens_only_keep_rewards_still_given(self):
        blocked = world.ram.BLOCKED_FLAGS | world.rom_patch.ALWAYS_BLOCKED
        for language in LANGUAGES:
            for book in range(1, 17):
                result = world.text_patch.ResultData(self.patched.read(f"/mgame/result/{language}/MG{book:03d}.dat.z"))
                for goal in range(7):
                    records = result.records(goal)
                    ap = [r for r in records if r[1] == world.reward_patch.CARD and r[2] == world.ap_card.IMAGE_ID]
                    self.assertEqual(len(ap), len(world.rewards.goal_locations(book, goal)), (language, book, goal))
                    for offset, kind, value in records:
                        if (kind, value) != (world.reward_patch.CARD, world.ap_card.IMAGE_ID):
                            self.assertFalse(set(world.reward_patch.record_flags(book, kind, value)) & blocked)
                    for offset, _, _ in ap:
                        self.assertIn("Item ", result.record_text(offset))

    def test_book_1_battle_levels_stay(self):
        result = world.text_patch.ResultData(self.patched.read("/mgame/result/en/MG001.dat.z"))
        kinds = [kind for goal in range(7) for _, kind, _ in result.records(goal)]
        self.assertIn(world.reward_patch.FIRST_CLEAR_LEVELS, kinds)

    def test_goal_lists(self):
        texts = world.text_patch.read_ptx(self.patched.read("/mgentryphase/text/de/secret/cl003.ptx"))
        self.assertEqual(len(texts), 7)
        self.assertTrue(all(text.startswith("\x1bC\x1bGItem 103") for text in texts))

    def test_result_overlay_reads_the_card_copy(self):
        overlay = next(o for o in self.patched.overlays if o.cpu == "arm9" and o.overlay_id == 53)
        code = self.patched.overlay_data(overlay)
        self.assertIn(b"card\\&\\apcd.bin.z\0", code)
        self.assertNotIn(b"card\\&\\card.bin.z", code)

    def test_archipelago_card_files(self):
        for language in LANGUAGES:
            card_bin = self.patched.read(f"/card/{language}/apcd.bin.z")
            vanilla_bin = self.vanilla.read(f"/card/{language}/card.bin.z")
            count, table = struct.unpack_from("<II", card_bin, 0)
            self.assertEqual(count, 128)
            image_id, number, *_ = struct.unpack_from("<6I", card_bin, table + 24 * 127)
            self.assertEqual((image_id, number), (world.ap_card.IMAGE_ID, world.ap_card.NUMBER))
            # The vanilla card.bin the collection and duels read is unchanged
            self.assertEqual(self.patched.read(f"/card/{language}/card.bin.z"), vanilla_bin)
            name = self.patched.read(f"/card/{language}/name_2700.NCGR.z")
            self.assertEqual(len(name), len(self.vanilla.read(f"/card/{language}/name_2600.NCGR.z")))

    def test_archipelago_card_only_changes_the_picture(self):
        card = world.ap_card.Pbg(self.patched.read("/card/card_2700.pbg.z"))
        template = world.ap_card.Pbg(self.vanilla.read("/card/card_2600.pbg.z"))
        self.assertEqual(card.palette[0xE0:0xF0], template.palette[0xE0:0xF0])
        offsets = world.ap_card.card_pixel_offsets(self.vanilla.read("/card/card.NSCR.z"))
        changed = 0
        for pixel, offset in offsets.items():
            new = card.palette[card.data[card.tiles_offset + offset]]
            old = template.palette[template.data[template.tiles_offset + offset]]
            if world.ap_card.in_picture(*pixel):
                changed += new != old
            else:
                self.assertEqual(new, old, pixel)
        self.assertGreater(changed, 3000)

    def test_text_wrapping(self):
        font = world.font.Font(self.vanilla.read("/text/font.nftr"))
        lines = font.wrap(font.clean("Łódź " + "Supercalifragilistic" * 4), 120, 2)
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[1].endswith("…"))
        self.assertTrue(all(font.width(line) <= 120 for line in lines))
        self.assertTrue(lines[0].startswith("Lódz"))


if __name__ == "__main__":
    unittest.main()
