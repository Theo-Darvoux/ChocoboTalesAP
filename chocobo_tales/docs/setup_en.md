# Chocobo Tales Setup Guide

This guide covers everything from installing the apworld to playing a multiworld session.

## Required software

- [Archipelago](https://github.com/ArchipelagoMW/Archipelago/releases) 0.6.7 or newer
- [BizHawk](https://tasvideos.org/BizHawk/ReleaseHistory) 2.10 or newer (its NDS core is melonDS)
  - Windows: run the BizHawk prerequisites installer first.
  - Linux: BizHawk needs Mono; start it with `EmuHawkMono.sh`.
- The Chocobo Tales apworld: `chocobo_tales.apworld` from the
  [latest release](https://github.com/Theo-Darvoux/ChocoboTalesAP/releases/latest)
- A Final Fantasy Fables: Chocobo Tales ROM, **Europe** version (game code `AEHP`,
  MD5 `a392490af90e31f2ce68d18b11833080`) or **USA** version (game code `AEHE`,
  MD5 `06d12ca36fcd88c32c276affe792ae61`). You have to dump it yourself; it is not provided.

## Optional software

- [Universal Tracker](https://github.com/FarisTheAncient/Archipelago/releases), which works with this world
  without a YAML file.

## Installing the apworld

1. Download `chocobo_tales.apworld` from the latest release.
2. Double-click it, or open the Archipelago Launcher and click **Install APWorld**, then pick the file. Either
   way it ends up in the `custom_worlds` folder of your Archipelago install.
3. Restart the Launcher. "Chocobo Tales" should now be in its list of games.

To update, install the new `.apworld` the same way; it replaces the old one. Everyone generating or playing a
seed should use the same apworld version.

## Creating your options file (YAML)

Your YAML file holds your slot name and the options of your world. Pick one of these ways to get one:

- **Presets from the release** (recommended): download one of the preset files and edit it in a text editor.
  - `chocobo_tales.yaml`: the full experience, with every card as its own item.
  - `chocobo_tales_compact.yaml`: monster Card Packs and fewer checks, for a shorter game.
  - `chocobo_tales_epilogues.yaml`: also shuffles the storybook epilogues.
- **Options Creator**: in the Launcher, open **Options Creator**, choose Chocobo Tales and export a YAML.
- **Template**: in the Launcher, click **Generate Template Options**. It writes `Chocobo Tales.yaml`, listing
  every option with its description, into the `Players/Templates` folder.

Then set `name:` to your slot name. Slot names must be unique within a multiworld; the presets use
`Player{number}`, which Archipelago turns into Player1, Player2, ...

What each option does is described in the [game page](https://github.com/Theo-Darvoux/ChocoboTalesAP/blob/main/chocobo_tales/docs/en_Chocobo%20Tales.md), and in the comments of the YAML files.

## Generating a game

Generation has to happen on a computer with the Chocobo Tales apworld installed, because archipelago.gg does not
know this game.

1. Collect every player's YAML files in the `Players` folder of your Archipelago install (and nothing else
   there except the `Templates` folder).
2. In the Launcher, click **Generate**. The result is a `.zip` in the `output` folder.
3. Inside the zip, every Chocobo Tales player has a `.apcts` patch file: send each player their own.

## Hosting the game

- **On archipelago.gg**: open [the upload page](https://archipelago.gg/uploads), upload the `.zip` and create a
  room. The website does not need the apworld to host a game that was generated elsewhere.
- **Locally**: in the Launcher, click **Host**, then pick the `.zip`. Other players need your address and port
  (38281 by default) to reach you.

## Configuring Archipelago for Chocobo Tales

You only need to do this once. You can edit `host.yaml` (in your Archipelago folder) directly, or just let
Archipelago ask you:

1. `chocobo_tales_options: rom_file`: the path to your Chocobo Tales ROM. If it isn't set, Archipelago asks for
   the ROM the first time you open a patch, then remembers it.
2. `bizhawkclient_options: emuhawk_path`: the path to `EmuHawk.exe` (Windows) or `EmuHawkMono.sh` (Linux). This
   is optional: with it, the client starts BizHawk with the game and the connector script for you.

## Playing

1. In the Launcher, click **Open Patch** and pick your `.apcts` file (or double-click the file). Archipelago
   builds the patched game next to it, a `.nds` file named after the patch, and opens the **BizHawk Client**.
2. If `emuhawk_path` is set, BizHawk starts with the game and the connector script. Otherwise:
   1. Open the patched `.nds` in BizHawk (**File > Open ROM**).
   2. Open **Tools > Lua Console**, then **Script > Open Script...**, and load
      `connector_bizhawk_generic.lua` from the `data/lua` folder of your Archipelago install.
3. In the BizHawk Client, type the server address (for example `archipelago.gg:38281`) at the top and click
   **Connect**. Your slot name is read from the ROM; enter the room password if there is one.
4. Start a **new game** in Chocobo Tales and play. Checks are sent as you complete them, and received items
   appear in your save directly (cards in the collection, chocobos, storybook modes).

The client says "Detected Chocobo Tales (...), Archipelago version" once BizHawk and the client are talking to
each other.

### Good to know

- Always play the patched `.nds`. The client refuses the vanilla ROM, because the vanilla game would hand out
  Archipelago's items by itself.
- Keep BizHawk at normal speed (**Config > Speed/Skip**). At boosted speeds BizHawk can stop running the connector
  script, and the client then loses its connection.
- BizHawk names the game's save after the ROM file, so every seed gets its own save. Keep the patched `.nds` and
  its save until the multiworld is over.
- Reward messages in the game name the item found there ("Item found: ..."), in every language. A message saying
  there is nothing to obtain means that check is turned off in your options.
- Every duel after the tutorial needs a 15-card deck. Keep `starting_cards` at 15 or more unless you want the
  first chapter to be a hunt for cards.

## Troubleshooting

- **"Chocobo Tales" isn't in the Launcher or the Options Creator**: the apworld isn't installed, or is installed
  twice. Look in `custom_worlds` (and `lib/worlds`) for old copies, keep a single `chocobo_tales.apworld`, then
  restart the Launcher.
- **The ROM is rejected when opening the patch**: only the European and USA ROMs with the MD5s above are
  supported. Check it isn't a trimmed, patched or Japanese dump.
- **The client doesn't see BizHawk**: make sure the connector Lua script is running in the Lua Console, and that
  only one BizHawk Client is open.
- **The client disconnects after a while**: set BizHawk back to 100% speed and reload the connector script.
- **Something else**: open an issue on the
  [GitHub repository](https://github.com/Theo-Darvoux/ChocoboTalesAP/issues) with your apworld version, your YAML
  and the client log (in Archipelago's `logs` folder).
