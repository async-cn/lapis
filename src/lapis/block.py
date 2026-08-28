from typing import TYPE_CHECKING, Any

from .pos import Pos
from .runtime import get_context
from .world import WORLDS
from .nbt import NBT

if TYPE_CHECKING:
    from typing import Any

class Block:
    block_id: str
    block_state: dict[str, Any]
    pos: BlockPos
    nbt: NBT

    def __init__(
            self,
            block_id: str,
            pos: BlockPos,
            block_state: dict[str, Any] = None,
            nbt: NBT = None
    ) -> None:

        if block_state is None:
            block_state = {}
        if nbt is None:
            nbt = NBT()

        self.block_id = block_id
        self.pos = pos
        self.block_state = block_state
        self.nbt = nbt


class BlockPos(Pos):
    x: int
    y: int
    z: int
    def __init__(self, world:str, x:int, y:int, z:int):
        super().__init__(world, x, y, z)

    def raw(self) -> dict[str, Any]:
        return {
            "world": self.world,
            "pos": [int(self.x), int(self.y), int(self.z)]
        }

    def __repr__(self) -> str:
        return f"BlockPos({self.world}: {self.x}, {self.y}, {self.z})"


def create_blockpos(dimension:str, x:int, y:int, z:int) -> BlockPos:
    return BlockPos(
        getattr(WORLDS, dimension),
        x,
        y,
        z,
    )

def create_block(
    block_id: str = "minecraft:air",
    world: str = "world",
    pos_raw: list[int] = None,
    block_state: dict[str, Any] = None,
    nbt_raw: dict[str, Any] = None
) -> Block:
    """
    创建方块
    :param block_id: 方块ID
    :param world: 世界名
    :param pos_raw: 方块坐标，用数组[x, y, z]表示
    :param block_state: 方块状态
    :param nbt_raw: 方块NBT
    :return: Block对象
    """
    if pos_raw is None: pos_raw = [0, 0, 0]
    if block_state is None: block_state = {}
    if nbt_raw is None: nbt_raw = {}

    return Block(
        block_id,
        BlockPos(world, *pos_raw),
        block_state,
        NBT(**nbt_raw)
    )