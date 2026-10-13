"""
Where the vanilla game hands out a reward, and which Archipelago location stands in its place. No Archipelago
imports: the ROM patch uses this as well as the world.
"""
from .data import FIELD_CARD_GRANTS, STORYBOOK_REWARD_RECORDS

MEDAL_FLAG_BASE = 0x9F8  # + 3 * (microgame - 1) + 1 Silver / 2 Gold


def storybook_location_id(book: int, goal_index: int) -> int:
    return 1000 + book * 10 + goal_index


def microgame_location_id(game: int, medal: str) -> int:
    return 2000 + game * 10 + (0 if medal == "Silver" else 1)


def field_card_location_id(card: int) -> int:
    return 4000 + card


def rescue_location_id(friend_id: int) -> int:
    return 5000 + friend_id


def card_gift_location_id(card: int) -> int:
    return 6000 + card


def medal_of_flag(flag: int) -> tuple[int, str]:
    """(microgame, "Silver" / "Gold") of a medal flag."""
    game, kind = divmod(flag - MEDAL_FLAG_BASE, 3)
    if kind == 0:
        raise ValueError(f"{flag:#x} is a first-play flag, not a medal")
    return game + 1, "Silver" if kind == 1 else "Gold"


def is_field_pickup(script: str) -> bool:
    return script.endswith("/cardget.act")


# Card gifts: cards field scripts give for something other than a field pickup or a microgame medal (NPCs, chests,
# beaten duelists). card -> (flag the script sets with the card, scripts giving it, flags in the gift's condition)
CARD_GIFTS: dict[int, tuple[int, tuple[str, ...], tuple[int, ...]]] = {}
for _script, _, _card, _event, _medal, _guard in FIELD_CARD_GRANTS:
    if not _medal and not is_field_pickup(_script):
        _event_flag, _scripts, _ = CARD_GIFTS.get(_card, (_event, (), ()))
        assert _event_flag == _event, _card
        CARD_GIFTS[_card] = (_event, (*_scripts, _script), _guard)


def field_grant_location(script: str, card: int, medal_flag: int) -> int:
    """The location announced by a field script's card message."""
    if medal_flag:
        return microgame_location_id(*medal_of_flag(medal_flag))
    if is_field_pickup(script):
        return field_card_location_id(card)
    return card_gift_location_id(card)


def goal_locations(book: int, goal_index: int) -> list[int]:
    """The locations completing a storybook goal checks: the goal itself, then its chocobo rescue if it has one."""
    rescues = [rescue_location_id(value) for kind, value in STORYBOOK_REWARD_RECORDS[book - 1][goal_index]
               if kind == "chocobo"]
    return [storybook_location_id(book, goal_index), *rescues]
