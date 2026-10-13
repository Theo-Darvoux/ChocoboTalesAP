"""
Drives a fresh Chocobo Tales boot (no save yet) to the field at the start of chapter 1, through the NDSTools bridge:
language select (English), title, new game in slot 1, name "ap", Story Mode, intro dialogue.

    python3 tools/new_game.py [screenshot_dir]

Timings are frame counts, so emulation speed doesn't matter.
"""
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT.parent / "NDSTools"))

from ndstools.bizhawk import BizHawk  # noqa: E402

STEPS = [
    ("boot", lambda bh: bh.frames(1000)),
    ("language", lambda bh: (bh.touch(47, 50), bh.frames(400))),
    ("intro", lambda bh: (bh.frames(600), bh.press("Start"), bh.frames(150))),
    ("title", lambda bh: (bh.touch(128, 96), bh.frames(180))),
    ("file select", lambda bh: (bh.touch(128, 48), bh.frames(180))),
    ("name", lambda bh: (bh.touch(73, 56), bh.touch(73, 104), bh.frames(20), bh.touch(225, 176), bh.frames(150))),
    ("main menu", lambda bh: (bh.touch(50, 40), bh.frames(500))),
    ("story intro", lambda bh: [bh.press("A") for _ in range(30)]),
    ("chapter 1", lambda bh: [(bh.touch(128, 175), bh.frames(40)) for _ in range(25)]),
]


def main() -> None:
    shots = Path(sys.argv[1]) if len(sys.argv) > 1 else PROJECT / "research" / "shots"
    shots.mkdir(parents=True, exist_ok=True)
    bh = BizHawk().connect()
    bh.pause(sticky=True)
    for name, step in STEPS:
        step(bh)
        print(f"{name}: frame {bh.frames(1)}, screenshot {bh.screenshot(shots / f'new_game_{name.replace(' ', '_')}.png')}")


if __name__ == "__main__":
    main()
