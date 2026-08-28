from typing import Any

from . import nbt, block
from .runtime import get_context
from .config import Config
from .utils import Data

class WORLDS:
    overworld: str
    the_nether: str
    the_end: str

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

for dimension, world_name in Config.DIMENSIONS.items():
    setattr(WORLDS, dimension, world_name)