"""Loads the chocobo_tales modules that don't need Archipelago (everything but __init__, options, regions, rom, client)."""
import importlib.util
import sys
import types
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent / "chocobo_tales"


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
                 "rom_patch", "items", "locations", "ram"):
        spec = importlib.util.spec_from_file_location(f"ct_world.{name}", PACKAGE / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        modules[name] = module
    return types.SimpleNamespace(**modules)
