from typing import TYPE_CHECKING

from .runtime import get_context

if TYPE_CHECKING:
    from .item import ItemStack

class Player:
    pass

class TargetPlayer(Player):
    def __init__(self, uuid:str):
        self.uuid=uuid

    async def send_message(self, message:str|dict) -> bool:
        return (await get_context().client.command(
            "send_message",
            {
                "player_uuid": self.uuid,
                "message_type": "pure_text" if isinstance(message, str) else "text_component",
                "message_content": message
            }
        )).ok

    async def give_item(self, item_stack:ItemStack) -> None:
        await get_context().client.command(
            "give_item",
            {
                "player_uuid": self.uuid,
                **item_stack.raw()
            }
        )

    async def take_item(self, item_stack:ItemStack) -> bool:
        return (await get_context().client.command(
            "take_item",
            {
                "player_uuid": self.uuid,
                **item_stack.raw()
            }
        )).data["is_success"]

    async def set_custom_data(self, key:str, value:str|int|float) -> None:
        await get_context().client.command(
            "set_custom_data",
            {
                "target_type": "player",
                "target_uuid": self.uuid,
                "package_name": get_context().package_name,
                "data_key": key,
                "data_value": value
            }
        )