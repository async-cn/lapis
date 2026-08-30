"""顶层、跨对象、纯功能性的命令 API。

领域对象专属的 OOP 风格方法请直接使用：
* :class:`lapis.player.Player` — send_message / ask_input / give_item /
  take_item / money_* / show_title / actionbar_* / play_sound* / 自定义数据
* :class:`lapis.block.Block` — 方块级 set_custom_data
* :class:`lapis.entity.Entity` — 实体级 set_custom_data

本模块仅保留：
1. 通用 execute_command。
2. 不依赖领域对象上下文的纯便捷函数（以 UUID 作为参数）。
3. 多目标通用型 PDC API（set_custom_data / remove_custom_data 可指定三种 target_type）。
4. 从对应模块 re-export 进来的模块级 API，保证 :mod:`lapis.commands` 作为单一入口。
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from .runtime import get_context
from .message import format_message, format_title_component


# ============================================================
# 1. Command Execution
# ============================================================

async def execute_command(minecraft_command: str) -> str:
    """执行原版 Minecraft 指令（以控制台身份）。

    :param minecraft_command: 原版指令字符串，不含开头斜杠。
    :return: 命令执行产生的文本输出。
    """
    return (await get_context().client.command(
        "execute_command",
        {"command": minecraft_command},
    )).data.get("result")


# ============================================================
# 2. Messaging / UI  (top-level, by UUID)
# ============================================================

async def send_message(
    player_uuid: str | UUID,
    message: str | dict[str, Any],
) -> bool:
    """向指定玩家发送聊天栏消息。

    :param player_uuid: 目标玩家 UUID。
    :param message: 纯文本字符串或 Minecraft 文本组件 dict。
    :return: Java 端是否成功处理。
    """
    return (await get_context().client.command(
        "send_message",
        {
            "player_uuid": str(player_uuid),
            **format_message(message),
        },
    )).ok


async def show_title(
    player_uuid: str | UUID,
    title: str | dict[str, Any],
    subtitle: str | dict[str, Any] | None = None,
    fade_in: int = 10,
    stay: int = 70,
    fade_out: int = 20,
) -> bool:
    """向玩家显示标题。

    :param player_uuid: 目标玩家 UUID。
    :param title: 主标题纯文本或文本组件 dict。
    :param subtitle: 副标题，``None`` 表示不显示。
    :param fade_in: 淡入 tick 数（默认 10）。
    :param stay: 停留 tick 数（默认 70）。
    :param fade_out: 淡出 tick 数（默认 20）。
    :return: Java 端是否成功处理。
    """
    title_type, title_content = format_title_component(title)
    data: dict[str, Any] = {
        "player_uuid": str(player_uuid),
        "title_type": title_type,
        "title": title_content,
        "fade_in": int(fade_in),
        "stay": int(stay),
        "fade_out": int(fade_out),
    }
    if subtitle is not None:
        subtitle_type, subtitle_content = format_title_component(subtitle)
        data["subtitle_type"] = subtitle_type
        data["subtitle"] = subtitle_content
    return (await get_context().client.command("show_title", data)).ok


async def actionbar_set(
    player_uuid: str | UUID,
    message: str | dict[str, Any],
) -> bool:
    """设置玩家 ActionBar（快捷栏上方）消息。

    :param player_uuid: 目标玩家 UUID。
    :param message: 纯文本或文本组件。
    :return: Java 端是否成功处理。
    """
    return (await get_context().client.command(
        "actionbar_set",
        {
            "player_uuid": str(player_uuid),
            **format_message(message),
        },
    )).ok


async def actionbar_clear(player_uuid: str | UUID) -> bool:
    """清除玩家 ActionBar 消息。

    :param player_uuid: 目标玩家 UUID。
    :return: Java 端是否成功处理。
    """
    return (await get_context().client.command(
        "actionbar_clear",
        {"player_uuid": str(player_uuid)},
    )).ok


# ============================================================
# 3. Sound  (top-level, by UUID)
# ============================================================

async def play_sound(
    player_uuid: str | UUID,
    sound_id: str,
    volume: float = 1.0,
    pitch: float = 1.0,
) -> bool:
    """在玩家位置播放声音（周围玩家也能听到）。

    :param player_uuid: 目标玩家 UUID（决定播放位置）。
    :param sound_id: 声音 ID，如 ``minecraft:block.note_block.pling``。
    :param volume: 音量（默认 1.0）。
    :param pitch: 音高（默认 1.0）。
    :return: Java 端是否成功处理。
    """
    return (await get_context().client.command(
        "play_sound",
        {
            "player_uuid": str(player_uuid),
            "sound_id": sound_id,
            "volume": float(volume),
            "pitch": float(pitch),
        },
    )).ok


async def play_sound_private(
    player_uuid: str | UUID,
    sound_id: str,
    volume: float = 1.0,
    pitch: float = 1.0,
) -> bool:
    """仅向指定玩家私人播放声音。

    :param player_uuid: 唯一能听到声音的玩家 UUID。
    :param sound_id: 声音 ID。
    :param volume: 音量（默认 1.0）。
    :param pitch: 音高（默认 1.0）。
    :return: Java 端是否成功处理。
    """
    return (await get_context().client.command(
        "play_sound_private",
        {
            "player_uuid": str(player_uuid),
            "sound_id": sound_id,
            "volume": float(volume),
            "pitch": float(pitch),
        },
    )).ok


# ============================================================
# 4. Multi-target Custom KV Data (PDC)
# ============================================================

async def set_custom_data(
    target_type: str,
    target_uuid: str | UUID,
    key: str,
    value: str | int | float | bool | list | dict,
    *,
    world: str | None = None,
    pos: list[int] | None = None,
) -> bool:
    """在 Java 端为当前 package 存储 KV 自定义数据（PDC）。

    支持三种目标类型：

    * ``"player"`` — 玩家：需提供 ``target_uuid``。
    * ``"entity"`` — 实体：需提供 ``target_uuid``。
    * ``"block"`` — 方块（Tile Entity）：需提供 ``world`` + ``pos=[x,y,z]``。
      ``target_uuid`` 可传任意占位字符串（Java 端 block 分支不读取）。

    :param target_type: ``"player"`` / ``"entity"`` / ``"block"``。
    :param target_uuid: 玩家或实体 UUID；block 传占位即可。
    :param key: 数据键名。
    :param value: 数据值。
    :param world: 仅 block 类型需要：世界名称。
    :param pos: 仅 block 类型需要：``[x, y, z]`` 坐标列表。
    :return: Java 端是否成功处理。
    """
    data: dict[str, Any] = {
        "target_type": target_type,
        "target_uuid": str(target_uuid),
        "package_name": get_context().package_name,
        "data_key": key,
        "data_value": value,
    }
    if target_type == "block":
        if world is not None:
            data["world"] = world
        if pos is not None:
            data["pos"] = [int(v) for v in pos]

    return (await get_context().client.command("set_custom_data", data)).ok


async def remove_custom_data(
    target_type: str,
    target_uuid: str | UUID,
    key: str,
    *,
    world: str | None = None,
    pos: list[int] | None = None,
) -> bool:
    """删除之前通过 :func:`set_custom_data` 存储的 KV 数据。

    参数含义与 :func:`set_custom_data` 一致。

    :return: Java 端是否成功处理。
    """
    data: dict[str, Any] = {
        "target_type": target_type,
        "target_uuid": str(target_uuid),
        "package_name": get_context().package_name,
        "data_key": key,
    }
    if target_type == "block":
        if world is not None:
            data["world"] = world
        if pos is not None:
            data["pos"] = [int(v) for v in pos]

    return (await get_context().client.command("remove_custom_data", data)).ok


# ============================================================
# 5. Re-exports  (从领域模块 re-export，保持 commands 为统一入口)
#
# 放在文件末尾：此时本模块所有函数已定义完毕；block/entity 模块
# 本身不 import commands，因此不会产生循环导入。
# ============================================================

from .block import (  # noqa: E402  (末尾 re-export，无需 top-level)
    set_block as set_block,
    get_block as get_block,
)
from .entity import (  # noqa: E402
    get_entity as get_entity,
)
