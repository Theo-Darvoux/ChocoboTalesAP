"""
Tests the ROM patch: rebuilds the ROM, then runs the patched game code (wrappers -> hooks -> the game's own flag
functions) in the unicorn ARM emulator to check which flag writes go through.
Needs the vanilla ROM (CHOCOBO_TALES_ROM, default ~/Applications/ROMs/NDS/FFF_ChocoboTales_Europe.nds) and
unicorn, so run it with ../../NDSTools/.venv/bin/python -m unittest test_rom_patch
"""
import hashlib
import os
import struct
import unittest
from pathlib import Path

from load_world import load

world = load()
ROM_PATH = Path(os.environ.get("CHOCOBO_TALES_ROM", Path.home() / "Applications/ROMs/NDS/FFF_ChocoboTales_Europe.nds"))

try:
    import unicorn
    from unicorn import arm_const
except ImportError:
    unicorn = None

BANK = 0x02300000  # fake save struct
RETURN = 0x00010000  # address the emulated call returns to


@unittest.skipUnless(ROM_PATH.exists(), "vanilla ROM not found")
class TestRomPatch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vanilla = ROM_PATH.read_bytes()
        cls.patched = world.rom_patch.patch_rom(cls.vanilla, world.ram.BLOCKED_FLAGS)
        cls.rom = world.nds.NDSRom(cls.patched)

    def test_vendored_rom_module_matches_ndstools(self):
        ndstools = Path(__file__).resolve().parents[2] / "NDSTools" / "ndstools" / "rom.py"
        vendored = Path(__file__).resolve().parents[1] / "chocobo_tales" / "nds.py"
        if ndstools.exists():
            self.assertEqual(vendored.read_text(), ndstools.read_text(), "copy NDSTools/ndstools/rom.py to nds.py")

    def test_vendored_font_module_matches_ndstools(self):
        ndstools = Path(__file__).resolve().parents[2] / "NDSTools" / "ndstools" / "nftr.py"
        vendored = Path(__file__).resolve().parents[1] / "chocobo_tales" / "font.py"
        if ndstools.exists():
            self.assertEqual(vendored.read_text(), ndstools.read_text(), "copy NDSTools/ndstools/nftr.py to font.py")

    def test_vanilla_rom_is_the_expected_one(self):
        self.assertEqual(hashlib.md5(self.vanilla).hexdigest(), world.rom_patch.VANILLA_MD5)

    def test_structure(self):
        rom, vanilla = self.rom, world.nds.NDSRom(self.vanilla)
        self.assertEqual(rom.module_params["compressed_static_end"], 0)
        self.assertEqual(rom.arm9_size, len(vanilla.arm9) + world.rom_patch.ITCM_BLOCK_SIZE)
        self.assertEqual(world.rom_patch.read_ap_data(self.patched), (True, ""))
        self.assertEqual(world.rom_patch.read_ap_data(self.vanilla)[0], False)
        # Every file and overlay is unchanged
        self.assertTrue(all(rom.read_id(i) == vanilla.read_id(i) for i in range(vanilla.fat_size // 8)))
        self.assertTrue(all(a == b for a, b in zip(rom.overlays, vanilla.overlays)))
        # Header checksum is valid
        self.assertEqual(world.nds.crc16(self.patched[:0x15E]), struct.unpack_from("<H", self.patched, 0x15E)[0])
        # The ITCM autoload block grew and still starts with the game's own code
        params = rom.module_params
        destination, size, _ = struct.unpack_from("<III", rom.arm9, params["autoload_list_start"] - 0x02000000)
        self.assertEqual((destination, size), (0x01FF8000, 0x6D00 + world.rom_patch.ITCM_BLOCK_SIZE))
        start = params["autoload_start"] - 0x02000000
        self.assertEqual(rom.arm9[start:start + 0x6D00], vanilla.arm9[start:start + 0x6D00])

    def test_epilogue_blocking_changes_per_seed(self):
        blocked = world.ram.BLOCKED_FLAGS | world.ram.EPILOGUE_FLAGS
        shuffled = world.nds.NDSRom(world.rom_patch.patch_rom(self.vanilla, blocked))
        params = shuffled.module_params
        start = params["autoload_start"] - 0x02000000
        bitmap_start = start + 0x6D00 + world.hooks.BITMAP_OFFSET
        bitmap = shuffled.arm9[bitmap_start:bitmap_start + world.hooks.FLAG_COUNT // 8]
        original = self.rom.arm9[bitmap_start:bitmap_start + world.hooks.FLAG_COUNT // 8]
        for flag in world.ram.EPILOGUE_FLAGS:
            bit = 1 << (flag & 7)
            self.assertFalse(original[flag >> 3] & bit)
            self.assertTrue(bitmap[flag >> 3] & bit)

    @unittest.skipIf(unicorn is None, "unicorn not installed")
    def test_hooks_in_emulated_game_code(self):
        params = self.rom.module_params
        arm9 = self.rom.arm9
        emu = unicorn.Uc(unicorn.UC_ARCH_ARM, unicorn.UC_MODE_ARM)
        emu.mem_map(0x01FF8000, 0x8000)  # ITCM
        emu.mem_map(0x02000000, 0x400000)  # main RAM
        emu.mem_map(RETURN, 0x1000)
        emu.mem_write(0x02000000, arm9[:params["autoload_start"] - 0x02000000])
        start = params["autoload_start"] - 0x02000000
        emu.mem_write(0x01FF8000, arm9[start:start + 0x6D00 + world.rom_patch.ITCM_BLOCK_SIZE])
        emu.mem_write(0x0209DDE0, struct.pack("<I", BANK))  # the save struct pointer

        def call(address: int, *args: int) -> None:
            for register, value in zip((arm_const.UC_ARM_REG_R0, arm_const.UC_ARM_REG_R1,
                                        arm_const.UC_ARM_REG_R2, arm_const.UC_ARM_REG_R3), args):
                emu.reg_write(register, value)
            emu.reg_write(arm_const.UC_ARM_REG_LR, RETURN)
            emu.reg_write(arm_const.UC_ARM_REG_SP, 0x02380000)
            emu.emu_start(address, RETURN, count=10_000)

        def is_set(flag: int) -> bool:
            offset, mask = world.flags.flag_position(flag)
            return bool(emu.mem_read(BANK + 0x24 + offset, 1)[0] & mask)

        def clear_bank() -> None:
            emu.mem_write(BANK, bytes(0x200))

        all_blocked = world.ram.BLOCKED_FLAGS | world.rom_patch.ALWAYS_BLOCKED
        blocked = sorted(all_blocked)
        allowed = [0x21, 0x43, 0x3DF, 0x7EE, 0x9F9, 0x480, 0x3E6, 0x7D8, 0x7DD, 0xA7F]
        self.assertFalse(set(allowed) & all_blocked)
        for flag in blocked + allowed:
            for wrapper, args in ((0x02001BE8, (flag,)), (0x02001C4C, (flag, 1, 1))):
                clear_bank()
                call(wrapper, *args)
                self.assertEqual(is_set(flag), flag not in all_blocked, f"{wrapper:#x} flag {flag:#x}")
                # nothing else in the bank changed
                set_count = sum(bin(b).count("1") for b in emu.mem_read(BANK + 0x24, 0x150))
                self.assertEqual(set_count, 0 if flag in all_blocked else 1)
        # Multi-bit fields and clearing always go through
        clear_bank()
        call(0x02001C4C, 0x3FB, 2, 3)
        self.assertTrue(is_set(0x3FB) and is_set(0x3FC))
        emu.mem_write(BANK + 0x24, b"\xff" * 0x150)
        card = blocked[0]
        call(0x02001C4C, card, 1, 0)
        self.assertFalse(is_set(card))


if __name__ == "__main__":
    unittest.main()
