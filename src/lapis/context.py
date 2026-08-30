from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Awaitable, Any

if TYPE_CHECKING:
    from .client import LapisClient
    from .event import EventRegistry
    from .database import Database


# 避免循环导入：ServerMessageHandler 的定义放在 server_message.py 中；
# 这里只声明结构足够字段。
MessageHandlerT = Callable[["ServerMessage"], Awaitable[bool | None] | bool | None]


@dataclass
class LapisContext:
    package_name: str
    client: LapisClient | None
    event_registry: EventRegistry | None
    database: Database | None

    # ---- 每个 Package 独立的消息处理器列表（替代原先的全局 _handlers）----
    # 由 init_message_dispatcher() / @message_handler 装饰器维护
    message_handlers: list["ServerMessageHandler"] = field(default_factory=list)


# ---- 为了避免循环导入而延后的类型定义 ----
# 实际的 ServerMessage / ServerMessageHandler 类在 server_message.py 中
if TYPE_CHECKING:  # pragma: no cover
    from .server_message import ServerMessage, ServerMessageHandler  # noqa: F401
