"""Checks the YAML presets in presets/ stay generic: no player name, and one fixed value per option."""
import re
import unittest
from pathlib import Path


PRESETS = sorted((Path(__file__).resolve().parent.parent / "presets").glob("*.yaml"))
OPTION = re.compile(r"^  (\w+):(.*)$")


def preset_options(path: Path) -> dict[str, str]:
    """Option key -> value, for the two-space-indented keys under the game's section."""
    options = {}
    for line in path.read_text().splitlines():
        if match := OPTION.match(line):
            options[match.group(1)] = match.group(2).split("#", 1)[0].strip()
    return options


class TestPresets(unittest.TestCase):
    def test_presets_exist_with_snake_case_names(self):
        self.assertTrue(PRESETS)
        for path in PRESETS:
            self.assertRegex(path.name, r"^[a-z0-9_]+\.yaml$")

    def test_generic_player_name(self):
        for path in PRESETS:
            self.assertIn("\nname: Player{number}\n", path.read_text(), path.name)

    def test_every_option_has_one_fixed_value(self):
        for path in PRESETS:
            for key, value in preset_options(path).items():
                self.assertTrue(value, f"{path.name}: {key} is weighted or empty")
