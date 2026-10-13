import unittest

from load_world import load

world = load()
ram = world.ram


class TestRam(unittest.TestCase):
    def test_story_order_from_skip_scripts(self):
        self.assertEqual(world.data.STORYBOOK_STORY_CHAPTER[1], 1)
        self.assertEqual(world.data.STORYBOOK_STORY_CHAPTER[5], 2)
        # No storybook waits for chapter 6: books 14 and 16 (in no skip script) are chapter 5's
        self.assertEqual(max(world.data.STORYBOOK_STORY_CHAPTER.values()), 5)
        self.assertEqual(world.data.STORYBOOK_STORY_CHAPTER[14], 5)
        self.assertEqual(world.data.STORYBOOK_STORY_CHAPTER[16], 5)

    def test_every_location_and_item_has_flags(self):
        self.assertEqual(set(ram.LOCATION_FLAGS), set(world.locations.location_name_to_id.values()))
        items = set(world.items.item_name_to_id.values()) - {world.items.item_name_to_id[world.items.FILLER_ITEM]}
        self.assertEqual(set(ram.ITEM_FLAGS), items)

    def test_flags_found_in_the_code(self):
        # Storybook 1's goal flags are set by overlay 3, microgame 1's medals by overlay 23
        self.assertEqual([world.flags.storybook_goal_flag(1, goal) for goal in range(7)], list(range(0x7EE, 0x7F5)))
        self.assertEqual(world.flags.microgame_flag(1, "Silver"), 0x9F9)
        self.assertEqual(world.flags.microgame_flag(1, "Gold"), 0x9FA)
        self.assertEqual(ram.ITEM_FLAGS[world.items.CHOCOBO_ITEMS["Chocobo Sweenie"]], [0x3E6 + 17])
        # Chapters open with flags 0x43, 0x45, ... (set by each chapter's opening script)
        self.assertEqual(ram.LOCATION_FLAGS[world.locations.CHAPTER_LOCATION_IDS["Chapter 1 Complete"]], 0x43)

    def test_mode_items(self):
        # Every storybook's goals unlock some battle levels; all but book 1 (vanilla, story-required) have a Modes item
        self.assertEqual(len(world.items.MODE_ITEMS), 15)
        self.assertNotIn(1, world.items.BOOK_MODE_ITEM)
        # Book 1: levels 1-5 come from its rewards; book 3 also unlocks trial mode; book 6 too ("Unlocked Trial Mode")
        self.assertEqual(world.items.MODE_UNLOCKS[1], (frozenset({1, 2, 3, 4, 5}), False))
        self.assertTrue(world.items.MODE_UNLOCKS[3][1] and world.items.MODE_UNLOCKS[6][1])
        book6 = world.items.BOOK_MODE_ITEM[6]
        self.assertIn(world.flags.trial_mode_flag(6), ram.ITEM_FLAGS[world.items.MODE_ITEMS[book6]])

    def test_first_adamantoise_race_unlocks_required_battle(self):
        unlocks = ram.STORYBOOK_01_VANILLA_MODE_UNLOCKS
        self.assertEqual(unlocks, {
            world.flags.battle_level_flag(1, 1): world.flags.storybook_goal_flag(1, 0),
            world.flags.battle_level_flag(1, 2): world.flags.storybook_goal_flag(1, 1),
            **{world.flags.battle_level_flag(1, level): world.flags.storybook_goal_flag(1, 2)
               for level in (3, 4, 5)},
        })
        self.assertFalse(unlocks.keys() & ram.BLOCKED_FLAGS)
        self.assertIn(world.flags.battle_level_flag(2, 1), ram.BLOCKED_FLAGS)

    def test_default_blocked_flags_exclude_checks_and_epilogues(self):
        self.assertEqual(len([f for f in ram.BLOCKED_FLAGS if 0x401 <= f <= 0x47F]), 127)
        # Nothing a location checks is blocked, or checks could never be sent
        self.assertFalse(set(ram.LOCATION_FLAGS.values()) & ram.BLOCKED_FLAGS)

    def test_card_packs_and_epilogues(self):
        self.assertEqual(len(world.items.CARD_PACK_ITEMS), 26)
        self.assertEqual(len(world.items.CARD_PACK_ITEMS), len(world.items.MONSTER_CARDS))
        packed = [number for numbers in world.items.CARD_PACK_NUMBERS.values() for number in numbers]
        self.assertEqual(sorted(packed), list(range(1, 128)))
        for item_id, numbers in world.items.CARD_PACK_NUMBERS.items():
            self.assertEqual(ram.ITEM_FLAGS[item_id], [world.flags.card_flag(number) for number in numbers])
        self.assertEqual(len(ram.EPILOGUE_FLAGS), 48)
        self.assertEqual(ram.ITEM_FLAGS[world.items.EPILOGUE_ITEMS["Storybook 01 Epilogue 1"]], [0x7D8])
        self.assertFalse(ram.EPILOGUE_FLAGS & ram.BLOCKED_FLAGS)

    def test_field_card_pickups_are_checks_not_card_ownership(self):
        pickups = world.locations.FIELD_CARD_LOCATIONS
        self.assertEqual(len(pickups), 9)
        self.assertEqual(set(world.locations.FIELD_CARD_LOCATION_IDS), set(pickups))
        for name, (number, pickup_flag, _) in pickups.items():
            self.assertEqual(ram.LOCATION_FLAGS[world.locations.FIELD_CARD_LOCATION_IDS[name]], pickup_flag)
            self.assertNotEqual(pickup_flag, world.flags.card_flag(number))
            self.assertNotIn(pickup_flag, ram.BLOCKED_FLAGS)
            self.assertIn(world.flags.card_flag(number), ram.BLOCKED_FLAGS)

    def test_chocobo_rescues_use_goal_completion_not_ownership(self):
        rescues = world.locations.RESCUE_LOCATIONS
        self.assertEqual(len(rescues), len(world.items.CHOCOBO_ITEMS))
        self.assertEqual({name.removeprefix("Rescue ") for name in rescues}, set(world.items.CHOCOBO_ITEMS))
        for name, goal in rescues.items():
            location_id = world.locations.RESCUE_LOCATION_IDS[name]
            goal_flag = world.flags.storybook_goal_flag(goal.book, goal.goal_index)
            self.assertEqual(ram.LOCATION_FLAGS[location_id], goal_flag)
            self.assertNotIn(goal_flag, ram.BLOCKED_FLAGS)
            friend = name.removeprefix("Rescue Chocobo ")
            self.assertIn(("chocobo", world.data.CHOCOBO_FRIEND_IDS[friend]),
                          world.data.STORYBOOK_REWARD_RECORDS[goal.book - 1][goal.goal_index])
            item_id = world.items.CHOCOBO_ITEMS[name.removeprefix("Rescue ")]
            self.assertNotIn(goal_flag, ram.ITEM_FLAGS[item_id])
            self.assertTrue(all(flag in ram.BLOCKED_FLAGS for flag in ram.ITEM_FLAGS[item_id]))

    def test_flag_position(self):
        # Flag 0x21 is the only flag set in a fresh chapter 1 save: word 1, value 0x40000000
        self.assertEqual(ram.flag_position(0x21), (4 + 3, 0x40))
        self.assertEqual(ram.flag_position(0), (3, 0x80))
        self.assertEqual(ram.flag_position(31), (0, 0x01))


if __name__ == "__main__":
    unittest.main()
