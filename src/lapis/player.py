from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any, Callable, TypeVar, cast
from functools import wraps

from .runtime import get_context
from .message import format_message, format_title_component
from .entity import EntityPos
from .exceptions import PlayerInconcreteError
from .utils import Data

if TYPE_CHECKING:
    from .item import ItemStack

    F = TypeVar("F", bound=Callable[..., Any])


class Player:

    uuid: str
    is_concrete: bool

    # ---- Event Data 玩家快照属性 ----
    name: str
    nbt: Data

    # 位置朝向（nbt: Dimension / Pos / Rotation）
    world: str
    x: float
    y: float
    z: float
    yaw: float
    pitch: float

    # 生命（max_health 来自 nbt.attributes 中 minecraft:max_health 的 base）
    health: float | None
    max_health: float | None
    absorption: float | None

    # 饱食度
    food_level: int | None
    food_saturation: float | None
    food_exhaustion: float | None

    # 经验
    xp_level: int | None
    xp_progress: float | None
    xp_total: int | None

    # 其他状态
    gamemode: int | None
    on_ground: bool | None
    fire_ticks: int | None
    air: int | None
    invulnerable: bool | None
    selected_item_slot: int | None
    selected_item: Data | None
    score: int | None

    # 容器数据（物品字典在 __init__ 中统一包装为 Data；不转 ItemStack，保留 Slot/components 信息）
    inventory: list[Data]
    ender_items: list[Data]
    equipment: dict[str, Data]
    abilities: dict
    attributes: list

    def __init__(
        self,
        uuid: str,
        name: str = "",
        nbt: dict[str, Any] | Data | None = None,
        world: str = "",
        x: float = 0.0,
        y: float = 0.0,
        z: float = 0.0,
        yaw: float = 0.0,
        pitch: float = 0.0,
        health: float | None = None,
        max_health: float | None = None,
        absorption: float | None = None,
        food_level: int | None = None,
        food_saturation: float | None = None,
        food_exhaustion: float | None = None,
        xp_level: int | None = None,
        xp_progress: float | None = None,
        xp_total: int | None = None,
        gamemode: int | None = None,
        on_ground: bool | None = None,
        fire_ticks: int | None = None,
        air: int | None = None,
        invulnerable: bool | None = None,
        selected_item_slot: int | None = None,
        score: int | None = None,
        inventory: list | None = None,
        ender_items: list | None = None,
        equipment: dict | None = None,
        abilities: dict | None = None,
        attributes: list | None = None,
    ) -> None:
        self.uuid = uuid
        self.is_concrete = True

        self.name = name
        if nbt is None:
            nbt = {}
        self.nbt = nbt if isinstance(nbt, Data) else Data(nbt)

        self.world = world
        self.x = x
        self.y = y
        self.z = z
        self.yaw = yaw
        self.pitch = pitch

        self.health = health
        self.max_health = max_health
        self.absorption = absorption

        self.food_level = food_level
        self.food_saturation = food_saturation
        self.food_exhaustion = food_exhaustion

        self.xp_level = xp_level
        self.xp_progress = xp_progress
        self.xp_total = xp_total

        self.gamemode = gamemode
        self.on_ground = on_ground
        self.fire_ticks = fire_ticks
        self.air = air
        self.invulnerable = invulnerable
        self.selected_item_slot = selected_item_slot
        self.score = score

        self.inventory = [Data(i) if isinstance(i, dict) else i for i in (inventory or [])]
        self.ender_items = [Data(i) if isinstance(i, dict) else i for i in (ender_items or [])]
        self.equipment = {slot: (Data(v) if isinstance(v, dict) else v)
                          for slot, v in (equipment or {}).items()}
        self.abilities = abilities if abilities is not None else {}
        self.attributes = attributes if attributes is not None else []

        self.selected_item = None

        if self.selected_item_slot is not None:
            for item in self.inventory: # 近似O(1)复杂度，无需二分优化
                if item.get('Slot') == self.selected_item_slot:
                    self.selected_item = item
                    break
                elif item.get('Slot') > self.selected_item_slot:
                    break


    @property
    def pos(self) -> EntityPos:
        """返回当前玩家的 :class:`PlayerPos` 位置对象。"""
        return EntityPos(self.world, self.x, self.y, self.z)

    # --------------------------------------------------------
    # Concreteness guard
    # --------------------------------------------------------

    def _assert_concrete(self) -> None:
        """当 Player 为 inconcrete 占位对象时抛出异常。"""
        if not self.is_concrete:
            raise PlayerInconcreteError

    def require_concreteness(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """装饰器：在调用被装饰函数前校验 Player 为 concrete。

        兼容同步与异步函数。推荐在方法内部直接调用
        :meth:`_assert_concrete` 以获得更清晰的调用栈。
        """

        if inspect.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                self._assert_concrete()
                return await func(*args, **kwargs)

            return async_wrapper

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            self._assert_concrete()
            return func(*args, **kwargs)

        return sync_wrapper

    # --------------------------------------------------------
    # Messaging / Input
    # --------------------------------------------------------

    async def send_message(self, message: str | dict[str, Any], mini: bool = False) -> bool:
        """向玩家发送消息。

        :param message: 字符串表示纯文本；字典表示 Minecraft 文本组件。
        :return: Java 端是否成功处理
        """
        data = {
                "player_uuid": self.uuid,
                **format_message(message),
            }
        if mini:
            data["message_type"] = "mini_message"
        return (await get_context().client.command(
            "send_message",
            data
        )).ok

    async def ask_input(
        self,
        prompt: str | None = None,
        timeout: float = -1,
    ) -> str:
        """请求玩家在聊天栏输入内容。

        :param prompt: 可选的提示消息。``None`` 表示无提示。
        :param timeout: 超时秒数，``-1`` 表示不限时。
        :return: 玩家输入的字符串。
        :raises TimeoutError: 到达时限玩家未输入。
        """
        self._assert_concrete()
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
                        "message_content": "",
                    }
                ),
                "timeout": timeout,
            },
        )

        if result.data.get("result_type") == "timeout":
            raise TimeoutError("ask_input exceeded the timeout limit")

        return cast(str, result.data.get("result_content"))

    # --------------------------------------------------------
    # Title / ActionBar
    # --------------------------------------------------------

    async def show_title(
        self,
        title: str | dict[str, Any],
        subtitle: str | dict[str, Any] | None = None,
        fade_in: int = 10,
        stay: int = 70,
        fade_out: int = 20,
    ) -> bool:
        """向玩家显示标题。

        :param title: 主标题纯文本或文本组件 dict。
        :param subtitle: 副标题，``None`` 表示不显示。
        :param fade_in: 淡入 tick 数（默认 10）。
        :param stay: 停留 tick 数（默认 70）。
        :param fade_out: 淡出 tick 数（默认 20）。
        :return: Java 端是否成功处理。
        """
        self._assert_concrete()
        title_type, title_content = format_title_component(title)
        data: dict[str, Any] = {
            "player_uuid": self.uuid,
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

    async def actionbar_set(self, message: str | dict[str, Any]) -> bool:
        """设置玩家 ActionBar（快捷栏上方）消息。

        :param message: 纯文本或文本组件。
        :return: Java 端是否成功处理。
        """
        self._assert_concrete()
        return (await get_context().client.command(
            "actionbar_set",
            {
                "player_uuid": self.uuid,
                **format_message(message),
            },
        )).ok

    async def actionbar_clear(self) -> bool:
        """清除玩家 ActionBar 消息。

        :return: Java 端是否成功处理。
        """
        self._assert_concrete()
        return (await get_context().client.command(
            "actionbar_clear",
            {"player_uuid": self.uuid},
        )).ok

    # --------------------------------------------------------
    # Sound
    # --------------------------------------------------------

    async def play_sound(
        self,
        sound_id: str,
        volume: float = 1.0,
        pitch: float = 1.0,
    ) -> bool:
        """在玩家位置播放声音（周围玩家也能听到）。

        :param sound_id: 声音 ID，如 ``minecraft:block.note_block.pling``。
        :param volume: 音量（默认 1.0）。
        :param pitch: 音高（默认 1.0）。
        :return: Java 端是否成功处理。
        """
        self._assert_concrete()
        return (await get_context().client.command(
            "play_sound",
            {
                "player_uuid": self.uuid,
                "sound_id": sound_id,
                "volume": float(volume),
                "pitch": float(pitch),
            },
        )).ok

    async def play_sound_private(
        self,
        sound_id: str,
        volume: float = 1.0,
        pitch: float = 1.0,
    ) -> bool:
        """仅向当前玩家私人播放声音。

        :param sound_id: 声音 ID。
        :param volume: 音量（默认 1.0）。
        :param pitch: 音高（默认 1.0）。
        :return: Java 端是否成功处理。
        """
        self._assert_concrete()
        return (await get_context().client.command(
            "play_sound_private",
            {
                "player_uuid": self.uuid,
                "sound_id": sound_id,
                "volume": float(volume),
                "pitch": float(pitch),
            },
        )).ok

    # --------------------------------------------------------
    # Inventory
    # --------------------------------------------------------

    async def give_item(self, item_stack: ItemStack) -> None:
        """给予玩家物品。"""
        self._assert_concrete()
        await get_context().client.command(
            "give_item",
            {
                "player_uuid": self.uuid,
                **item_stack.raw(),
            },
        )

    async def take_item(self, item_stack: ItemStack) -> bool:
        """从玩家背包扣除物品。

        :return: ``True`` 表示扣除成功。
        """
        self._assert_concrete()
        return cast(
            bool,
            (await get_context().client.command(
                "take_item",
                {
                    "player_uuid": self.uuid,
                    **item_stack.raw(),
                },
            )).data.get("is_success"),
        )

    # --------------------------------------------------------
    # Custom KV data
    # --------------------------------------------------------

    async def set_custom_data(
        self,
        key: str,
        value: str | int | float | bool | list | dict,
    ) -> None:
        """在 Java 端为当前 package 存储一份 KV 自定义数据（PDC）。"""
        self._assert_concrete()
        await get_context().client.command(
            "set_custom_data",
            {
                "target_type": "player",
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
        self._assert_concrete()
        await get_context().client.command(
            "remove_custom_data",
            {
                "target_type": "player",
                "target_uuid": self.uuid,
                "package_name": get_context().package_name,
                "data_key": key,
            },
        )

    # --------------------------------------------------------
    # Economy
    # --------------------------------------------------------

    async def money_query(self) -> float:
        """查询玩家经济余额。"""
        self._assert_concrete()
        return cast(
            float,
            (await get_context().client.command(
                "money_query",
                {"player_uuid": self.uuid},
            )).data.get("balance"),
        )

    async def money_give(self, amount: float) -> None:
        """向玩家发放经济。"""
        self._assert_concrete()
        await get_context().client.command(
            "money_give",
            {
                "player_uuid": self.uuid,
                "amount": amount,
            },
        )

    async def money_set(self, amount: float) -> None:
        """直接设置玩家经济余额。"""
        self._assert_concrete()
        await get_context().client.command(
            "money_set",
            {
                "player_uuid": self.uuid,
                "amount": amount,
            },
        )

    async def money_take(
        self,
        amount: float,
        force: bool = False,
    ) -> bool:
        """扣除玩家经济。

        :param amount: 金额。
        :param force: 若为 ``True``，即使余额不足也会强制扣除。
        :return: 是否成功扣款。
        """
        self._assert_concrete()
        return cast(
            bool,
            (await get_context().client.command(
                "money_take",
                {
                    "player_uuid": self.uuid,
                    "amount": amount,
                    "force": force,
                },
            )).data.get("is_success"),
        )


def create_target_player(uuid: str) -> Player:
    """创建一个 inconcrete 的 Player 占位对象。

    占位对象不可直接执行需要连接 Java 端的方法，
    会抛出 :class:`PlayerInconcreteError`。
    """
    player = Player(uuid)
    player.is_concrete = False
    return player


def create_player(raw: dict[str, Any]) -> Player:
    """从 Event Data 中的 player 子字典构造 :class:`Player`。

    :param raw: Event Data 玩家数据字典，结构参见
        ``standards/standard_player_in_event_data.json``：
        顶层含 ``uuid`` / ``name`` / ``nbt``；对缺失键全部容错
        （事件 subscription 可能只回传部分数据）。
        ``inventory`` / ``ender_items`` / ``equipment`` 中的物品字典
        会自动包装为 :class:`lapis.utils.Data`。
    :return: 填充完成的 :class:`Player` 对象。
    """
    nbt: dict[str, Any] = raw.get("nbt") or {}
    pos = nbt.get("Pos") or [0.0, 0.0, 0.0]
    rotation = nbt.get("Rotation") or [0.0, 0.0]
    attributes = nbt.get("attributes") or []
    max_health = next(
        (a.get("base") for a in attributes if a.get("id") == "minecraft:max_health"),
        None,
    )

    def _flag(key: str) -> bool | None:
        value = nbt.get(key)
        return None if value is None else bool(value)

    return Player(
        uuid=raw.get("uuid", ""),
        name=raw.get("name", ""),
        nbt=nbt,
        world=nbt.get("Dimension", ""),
        x=float(pos[0]),
        y=float(pos[1]),
        z=float(pos[2]),
        yaw=float(rotation[0]),
        pitch=float(rotation[1]),
        health=nbt.get("Health"),
        max_health=max_health,
        absorption=nbt.get("AbsorptionAmount"),
        food_level=nbt.get("foodLevel"),
        food_saturation=nbt.get("foodSaturationLevel"),
        food_exhaustion=nbt.get("foodExhaustionLevel"),
        xp_level=nbt.get("XpLevel"),
        xp_progress=nbt.get("XpP"),
        xp_total=nbt.get("XpTotal"),
        gamemode=nbt.get("playerGameType"),
        on_ground=_flag("OnGround"),
        fire_ticks=nbt.get("Fire"),
        air=nbt.get("Air"),
        invulnerable=_flag("Invulnerable"),
        selected_item_slot=nbt.get("SelectedItemSlot"),
        score=nbt.get("Score"),
        inventory=list(nbt.get("Inventory") or []),
        ender_items=list(nbt.get("EnderItems") or []),
        equipment=dict(nbt.get("equipment") or {}),
        abilities=dict(nbt.get("abilities") or {}),
        attributes=list(attributes),
    )
