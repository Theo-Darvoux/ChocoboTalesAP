"""Compatibility tests for option data carried by generated .apcts files."""
import importlib.util
import sys
import types
import unittest
from unittest.mock import patch

from load_world import PACKAGE, load


class TestRomProcedure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.world = load()
        sys.modules.setdefault("settings", types.ModuleType("settings"))
        sys.modules.setdefault("worlds", types.ModuleType("worlds"))
        files = types.ModuleType("worlds.Files")
        files.APPatchExtension = type("APPatchExtension", (), {})
        files.APProcedurePatch = type("APProcedurePatch", (), {})
        files.APTokenMixin = type("APTokenMixin", (), {})
        files.APTokenTypes = type("APTokenTypes", (), {})
        sys.modules["worlds.Files"] = files
        spec = importlib.util.spec_from_file_location("ct_world.rom", PACKAGE / "rom.py")
        cls.rom = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cls.rom
        spec.loader.exec_module(cls.rom)

    def test_old_patch_without_option_byte_uses_original_bitmap(self):
        class OldPatch:
            def get_file(self, name):
                raise KeyError(name)

        with patch.object(self.rom, "patch_rom", return_value=b"patched") as build:
            self.assertEqual(self.rom.ChocoboTalesPatchExtension.build_ap_rom(OldPatch(), b"rom"), b"patched")
        build.assert_called_once_with(b"rom", self.world.ram.BLOCKED_FLAGS)

    def test_new_patch_selects_epilogue_bitmap(self):
        class NewPatch:
            def get_file(self, name):
                if name == "shuffle_epilogues.bin":
                    return b"\x01"
                raise KeyError(name)

        with patch.object(self.rom, "patch_rom", return_value=b"patched") as build:
            self.rom.ChocoboTalesPatchExtension.build_ap_rom(NewPatch(), b"rom")
        build.assert_called_once_with(b"rom", self.world.ram.BLOCKED_FLAGS | self.world.ram.EPILOGUE_FLAGS)

    def test_patch_with_location_items_names_them(self):
        class ItemsPatch:
            def get_file(self, name):
                files = {"shuffle_epilogues.bin": b"\x00",
                         "location_items.json": b'{"4103": "Progressive Hookshot", "1010": "Cactuar - Ambush"}'}
                return files[name]

        with patch.object(self.rom, "patch_rom", return_value=b"patched") as build:
            self.rom.ChocoboTalesPatchExtension.build_ap_rom(ItemsPatch(), b"rom")
        build.assert_called_once_with(b"rom", self.world.ram.BLOCKED_FLAGS,
                                      {4103: "Progressive Hookshot", 1010: "Cactuar - Ambush"})


if __name__ == "__main__":
    unittest.main()
