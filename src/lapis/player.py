from typing import TYPE_CHECKING

from .runtime import get_context
from .message import format_message

if TYPE_CHECKING:
    from .item import ItemStack

class Player:
    pass

class TargetPlayer(Player):
    def __init__(self, uuid:str):
        self.uuid=uuid

    async def send_message(self, message:str|dict) -> bool:
        """
        向玩家发送消息
        :param message: 消息类型，若为字符串则消息为纯文本，若为字典则消息为文本组件
        :return:
        """
        return (await get_context().client.command(
            "send_message",
            {
                "player_uuid": self.uuid,
                **format_message(message)
            }
        )).ok

    async def ask_input(self, prompt:str = None, timeout:float = -1) -> str:
        """
        请求玩家输入

        :param prompt: 提示消息，None表示无提示
        :param timeout: 时间限制，-1表示无时间限制，超时则抛出TimeoutError异常
        :return: 输入结果
        """
        result = await get_context().client.command(
            "ask_input",
            {
                "player_uuid": self.uuid,
                "prompt": prompt is not None,
                **(
                    format_message(prompt)
                    if prompt is not None
                    else {
                        "message_type": "",
                        "message_content": ""
                    }
                )
            }
        )

        if result.data["result_type"] == "timeout":
            raise TimeoutError("ask_input exceeded the timeout limit")

        return result.data["result_content"]

    async def give_item(self, item_stack:ItemStack) -> None:
        """
        给予玩家物品
        :param item_stack: 物品堆
        :return:
        """
        await get_context().client.command(
            "give_item",
            {
                "player_uuid": self.uuid,
                **item_stack.raw()
            }
        )

    async def take_item(self, item_stack:ItemStack) -> bool:
        """
        拿走玩家物品
        :param item_stack: 物品堆
        :return: 是否成功
        """
        return (await get_context().client.command(
            "take_item",
            {
                "player_uuid": self.uuid,
                **item_stack.raw()
            }
        )).data["is_success"]

    async def set_custom_data(self, key:str, value:str|int|float) -> None:
        """
        设置自定义数据
        :param key: 自定义数据键
        :param value: 自定义数据值
        :return:
        """
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

    async def money_query(self) -> float:
        """
        查询eco余额
        :return:
        """
        return (await get_context().client.command(
            "money_query",
            {
                "player_uuid": self.uuid,
            }
        )).data["balance"]

    async def money_give(self, amount:float) -> None:
        """
        给予eco
        :param amount: 金额
        :return:
        """
        await get_context().client.command(
            "money_give",
            {
                "player_uuid": self.uuid,
                "amount": amount
            }
        )

    async def money_set(self, amount:float) -> None:
        """
        设置eco
        :param amount: 金额
        :return:
        """
        await get_context().client.command(
            "money_set",
            {
                "player_uuid": self.uuid,
                "amount": amount
            }
        )

    async def money_take(self, amount:float, force:bool=False) -> None:
        """
        扣除eco
        :param amount: 金额
        :param force: 无视余额限制强制扣除
        :return: 是否扣款成功
        """
        return (await get_context().client.command(
            "money_take",
            {
                "player_uuid": self.uuid,
                "amount": amount,
                "force": force
            }
        )).data["is_success"]