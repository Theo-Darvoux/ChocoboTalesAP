# Chocobo Tales

## What does randomization do to this game?

The rewards for storybook goals and microgame medals are shuffled into the multiworld, along with the battle
and trial modes of each storybook minigame. The patched game no longer gives you cards, rescued chocobos or
most mode unlocks by itself. Those come from Archipelago items, which can be in your world or in other
players' worlds. The first Adamantoise storybook still unlocks its battle levels normally so the story can proceed.

## What is the goal?

Depending on your options:

- **Story Complete** (default): beat the story. The ending plays after the last Bebuzzu duel.
- **Chocobo Rescue**: receive enough rescued chocobos.
- **Card Collection**: receive enough cards.
- **Storybook Goals**: complete the chosen number of enabled storybook goals.
- **Gold Medals**: win the chosen number of Gold microgame medals.

## Which locations are checks?

- **Storybooks (32–112):** each of the 16 storybook minigames has 7 goals. You can select the first 2–7
  goals per book; the older exclusion option caps the selection at 4.
- **Microgames (46, or 23):** each of the 23 field microgames has Silver and Gold targets. You can use
  both medals or only one tier as checks.
- **Field Cards (9, optional):** find the cards lying in the field. Each pickup is a check even if you already
  received that card as an Archipelago item. Set `field_card_checks: false` to remove these checks.
- **Chocobo Rescues (15, optional):** complete the storybook goal that rescues each chocobo. Each rescue is a check
  even if its storybook goal is not selected as a separate check, or you already received that chocobo as an item.
  Set `chocobo_rescue_checks: false` to remove these checks.
- **Story (5):** completing chapters 1 to 5. Each chapter ends with a boss Pop-up Duel against Bebuzzu.
- **Boss Pop-up Duel Wins (8, optional):** winning each boss duel. The older YAML key is
  `duel_s_rank_checks`; the game's S result script means success, not a separate rank.
- **Card Gifts (27, optional):** the cards characters hand you outside storybooks and microgames: the six
  Carbuncles, Peachie, Becky, Grinn, Bruce and others, the four Typhon chests, the beaten Pop-up duelists, and the
  rewards for beating all four Pop-up Duel bosses and all four Bebuzzu duels. Logic only expects them after the
  ending (they are unavailable during the last chapter, and when each opens up hasn't been checked yet), plus
  the rescued chocobo when one gives the card. Set `card_gift_checks: false` to remove these checks.

## What do I see when I complete a check?

The game names the Archipelago item instead of the vanilla reward, in every language. Field messages read
"Item found:" followed by the item's name (the player it belongs to isn't shown). A storybook result screen shows
an Archipelago card, built from your ROM when patching, for each check the goal completes, with the item's name, and
the storybook goal list shows the items too. Rewards the patched game still gives, such as book 1's battle levels or
unshuffled epilogues, keep their vanilla texts. A reward whose check isn't enabled in your options says there is
nothing to obtain, since the game no longer gives it.

## Which items are in the pool?

- All 127 Pop-up Duel cards, individually or bundled by monster into 26 **Card Packs**. **Starting Cards**
  gives you at least that many cards at the start; packs round up to whole packs.
- The 15 chocobos rescued through storybook goals. Four microgames (Silly Scribbles, Tome Raider, Rodeo
  Roundup, Up, Up, and A-Kweh!) are run by rescued chocobos. **Starting Chocobos** gives you some immediately.
- 15 **Storybook Modes** items, each unlocking a book's battle and trial modes. Storybook 1's modes unlock
  through normal play, since the story needs its first duel. **Open Storybook Modes**
  gives you all 15 at the start.
- Optional: 48 **Storybook Epilogues**, three per book. Their vanilla grants are blocked when shuffled.
- Gysahl Greens, a filler item that does nothing.

## How does logic work?

Storybooks and microgames open as the story goes on, chapter by chapter. Duels after the tutorial need 15
owned cards for a deck. Logic expects **Cards Per Chapter** more cards for each later chapter. Crazy Credits
only opens after the ending. Microgame chapter timing remains a conservative estimate, and some field
obstacles have not been checked in live play; this build is experimental until that access model is verified.
See [NOTES.md](https://github.com/Theo-Darvoux/ChocoboTalesAP/blob/main/NOTES.md) for the current evidence.

If a reduced check pool cannot hold every item, generation explains which options to change; it does not
raise Starting Cards silently. The Storybook Goals target must not exceed the enabled goal count. The
included Compact and Epilogues YAML presets pair item bundles with suitable check counts.

## Supported versions

Europe (`AEHP`) and USA (`AEHE`). Japan isn't supported.
