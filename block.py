from typing import TYPE_CHECKING

from .runtime import get_context

if TYPE_CHECKING:
    from typing import Any
    from .pos import BlockPos
    from .nbt import NBT

class Block:
    block_id: str
    pos: BlockPos
    block_state: dict[str, Any]
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

async def set_block(block: Block) -> bool:
    return (await get_context().client.command(
        "set_block",
        {
            "block_id": block.block_id,
            "pos": block.pos.raw(),
            "block_state": block.block_state,
            "nbt": block.nbt.raw()
        }
    )).ok