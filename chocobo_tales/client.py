import logging
import struct
from typing import TYPE_CHECKING

from NetUtils import ClientStatus
import worlds._bizhawk as bizhawk
from worlds._bizhawk.client import BizHawkClient

from . import flags, ram
from .items import CARD_ITEMS, CARD_PACK_NUMBERS, CHOCOBO_ITEMS, GAME_NAME
from .locations import STORYBOOK_LOCATION_IDS, STORYBOOK_LOCATIONS

if TYPE_CHECKING:
    from worlds._bizhawk.context import BizHawkClientContext

logger = logging.getLogger("Client")

CARD_IDS = frozenset(CARD_ITEMS.values())
CHOCOBO_IDS = frozenset(CHOCOBO_ITEMS.values())
GOAL_STORY_COMPLETE, GOAL_CHOCOBO_RESCUE, GOAL_CARD_COLLECTION, GOAL_STORYBOOK_GOALS, GOAL_GOLD_MEDALS = range(5)


class ChocoboTalesClient(BizHawkClient):
    game = GAME_NAME
    system = "NDS"
    patch_suffix = ".apcts"

    def __init__(self) -> None:
        super().__init__()
        self.warned_unpatched = False
        self.save_pointer = ram.SAVE_POINTERS[b"AEHP"]

    async def validate_rom(self, ctx: "BizHawkClientContext") -> bool:
        try:
            header, ap_data = await bizhawk.read(ctx.bizhawk_ctx, [
                (ram.CART_HEADER, 0x10, ram.MAIN_RAM),
                (ram.AP_DATA_OFFSET, len(ram.AP_MAGIC), ram.ROM),
            ])
        except bizhawk.RequestFailedError:
            return False
        if header[:12] != ram.GAME_TITLE or header[12:16] not in ram.SUPPORTED_GAME_CODES:
            return False
        if ap_data != ram.AP_MAGIC:
            if not self.warned_unpatched:
                logger.error("This is the vanilla Chocobo Tales ROM. Open your .apcts patch file to get the "
                             "Archipelago version of the game.")
                self.warned_unpatched = True
            return False

        self.save_pointer = ram.SAVE_POINTERS[header[12:16]]
        ctx.game = self.game
        # Items found in this world are given by the client too, so every item comes from the server
        ctx.items_handling = 0b111
        ctx.want_slot_data = True
        ctx.watcher_timeout = 0.5
        logger.info(f"Detected Chocobo Tales ({ram.SUPPORTED_GAME_CODES[header[12:16]]}), Archipelago version")
        return True

    async def set_auth(self, ctx: "BizHawkClientContext") -> None:
        name = (await bizhawk.read(ctx.bizhawk_ctx, [(ram.SLOT_NAME_OFFSET, ram.SLOT_NAME_SIZE, ram.ROM)]))[0]
        ctx.auth = name.split(b"\0", 1)[0].decode("utf-8")

    async def game_watcher(self, ctx: "BizHawkClientContext") -> None:
        if ctx.server is None or ctx.server.socket.closed or ctx.slot_data is None:
            return
        try:
            pointer_bytes = (await bizhawk.read(ctx.bizhawk_ctx, [(self.save_pointer, 4, ram.MAIN_RAM)]))[0]
            pointer = struct.unpack("<I", pointer_bytes)[0]
            if not ram.MAIN_RAM_BASE <= pointer < ram.MAIN_RAM_BASE + ram.MAIN_RAM_SIZE - ram.FLAG_BANK_SIZE:
                return  # No save data set up yet (boot / title screen)
            bank = pointer - ram.MAIN_RAM_BASE + ram.FLAG_BANK_OFFSET
            pointer_guard = (self.save_pointer, pointer_bytes, ram.MAIN_RAM)

            result = await bizhawk.guarded_read(ctx.bizhawk_ctx, [(bank, ram.FLAG_BANK_SIZE, ram.MAIN_RAM)],
                                                [pointer_guard])
            if result is None:
                return
            flag_bank = result[0]
            await self.check_locations(ctx, flag_bank)
            await self.check_goal(ctx, flag_bank)
            await self.give_items(ctx, bank, flag_bank, pointer_guard)
        except bizhawk.RequestFailedError:
            pass  # The connector didn't respond; the main loop will reconnect

    @staticmethod
    def flag_set(flag_bank: bytes, flag: int) -> bool:
        offset, mask = flags.flag_position(flag)
        return bool(flag_bank[offset] & mask)

    async def check_goal(self, ctx: "BizHawkClientContext", flag_bank: bytes) -> None:
        if ctx.finished_game:
            return
        goal = ctx.slot_data["goal"]
        received = [item.item for item in ctx.items_received]
        if goal == GOAL_CARD_COLLECTION:
            cards = set(CARD_IDS.intersection(received))
            for item_id in received:
                cards.update(CARD_PACK_NUMBERS.get(item_id, ()))
            done = len(cards) >= ctx.slot_data["cards_required"]
        elif goal == GOAL_CHOCOBO_RESCUE:
            done = len(CHOCOBO_IDS.intersection(received)) >= ctx.slot_data["chocobos_required"]
        elif goal == GOAL_STORYBOOK_GOALS:
            enabled = ctx.server_locations
            done = sum(self.flag_set(flag_bank, ram.LOCATION_FLAGS[STORYBOOK_LOCATION_IDS[name]])
                       for name in STORYBOOK_LOCATIONS if STORYBOOK_LOCATION_IDS[name] in enabled) >= ctx.slot_data["storybook_goals_required"]
        elif goal == GOAL_GOLD_MEDALS:
            done = sum(self.flag_set(flag_bank, flags.microgame_flag(game, "Gold")) for game in range(1, 24)) >= ctx.slot_data["gold_medals_required"]
        else:
            done = self.flag_set(flag_bank, flags.STORY_COMPLETE_FLAG)
        if done:
            await ctx.send_msgs([{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}])
            ctx.finished_game = True

    async def check_locations(self, ctx: "BizHawkClientContext", flag_bank: bytes) -> None:
        done = {location for location, flag in ram.LOCATION_FLAGS.items() if self.flag_set(flag_bank, flag)}
        new = (done & ctx.server_locations) - ctx.checked_locations
        if new:
            await ctx.send_msgs([{"cmd": "LocationChecks", "locations": sorted(new)}])

    async def give_items(self, ctx: "BizHawkClientContext", bank: int, flag_bank: bytes,
                         pointer_guard: tuple[int, bytes, str]) -> None:
        """Set received items and restore book 1's vanilla mode rewards from completed goals."""
        updated = bytearray(flag_bank)
        for item in {item.item for item in ctx.items_received}:
            for flag in ram.ITEM_FLAGS.get(item, ()):
                offset, mask = flags.flag_position(flag)
                updated[offset] |= mask
        for mode_flag, goal_flag in ram.STORYBOOK_01_VANILLA_MODE_UNLOCKS.items():
            if self.flag_set(flag_bank, goal_flag):
                offset, mask = flags.flag_position(mode_flag)
                updated[offset] |= mask
        changed = [offset for offset in range(len(flag_bank)) if updated[offset] != flag_bank[offset]]
        if not changed:
            return
        await bizhawk.guarded_write(
            ctx.bizhawk_ctx,
            [(bank + offset, [updated[offset]], ram.MAIN_RAM) for offset in changed],
            # Only write if the save struct hasn't moved and the bytes haven't changed since they were read
            [pointer_guard, *((bank + offset, bytes([flag_bank[offset]]), ram.MAIN_RAM) for offset in changed)],
        )
