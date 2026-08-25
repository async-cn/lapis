from __future__ import annotations

from typing import TYPE_CHECKING
from functools import wraps
import inspect

from .runtime import get_context
from .log import warning

if TYPE_CHECKING:
    from typing import Any, Callable

_handlers: list[MessageHandler] = []

class Message:
    def __init__(self, raw_message: dict[str, Any]):
        self.message_type = raw_message["message_type"]
        self.data = raw_message["data"]


class MessageHandler:
    def __init__(self, message_type: str, handler: Callable,):
        self.message_type = message_type
        self.handler = handler


async def dispatcher(raw_message: dict[str, Any],) -> None:
    message = Message(raw_message)
    handled = False

    for handler in _handlers:
        if handler.message_type != message.message_type: continue

        result = handler.handler(message)

        if inspect.isawaitable(result):
            result = await result

        if result:
            handled = True
            break

    if not handled:
        warning(
            f"Unhandled message: "
            f"<{message.message_type}>"
            f"{message.data}"
        )


def init_message_dispatcher() -> None:
    get_context().client.set_message_handler(dispatcher)


def register_message_handler(handler: MessageHandler) -> None:
    _handlers.append(handler)


def message_handler(message_type: str):
    def decorator(func: Callable):
        register_message_handler(
            MessageHandler(message_type, func)
        )
        return func
    return decorator