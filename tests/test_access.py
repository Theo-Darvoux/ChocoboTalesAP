"""
Checks the access tables (chocobo_tales/access.py) for consistency, and against the field scripts they were read from
when the vanilla ROM is available (CHOCOBO_TALES_ROM, default ~/Applications/ROMs/NDS/FFF_ChocoboTales_Europe.nds).
"""
import os
import re
import struct
import unittest
from pathlib import Path

from load_world import load

world = load()
access = world.access
ROM_PATH = Path(os.environ.get("CHOCOBO_TALES_ROM", Path.home() / "Applications/ROMs/NDS/FFF_ChocoboTales_Europe.nds"))


class TestAccessTables(unittest.TestCase):
    def test_every_location_kind_has_an_entry(self):
        self.assertEqual(set(access.MICROGAME_ACCESS), set(range(1, 24)))
        self.assertEqual(set(access.CARD_GIFT_ACCESS), set(world.rewards.CARD_GIFTS))

    def test_entries_are_valid(self):
        for table in (access.MICROGAME_ACCESS, access.CARD_GIFT_ACCESS):
            for key, entry in table.items():
                self.assertIn(entry.chapter, range(1, access.POST_GAME + 1), key)
                for name in (*entry.chocobos, *entry.owned):
                    self.assertIn(name, world.data.CHOCOBO_FRIEND_IDS, key)
                for book, epilogue in entry.epilogues:
                    self.assertIn((book, epilogue), access.GIMMICK_FLAGS, key)
                    # The location's chapter is no earlier than the storybook giving the epilogue
                    self.assertGreaterEqual(entry.chapter, world.data.STORYBOOK_STORY_CHAPTER[book], key)

    def test_story_epilogues_come_from_books_available_by_then(self):
        for chapter, epilogues in access.STORY_EPILOGUES.items():
            for book, _ in epilogues:
                self.assertLessEqual(world.data.STORYBOOK_STORY_CHAPTER[book], chapter, (chapter, book))

    def test_preset_goal_counts_need_chapter_5(self):
        # Storybook Goals and Gold Medals presets ask for more than chapters 1-4 hold
        books = sum(chapter <= 4 for chapter in world.data.STORYBOOK_STORY_CHAPTER.values())
        games = sum(entry.chapter <= 4 for entry in access.MICROGAME_ACCESS.values())
        for path in sorted((Path(__file__).resolve().parent.parent / "presets").glob("*.yaml")):
            options = dict(re.findall(r"^  (\w+): *([^ #\n]+)", path.read_text(), re.M))
            per_book = int(options["storybook_goals_per_book"])
            self.assertGreater(int(options["storybook_goals_required"]), books * per_book, path.name)
            self.assertLessEqual(int(options["storybook_goals_required"]), 16 * per_book, path.name)
            self.assertGreater(int(options["gold_medals_required"]), games, path.name)

    def test_ending_only_microgames(self):
        for game in (11, 15, 23):
            self.assertEqual(access.MICROGAME_ACCESS[game].chapter, access.POST_GAME)


def flag_writes(data: bytes) -> list[tuple[int, int]]:
    """(flag, value) of every immediate flag assignment (opcode 0) in a field script."""
    script = world.text_patch.ActScript(data)
    return [(args[0][1] & 0xFFFF, args[1][1]) for _, opcode, args in script.commands()
            if opcode == 0 and len(args) == 2 and args[0][0] == 4 and args[0][1] >> 16 == 1 and args[1][0] == 1]


@unittest.skipUnless(ROM_PATH.exists(), "vanilla ROM not found")
class TestAccessAgainstRom(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = world.nds.NDSRom(ROM_PATH.read_bytes())

    def test_gimmick_scripts_set_the_listed_flags(self):
        for (book, epilogue), flag in access.GIMMICK_FLAGS.items():
            name = f"Gimmick{(book + 1) // 2}{'A' if book % 2 else 'B'}{epilogue}.act".lower()
            paths = [p for p in self.rom.files if p.lower().endswith("/" + name)]
            self.assertTrue(paths, name)
            self.assertTrue(any((flag, 1) in flag_writes(self.rom.read(p)) for p in paths), (name, hex(flag)))

    def test_bookret_runs_each_gimmick_on_its_epilogue(self):
        for (book, epilogue), flag in access.GIMMICK_FLAGS.items():
            epilogue_flag = world.flags.epilogue_flag(book, epilogue)
            # The guard is (gimmick == 0) && (epilogue == 1), stored as a postfix expression
            guard = (b"\x00\x00\x04\x00\x00\x00" + struct.pack("<H", flag) + b"\x01\x00"
                     + b"\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x07\x00"
                     + b"\x00\x00\x04\x00\x00\x00" + struct.pack("<H", epilogue_flag) + b"\x01\x00")
            self.assertTrue(any(guard in self.rom.read(p) for p in self.rom.files if p.endswith("/bookret.act")),
                            (book, epilogue))

    def test_story_epilogues_are_in_the_skip_scripts(self):
        for chapter, epilogues in access.STORY_EPILOGUES.items():
            skip = access.STORY_SNAPSHOTS[chapter]
            written = {flag for flag, value in flag_writes(self.rom.read(f"/field/50/50/{skip}.act")) if value}
            for epilogue in epilogues:
                if epilogue != access.BOSS_EPILOGUES.get(chapter):
                    self.assertIn(access.GIMMICK_FLAGS[epilogue], written, (chapter, epilogue))
            self.assertIn(access.BOSS_EPILOGUES.get(chapter, epilogues[0]), epilogues, chapter)

    def test_boss_epilogues_start_the_bebuzzu_scene(self):
        for chapter, (book, epilogue) in access.BOSS_EPILOGUES.items():
            name = f"gimmick{(book + 1) // 2}{'a' if book % 2 else 'b'}{epilogue}.act"
            path = next(p for p in self.rom.files if p.lower().endswith("/" + name))
            folder = path.rsplit("/", 1)[0]
            x, y = (int(n) for n in folder.split("/")[2:4])
            script = world.text_patch.ActScript(self.rom.read(path))
            warps = [args for _, opcode, args in script.commands() if opcode == 0x29]
            self.assertTrue(warps, path)
            self.assertEqual((warps[-1][0][1], warps[-1][1][1]), (x, y), path)
            offset = script.base + warps[-1][2][1]
            scene = script.data[offset:script.data.index(0, offset)].decode()
            # The scene sets the flag that creates the Bebuzzu duel object in the tile's map.act
            scene_flags = {flag for flag, value in flag_writes(self.rom.read(scene)) if value}
            map_data = self.rom.read(f"{folder}/map.act")
            self.assertIn(b"bebuz.act", map_data.lower(), folder)
            self.assertTrue(any(b"\x00\x00\x04\x00\x00\x00" + struct.pack("<H", flag) + b"\x01\x00"
                                + b"\x00\x00\x01\x00\x00\x00\x01\x00\x00\x00\x07\x00" in map_data
                                for flag in scene_flags), (chapter, scene))
            self.assertEqual(world.data.STORYBOOK_STORY_CHAPTER[book], chapter, book)

    def test_ending_only_hosts_test_the_ending_flag(self):
        ending = b"\x04\x00\x00\x00" + struct.pack("<H", world.flags.STORY_COMPLETE_FLAG) + b"\x01\x00"
        for path in ("/field/49/49/swinny.act", "/field/49/49/wakaba.act", "/field/56/51/text1.act",
                     "/field/44/45/text1.act", "/field/45/51/text1.act", "/field/48/55/text1.act"):
            self.assertIn(ending, self.rom.read(path), path)

    def test_carbuncles_are_created_before_the_ending(self):
        # Map guards, as opposed to the optional jingle in carbuncle.act, determine when they appear.
        for path, guard_offsets, spawn_offset, flags in (
            ("/field/44/45/map.act", (0x764,), 0x7D4, (0xCD, 0x7F)),
            ("/field/149/52/map.act", (0x60, 0x6C), 0xDC, (0xCE, 0xC9, 0xCA, 0xCB, 0xCC, 0xCD)),
        ):
            script = world.text_patch.ActScript(self.rom.read(path))
            commands = script.commands()
            guards = [next(args for at, opcode, args in commands if at == offset and opcode == 5)
                      for offset in guard_offsets]
            self.assertTrue(all(spawn_offset < args[0][1] for args in guards), path)
            expressions = []
            for args in guards:
                start = script.base + args[0][0]
                end = start
                while True:
                    opcode = struct.unpack_from("<H", script.data, end)[0]
                    end += 10 if opcode == 0 else 2
                    if opcode == 15:
                        break
                expressions.append(script.data[start:end])
            expression = b"".join(expressions)
            for flag in flags:
                self.assertIn(struct.pack("<H", flag) + b"\x01\x00", expression, (path, flag))
            self.assertNotIn(struct.pack("<H", world.flags.STORY_COMPLETE_FLAG) + b"\x01\x00",
                             expression, path)
        self.assertEqual(access.CARD_GIFT_ACCESS[76].chapter, 6)
        self.assertEqual(access.CARD_GIFT_ACCESS[78].chapter, 6)

    def test_duplicate_microgame_launch_scripts_have_no_map_objects(self):
        for tile, name in (((49, 51), "game1.act"), ((50, 51), "game1.act")):
            folder = f"/field/{tile[0]}/{tile[1]}"
            self.assertIn((1, 0x10 + (12 if tile == (49, 51) else 14)),
                          [args[1] for _, opcode, args in world.text_patch.ActScript(
                              self.rom.read(f"{folder}/{name}")).commands() if opcode == 0x0A])
            map_script = world.text_patch.ActScript(self.rom.read(f"{folder}/map.act"))
            self.assertNotIn(f"{folder}/{name}".encode(), map_script.data)

    def test_giver_and_carbuncle_presence_flags_are_not_cleared(self):
        presence = {0x7F, 0x110, 0x112, 0x114, 0x119, 0xC9, 0xCA, 0xCB, 0xCC, 0xCD}
        assignments = {flag: set() for flag in presence}
        for path in self.rom.files:
            if not path.endswith(".act") or "/skip" in path:
                continue
            for flag, value in flag_writes(self.rom.read(path)):
                if flag in assignments:
                    assignments[flag].add(value)
        self.assertEqual(assignments, {flag: {1} for flag in presence})

    def test_story_snapshots_follow_the_previous_boss(self):
        # skipN has the flags chapter N - 1's boss scene sets; skipNpb, a point inside chapter N, doesn't have chapter
        # N's yet
        boss_scenes = {2: "/field/45/51/a3.act", 3: "/field/48/55/a2.act", 4: "/field/56/51/a4.act"}
        chapter_flags = set(world.flags.CHAPTER_COMPLETE_FLAGS.values())
        for chapter, scene in boss_scenes.items():
            flags = {flag for flag, value in flag_writes(self.rom.read(scene)) if value} - chapter_flags
            self.assertTrue(flags, scene)
            snapshot = {flag for flag, value in flag_writes(
                self.rom.read(f"/field/50/50/{access.STORY_SNAPSHOTS[chapter]}.act")) if value}
            before = {flag for flag, value in flag_writes(
                self.rom.read(f"/field/50/50/skip{chapter}pb.act")) if value}
            self.assertLessEqual(flags, snapshot, scene)
            self.assertFalse(flags & before, scene)

    def test_book_chapters_match_the_skip_snapshots(self):
        chapters = {}
        for skip, chapter in (("skip2", 1), ("skip2pb", 2), ("skip3", 2), ("skip3pb", 3), ("skip4", 3),
                              ("skip4pb", 4), ("skip5", 4), ("skip5pb", 5)):
            written = {flag for flag, value in flag_writes(self.rom.read(f"/field/50/50/{skip}.act")) if value}
            for book in range(1, 17):
                if 0x7E3 + 32 * (book - 1) in written:
                    chapters.setdefault(book, chapter)
        # Book 14's book object needs Gimmick8A1's flag 0x60, which skip5pb has; book 16 is a BOSS_EPILOGUES book
        self.assertIn(b"\x04\x00\x00\x00\x60\x00\x01\x00", self.rom.read("/field/47/45/map.act"))
        self.assertIn(0x60, {flag for flag, value in flag_writes(self.rom.read("/field/50/50/skip5pb.act")) if value})
        chapters.update({14: 5, 16: 5})
        for book in range(1, 17):
            self.assertEqual(world.data.STORYBOOK_STORY_CHAPTER[book], chapters[book], book)

    def test_book_13_is_reachable_in_chapter_4(self):
        # Only 56/50/sahagin.act sets 0x69, and skip4pb (before chapter 4's boss) has it: the player has been on
        # 56/50, whose map creates book.act (book 13) outside every condition
        writers = [path for path in self.rom.files if path.endswith(".act") and "/50/50/" not in path
                   and (0x69, 1) in flag_writes(self.rom.read(path))]
        self.assertEqual(writers, ["/field/56/50/sahagin.act"])
        self.assertIn((0x69, 1), flag_writes(self.rom.read("/field/50/50/skip4pb.act")))
        script = world.text_patch.ActScript(self.rom.read("/field/56/50/map.act"))
        commands = script.commands()
        book = next(at for at, opcode, args in commands if opcode == 0x26
                    and script.data[script.base + args[1][1]:].startswith(b"field/56/50/book.act"))
        self.assertFalse([at for at, opcode, args in commands if opcode == 5 and at < book < args[0][1]])
        self.assertEqual(world.data.STORYBOOK_STORY_CHAPTER[13], 4)

    def test_gold_needle_needs_moggy(self):
        # The Goblin (50/53/game1.act) tests 0x11E, which only 51/51/moggy.act sets; its object needs Moggy (0x10E)
        self.assertIn(b"\x04\x00\x00\x00\x1e\x01\x01\x00", self.rom.read("/field/50/53/game1.act"))
        self.assertIn((0x11E, 1), flag_writes(self.rom.read("/field/51/51/moggy.act")))
        moggy = 0x107 + world.data.CHOCOBO_FRIEND_IDS["Moggy"]
        self.assertIn(b"\x04\x00\x00\x00" + struct.pack("<H", moggy) + b"\x01\x00",
                      self.rom.read("/field/51/51/map.act"))
        self.assertIn("Moggy", access.MICROGAME_ACCESS[3].chocobos)

    def test_carbuncle_77_follows_chapter_2_boss(self):
        # 149/49's Carbuncle needs 0x34, which the chapter 2 boss scene sets (with the chapter 3 flag)
        self.assertIn((0x34, 1), flag_writes(self.rom.read("/field/45/51/a3.act")))
        self.assertIn(b"\x04\x00\x00\x00\x34\x00\x01\x00", self.rom.read("/field/149/49/map.act"))
        self.assertGreaterEqual(access.CARD_GIFT_ACCESS[77].chapter, 3)


if __name__ == "__main__":
    unittest.main()
