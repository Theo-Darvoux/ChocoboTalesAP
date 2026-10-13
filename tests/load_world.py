"""Loads the chocobo_tales modules that don't need Archipelago (everything but __init__, options, regions, rom, client)."""
import importlib.util
import os
import sys
import types
import zipfile
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent / "chocobo_tales"
ROMS = Path.home() / "Applications/ROMs/NDS"
# Game code -> vanilla ROM (an .nds, or a .zip holding one)
ROM_PATHS = {
    "AEHP": Path(os.environ.get("CHOCOBO_TALES_ROM", ROMS / "FFF_ChocoboTales_Europe.nds")),
    "AEHE": Path(os.environ.get("CHOCOBO_TALES_US_ROM", ROMS / "chocobotalesusa.zip")),
}


def read_rom(game_code: str) -> bytes | None:
    """The vanilla ROM of that release, or None when it isn't there."""
    path = ROM_PATHS[game_code]
    if not path.exists():
        return None
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            names = [name for name in archive.namelist() if name.lower().endswith(".nds")]
            return archive.read(names[0]) if len(names) == 1 else None
    return path.read_bytes()


def load():
    if "BaseClasses" not in sys.modules:
        base = types.ModuleType("BaseClasses")
        base.Item = type("Item", (), {})
        base.Location = type("Location", (), {})
        sys.modules["BaseClasses"] = base
    package = types.ModuleType("ct_world")
    package.__path__ = [str(PACKAGE)]
    sys.modules["ct_world"] = package
    modules = {}
    for name in ("flags", "data", "hooks", "nds", "text_patch", "font", "rewards", "ap_card", "reward_patch",
                 "rom_patch", "items", "locations", "ram", "access"):
        spec = importlib.util.spec_from_file_location(f"ct_world.{name}", PACKAGE / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        modules[name] = module
    return types.SimpleNamespace(**modules)
