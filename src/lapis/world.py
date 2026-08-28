from typing import Any

from .runtime import get_context
from .utils import Data

class World:
    name: str
    def __init__(self, name: str):
        self.name = name

    async def set_block(
            self,
            x:int, y:int, z:int,
            block_id: str,
            block_state :dict[str, Any] = None,
            nbt: dict[str, Any] | Data = None
    ) -> bool:
        """
        设置方块
        :param x: 坐标 x
        :param y: 坐标 y
        :param z: 坐标 z
        :param block_id: 方块 id
        :param block_state: 方块 BlockState
        :param nbt: 方块 nbt
        :return:
        """

        if block_state is None:
            block_state = {}

        if nbt is None:
            nbt = {}
        elif isinstance(nbt, Data):
            nbt = nbt.raw()

        return (await get_context().client.command(
            "set_block",
            {
                "block_id": block_id,
                "world": self.name,
                "pos": [x, y, z],
                "block_state": block_state,
                "nbt": nbt
            }
        )).ok

OVERWORLD = World("world")
THE_NETHER = World("world_the_nether")
THE_END = World("world_the_end")