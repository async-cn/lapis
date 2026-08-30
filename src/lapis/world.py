from __future__ import annotations

from typing import Any

from .config import Config
from .runtime import get_context
from .utils import Data
from .block import Block, create_block

class World:
    """表示 Minecraft 中的一个世界/维度。"""

    name: str

    def __init__(self, name: str) -> None:
        self.name = name

    async def get_block(self, x: int, y: int, z: int) -> Block:
        """
        获取指定位置的方块
        :param x: 坐标 X
        :param y: 坐标 Y
        :param z: 坐标 Z
        :return: 指定位置的方块，Block对象
        """
        result = await get_context().client.command(
            "get_block",
            {
                "world": self.name,
                "pos": [x, y, z],
            },
        )
        return create_block(
            block_id=result.data.get("block_id"),
            world=self.name,
            pos_raw=[x, y, z],
            block_state=result.data.get("block.state"),
            nbt_raw=result.data.get("block.nbt"),
        )

    async def set_block(
        self,
        x: int,
        y: int,
        z: int,
        block_id: str,
        block_state: dict[str, Any] | None = None,
        nbt: dict[str, Any] | Data | None = None,
    ) -> bool:
        """在 ``(x, y, z)`` 位置设置方块。

        :param x: X 坐标
        :param y: Y 坐标
        :param z: Z 坐标
        :param block_id: 方块 ID，如 ``minecraft:stone``
        :param block_state: BlockState 字典
        :param nbt: 方块 NBT 字典或 :class:`Data` 包装
        :return: Java 端是否成功处理
        """

        if block_state is None:
            block_state = {}

        if nbt is None:
            nbt_dict: dict[str, Any] = {}
        elif isinstance(nbt, Data):
            nbt_dict = nbt.raw()
        else:
            nbt_dict = nbt

        return (await get_context().client.command(
            "set_block",
            {
                "block_id": block_id,
                "world": self.name,
                "pos": [x, y, z],
                "block_state": block_state,
                "nbt": nbt_dict,
            },
        )).ok


# ------------------------------------------------------------
# 基于 Config.DIMENSIONS 的维度单例（延迟加载）
# ------------------------------------------------------------
#
# 与原来不同，这里不在模块导入时立即构造 World 实例，
# 而是通过模块级 __getattr__ 在首次访问时从当前进程内生效的
# Config.DIMENSIONS 读取，允许用户在 lapis.init() 之前
# 修改 Config.DIMENSIONS 后得到对应的 World 对象。
#
# 同时提供 get_world() 作为显式工厂函数（推荐在新代码中使用）。


def get_world(name: str) -> World:
    """根据维度代号获取对应的 :class:`World` 实例。

    ``name`` 首先尝试在 :data:`Config.DIMENSIONS` 中查找代号（如
    ``"overworld"``），命中后使用其真实目录名；否则将 ``name`` 直接作为
    世界目录名（便于用户引用自定义世界）。
    """
    dimensions = Config.DIMENSIONS
    if name in dimensions:
        return World(dimensions[name])
    return World(name)


def __getattr__(name: str) -> World:
    """惰性导出维度常量：``OVERWORLD`` / ``THE_NETHER`` / ``THE_END``。

    均通过 :func:`get_world` 基于当前 :data:`Config.DIMENSIONS` 构造。
    """
    aliases = {
        "OVERWORLD": "overworld",
        "THE_NETHER": "the_nether",
        "THE_END": "the_end",
    }
    if name in aliases:
        return get_world(aliases[name])
    raise AttributeError(f"module 'lapis.world' has no attribute {name!r}")
