from __future__ import annotations

from typing import Any

from .pos import Pos
from .utils import Data


class Block:
    """表示 Minecraft 中的一个方块。

    典型构造方式：通过 :func:`get_block` 从 Java 端拉取。
    """

    block_id: str
    block_state: Data
    pos: BlockPos
    nbt: Data

    def __init__(
        self,
        block_id: str,
        pos: BlockPos,
        block_state: Any = None,
        nbt: Any = None,
    ) -> None:
        if block_state is None:
            block_state = {}
        if nbt is None:
            nbt = Data({})

        self.block_id = block_id
        self.pos = pos
        # 兼容 Data 或 dict
        self.block_state = (
            block_state if isinstance(block_state, Data) else Data(block_state)
        )
        self.nbt = nbt if isinstance(nbt, Data) else Data(nbt)

    # --------------------------------------------------------
    # Custom KV data (PDC) — block target (Tile Entity only)
    # --------------------------------------------------------

    async def set_custom_data(
        self,
        key: str,
        value: str | int | float | bool | list | dict,
    ) -> None:
        """在 Java 端为当前 package 在该方块（Tile Entity）上存储 KV 自定义数据。

        仅对支持 PersistentDataContainer 的 Tile Entity 方块有效（箱子、命令方块、
        告示牌等）；普通方块调用会在 Java 端返回错误。

        :param key: 数据键名。
        :param value: 数据值。
        """
        from .runtime import get_context

        await get_context().client.command(
            "set_custom_data",
            {
                "target_type": "block",
                # Java 端 block 分支不读取 target_uuid，传空串占位
                "target_uuid": "",
                "package_name": get_context().package_name,
                "data_key": key,
                "data_value": value,
                "world": self.pos.world,
                "pos": [int(self.pos.x), int(self.pos.y), int(self.pos.z)],
            },
        )

    async def remove_custom_data(self, key: str) -> None:
        """删除之前通过 :meth:`set_custom_data` 在方块上存储的 KV 数据。

        :param key: 数据键名。
        """
        from .runtime import get_context

        await get_context().client.command(
            "remove_custom_data",
            {
                "target_type": "block",
                "target_uuid": "",
                "package_name": get_context().package_name,
                "data_key": key,
                "world": self.pos.world,
                "pos": [int(self.pos.x), int(self.pos.y), int(self.pos.z)],
            },
        )


class BlockPos(Pos):
    x: int
    y: int
    z: int

    def __init__(self, world: str, x: int, y: int, z: int) -> None:
        super().__init__(world, x, y, z)

    def raw(self) -> dict[str, Any]:
        return {
            "world": self.world,
            "pos": [int(self.x), int(self.y), int(self.z)],
        }

    def __repr__(self) -> str:
        return f"BlockPos({self.world}: {self.x}, {self.y}, {self.z})"


def create_block(
    block_id: str = "minecraft:air",
    world: str = "world",
    pos_raw: list[int] | None = None,
    block_state: dict[str, Any] | None = None,
    nbt_raw: dict[str, Any] | None = None,
) -> Block:
    """从原始数据构造 :class:`Block`。

    :param block_id: 方块 ID，例如 ``minecraft:stone``。
    :param world: 世界名称。
    :param pos_raw: ``[x, y, z]`` 坐标数组。
    :param block_state: BlockState 字典。
    :param nbt_raw: 方块 NBT 字典。
    """
    if pos_raw is None:
        pos_raw = [0, 0, 0]
    if block_state is None:
        block_state = {}
    if nbt_raw is None:
        nbt_raw = {}

    return Block(
        block_id,
        BlockPos(world, *pos_raw),
        Data(block_state),
        Data(nbt_raw),
    )


# ============================================================
# Module-level Block Commands
# ============================================================

async def set_block(
    world: str,
    x: int,
    y: int,
    z: int,
    block_id: str,
    block_state: dict[str, Any] | None = None,
    nbt: dict[str, Any] | None = None,
) -> bool:
    """设置指定位置的方块。

    :param world: 世界名称。
    :param x: X 坐标。
    :param y: Y 坐标。
    :param z: Z 坐标。
    :param block_id: 方块 ID，如 ``minecraft:stone``。
    :param block_state: BlockState 属性字典，如 ``{"facing": "north"}``。
    :param nbt: 方块实体 NBT 数据（仅 Tile Entity 方块可用）；每个键会被按当前
                package 的命名空间写入 PDC。
    :return: Java 端是否成功处理。
    """
    from .runtime import get_context

    data: dict[str, Any] = {
        "block_id": block_id,
        "pos": {
            "x": int(x),
            "y": int(y),
            "z": int(z),
        },
    }
    if world is not None:
        data["world"] = world
    if block_state is not None and len(block_state) > 0:
        data["block_state"] = block_state
    if nbt is not None and len(nbt) > 0:
        data["nbt"] = nbt

    return (await get_context().client.command("set_block", data)).ok


async def get_block(
    world: str,
    x: int,
    y: int,
    z: int,
) -> Block:
    """获取指定位置的方块信息。

    :param world: 世界名称。
    :param x: X 坐标。
    :param y: Y 坐标。
    :param z: Z 坐标。
    :return: :class:`Block` 对象，包含 id、pos、state、nbt。
    """
    from .runtime import get_context

    data: dict[str, Any] = {
        "pos": {
            "x": int(x),
            "y": int(y),
            "z": int(z),
        },
    }
    if world is not None:
        data["world"] = world

    resp = await get_context().client.command("get_block", data)
    block_raw = resp.data.get("block")
    pos = block_raw.get("pos", {"x": x, "y": y, "z": z})
    return create_block(
        block_id=block_raw.get("id", "minecraft:air"),
        world=block_raw.get("world", world),
        pos_raw=[pos.get("x", x), pos.get("y", y), pos.get("z", z)],
        block_state=block_raw.get("state", {}),
        nbt_raw=block_raw.get("nbt", {}),
    )
