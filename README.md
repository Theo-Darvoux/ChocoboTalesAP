# Chocobo Tales for Archipelago

An [Archipelago](https://archipelago.gg) world for **Final Fantasy Fables: Chocobo Tales** (Nintendo DS, Europe),
played on [BizHawk](https://tasvideos.org/BizHawk) with its melonDS core.

Storybook goals, microgame medals, field cards, chocobo rescues, story chapters and card gifts become checks. The
127 Pop-up Duel cards, the rescued chocobos, the storybook battle and trial modes (and optionally the epilogues)
become items, shared with the other games of the multiworld. The patched game names the Archipelago item at every
reward message, in all five languages.

> **Status: experimental.** Generation, patching and the reward texts are tested; some access rules (microgame
> chapter timing, card gifts) are still conservative estimates. See [NOTES.md](NOTES.md).

## Download

Get the files from the [latest release](../../releases/latest):

| File | What it is |
|---|---|
| `chocobo_tales.apworld` | The world. Install it in Archipelago. |
| `chocobo_tales.yaml` | Preset: the full experience, every card is an item. |
| `chocobo_tales_compact.yaml` | Preset: monster Card Packs and fewer checks, for a shorter game. |
| `chocobo_tales_epilogues.yaml` | Preset: Card Packs, plus shuffled storybook epilogues. |

## Quick start

1. Install [Archipelago](https://github.com/ArchipelagoMW/Archipelago/releases) 0.6.7+ and
   [BizHawk](https://tasvideos.org/BizHawk/ReleaseHistory) 2.10+.
2. Double-click `chocobo_tales.apworld` (or **Install APWorld** in the Archipelago Launcher).
3. Pick a preset YAML, set your `name:`, and generate the game with the other players' YAMLs.
4. Open your `.apcts` patch with the Launcher's **Open Patch**; give it your Europe ROM (`AEHP`) when asked.
5. Load `connector_bizhawk_generic.lua` in BizHawk if it isn't loaded for you, connect the BizHawk Client and play.

Full tutorial: **[English](chocobo_tales/docs/setup_en.md)** · **[Français](chocobo_tales/docs/setup_fr.md)**.
Game page (checks, items, goals, logic): [en_Chocobo Tales.md](chocobo_tales/docs/en_Chocobo%20Tales.md).

## Supported versions

| | |
|---|---|
| Game | Europe only (`AEHP`, MD5 `a392490af90e31f2ce68d18b11833080`). No ROM is provided. |
| Archipelago | 0.6.7 or newer |
| Emulator | BizHawk 2.10 or newer (melonDS core) |

## Repository layout

```
chocobo_tales/   the apworld package (docs/ holds the tutorials and the game page)
presets/         YAML presets attached to every release
tests/           unit tests (stdlib; ROM tests skip without the ROM)
tools/           ROM data extraction and research scripts (need NDSTools)
build.sh         packs chocobo_tales/ into chocobo_tales.apworld
NOTES.md         reverse-engineering notes: memory map, ROM patch, test status
```

## Development

```sh
./build.sh --package-only        # build chocobo_tales.apworld
./build.sh                       # build and install it in ~/.local/share/Archipelago/worlds
cd tests && python3 -m unittest  # unit tests
```

The ROM tests (`test_rom_patch`, `test_reward_patch`) need the vanilla ROM: set `CHOCOBO_TALES_ROM` to its path.
`test_rom_patch` also needs [unicorn](https://pypi.org/project/unicorn/). The research tools in `tools/` import
NDSTools from a sibling `../NDSTools` checkout.

Pull requests run the unit tests and generate seeds from every preset with Archipelago (see
[.github/workflows](.github/workflows)).

### Releasing

1. Bump `world_version` in [chocobo_tales/archipelago.json](chocobo_tales/archipelago.json) and add a section to
   [CHANGELOG.md](CHANGELOG.md).
2. Tag the commit `v<world_version>` and push the tag. The release workflow checks that the tag matches,
   runs the tests, builds the apworld and publishes a GitHub release with the apworld and the presets.

## License

[MIT](LICENSE). Final Fantasy Fables: Chocobo Tales is © Square Enix. This project ships no ROM, graphics or game
files: the patch is built from your own ROM on your computer.
