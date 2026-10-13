# Changelog

Each release's section is used as its GitHub release notes. Versions follow `world_version` in
`chocobo_tales/archipelago.json`.

## 0.4.0

- USA ROM (`AEHE`) support. The same `.apcts` patch works on either release; the USA game's messages are in
  English.
- Card gifts are now expected from the chapter their giver appears in, with the rescued chocobos and storybook
  epilogues they need, instead of after the ending. Only Karma+ (Bebuzzu rematches) and its duel wins stay after
  the ending.
- Story order fixed: storybooks 3, 7, 8, 10, 12 and 13 open a chapter earlier, 14 and 16 in chapter 5. Each
  chapter's Bebuzzu duel now needs the epilogue whose field change starts it, and the epilogues the story uses
  are progression when shuffled.
- Microgame access read from the game's scripts: Sweenie's and Wakaba's games only after the ending, the
  Goblin's needs Moggy, and several need Belle, Indy or Jarro on the field.
- Storybook Goals Required defaults to 90 (Compact preset: 26), so the goal still needs chapter 5.

## 0.3.0

First public release. Europe ROM (`AEHP`) only, Archipelago 0.6.7 or newer.

- Checks: storybook goals (first 2–7 per book), microgame Silver / Gold medals, field cards, chocobo rescues,
  story chapters, optional boss duel wins and card gifts.
- Items: the 127 cards (or 26 monster Card Packs), the 15 rescued chocobos, storybook battle / trial modes,
  optional shuffled epilogues.
- Goals: Story Complete, Chocobo Rescue, Card Collection, Storybook Goals (75 by default), Gold Medals (19 by
  default). The last two defaults need chapter 5.
- The patched game names the Archipelago item in every reward message, in all five languages, and shows an
  Archipelago card on storybook result screens.
- Universal Tracker support without a YAML.
- Three YAML presets: full, Compact and Epilogues.
- Setup guides in English and French.

Known limitations: microgame chapter timing and card gift availability are conservative estimates (card gifts are
expected after the ending); some reward displays have not been seen in game yet. See `NOTES.md`.
