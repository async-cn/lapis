from __future__ import annotations

from typing import Any, TYPE_CHECKING
from uuid import UUID

from .pos import Pos
from .utils import Data

if TYPE_CHECKING:
    pass


class EntityPos(Pos):
    def __repr__(self) -> str:
        return f"EntityPos({self.world}: {self.x}, {self.y}, {self.z})"


class Entity:
    """表示 Minecraft 中的一个实体（玩家、怪物、掉落物、车辆等）。

    典型构造方式：通过 :func:`get_entity` 从 Java 端拉取。
    """

    uuid: str
    type: str
    name: str
    custom_name: str | None
    world: str
    x: float
    y: float
    z: float
    health: float | None
    max_health: float | None
    nbt: Data

    def __init__(
        self,
        uuid: str,
        type: str,
        name: str,
        world: str,
        x: float,
        y: float,
        z: float,
        custom_name: str | None = None,
        health: float | None = None,
        max_health: float | None = None,
        nbt: dict[str, Any] | Data | None = None,
    ) -> None:
        self.uuid = uuid
        self.type = type
        self.name = name
        self.custom_name = custom_name
        self.world = world
        self.x = x
        self.y = y
        self.z = z
        self.health = health
        self.max_health = max_health
        if nbt is None:
            nbt = {}
        self.nbt = nbt if isinstance(nbt, Data) else Data(nbt)

    # --------------------------------------------------------
    # Position
    # --------------------------------------------------------

    @property
    def pos(self) -> EntityPos:
        """返回当前实体的 :class:`EntityPos` 位置对象。"""
        return EntityPos(self.world, self.x, self.y, self.z)

    # --------------------------------------------------------
    # Custom KV data (PDC) — entity target
    # --------------------------------------------------------

    async def set_custom_data(
        self,
        key: str,
        value: str | int | float | bool | list | dict,
    ) -> None:
        """在 Java 端为当前 package 在该实体上存储 KV 自定义数据（PDC）。

        :param key: 数据键名。
        :param value: 数据值。
        """
        from .runtime import get_context

        await get_context().client.command(
            "set_custom_data",
            {
                "target_type": "entity",
                "target_uuid": self.uuid,
                "package_name": get_context().package_name,
                "data_key": key,
                "data_value": value,
            },
        )

    async def remove_custom_data(self, key: str) -> None:
        """删除之前通过 :meth:`set_custom_data` 存储的 KV 数据。

        :param key: 数据键名。
        """
        from .runtime import get_context

        await get_context().client.command(
            "remove_custom_data",
            {
                "target_type": "entity",
                "target_uuid": self.uuid,
                "package_name": get_context().package_name,
                "data_key": key,
            },
        )

    def __repr__(self) -> str:
        return (
            f"Entity(type={self.type!r}, uuid={self.uuid!r}, "
            f"name={self.name!r}, pos=({self.x}, {self.y}, {self.z}))"
        )


# ============================================================
# Factory / Module-level API
# ============================================================

def create_entity(raw: dict[str, Any]) -> Entity:
    """从 Java 端 ``get_entity`` 返回的原始字典构造 :class:`Entity`。

    :param raw: Java 端 ``get_entity`` 返回的 entity 子字典。
    """
    nbt_full = raw.get("_full", raw)
    return Entity(
        uuid=raw.get("uuid", ""),
        type=raw.get("type", ""),
        name=raw.get("name", ""),
        custom_name=raw.get("custom_name"),
        world=raw.get("world", ""),
        x=float(raw.get("x", 0)),
        y=float(raw.get("y", 0)),
        z=float(raw.get("z", 0)),
        health=raw.get("health"),
        max_health=raw.get("max_health"),
        nbt=nbt_full,
    )


async def get_entity(entity_uuid: str | UUID) -> Entity:
    """根据 UUID 从 Java 端获取实体信息。

    :param entity_uuid: 实体 UUID 字符串或 :class:`uuid.UUID`。
    :return: 填充完成的 :class:`Entity` 对象。
    :raises LapisCommandError: 实体不存在或命令出错时抛出。
    """
    from .runtime import get_context

    resp = await get_context().client.command(
        "get_entity",
        {
            "uuid": str(entity_uuid),
        },
    )
    return create_entity(resp.data.get("entity"))
