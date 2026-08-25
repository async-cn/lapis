from __future__ import annotations
from typing import TYPE_CHECKING
from functools import wraps

from .runtime import get_context

from .log import warning

if TYPE_CHECKING:
    from typing import Any, Callable

_handlers:list[MessageHandler] = []

class Message:
    def __init__(self, raw_message: dict[str, Any]):
        self.message_type = raw_message["message_type"]
        self.data = raw_message["data"]

class MessageHandler:
    def __init__(self, message_type:str, handler:Callable[[Message], bool]):
        self.message_type = message_type
        self.handler = handler

async def dispatcher(raw_message:dict[str, Any]) -> None:
    message = Message(raw_message)
    handled = False
    for handler in _handlers:
        if handler.message_type == message.message_type:
            if handler.handler(message):
                handled = True
                break
    if not handled:
        warning(f"Unhandled message: <{message.message_type}>{message.data}")

def init_message_dispatcher() -> None:
    get_context().client.set_message_handler(dispatcher)

def register_message_handler(handler: MessageHandler) -> None:
    _handlers.append(handler)

def message_handler(message_type:str):
    """
    装饰器，对消息handler函数使用，原始handler函数应接受一个Message参数
    :param message_type: 匹配的消息类型
    :return: 事件监听器UUID
    """
    def decorator(func:Callable[[Message], bool]):
        new_message_handler = MessageHandler(message_type, func)
        register_message_handler(new_message_handler)
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            return result if result is not None else True
        return wrapper
    return decorator