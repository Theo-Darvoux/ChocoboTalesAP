# Changelog

Each release's section is used as its GitHub release notes. Versions follow `world_version` in
`chocobo_tales/archipelago.json`.

## 0.3.0

First public release. Europe ROM (`AEHP`) only, Archipelago 0.6.7 or newer.

- Checks: storybook goals (first 2–7 per book), microgame Silver / Gold medals, field cards, chocobo rescues,
  story chapters, optional boss duel wins and card gifts.
- Items: the 127 cards (or 26 monster Card Packs), the 15 rescued chocobos, storybook battle / trial modes,
  optional shuffled epilogues.
- Goals: Story Complete, Chocobo Rescue, Card Collection, Storybook Goals, Gold Medals.
- The patched game names the Archipelago item in every reward message, in all five languages, and shows an
  Archipelago card on storybook result screens.
- Universal Tracker support without a YAML.
- Three YAML presets: full, Compact and Epilogues.
- Setup guides in English and French.

Known limitations: microgame chapter timing and card gift availability are conservative estimates (card gifts are
expected after the ending); some reward displays have not been seen in game yet. See `NOTES.md`.
