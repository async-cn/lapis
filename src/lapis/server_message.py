from __future__ import annotations

from typing import TYPE_CHECKING
import inspect

from .runtime import get_context
from .log import warning

if TYPE_CHECKING:
    from typing import Any, Awaitable, Callable


# ============================================================
# Message model
# ============================================================

class ServerMessage:
    """Java 端主动推送的消息（例如事件、通知等）。"""

    def __init__(self, raw_message: dict[str, Any]) -> None:
        self.message_type: str = raw_message["message_type"]
        self.data: dict[str, Any] = raw_message["data"]


class ServerMessageHandler:
    """按 ``message_type`` 精确匹配的处理器条目。"""

    def __init__(
        self,
        message_type: str,
        handler: Callable[[ServerMessage], Awaitable[Any] | Any],
    ) -> None:
        self.message_type: str = message_type
        self.handler: Callable[[ServerMessage], Awaitable[Any] | Any] = handler


# ============================================================
# Dispatcher
# ============================================================

async def dispatcher(raw_message: dict[str, Any]) -> None:
    """把 Java 端原始消息分发给当前 Context 的匹配处理器。

    已不再使用全局 ``_handlers`` 列表，而是读取
    :attr:`LapisContext.message_handlers`，保证多 Package 在同一进程内
    运行时互不干扰。
    """
    message = ServerMessage(raw_message)
    handled = False

    context = get_context()
    for handler in context.message_handlers:
        if handler.message_type != message.message_type:
            continue

        result = handler.handler(message)
        if inspect.isawaitable(result):
            result = await result

        if result:
            handled = True
            break

    if not handled:
        warning(
            f"Unhandled message: <{message.message_type}>{message.data!r}"
            f" (package={context.package_name})"
        )


def init_message_dispatcher() -> None:
    """把 dispatcher 挂到当前 Context 的 client 上。"""
    get_context().client.set_message_handler(dispatcher)


def register_message_handler(handler: ServerMessageHandler) -> None:
    """向当前 Context 追加一个消息处理器。"""
    get_context().message_handlers.append(handler)


def message_handler(message_type: str):
    """装饰器：将被装饰函数注册为指定 ``message_type`` 的处理器。

    函数返回值为 truthy 时，消息会被视为"已消费"，不再继续分发给后续处理器。
    """
    def decorator(func: Callable[[ServerMessage], Awaitable[Any] | Any]):
        register_message_handler(
            ServerMessageHandler(message_type, func)
        )
        return func
    return decorator
