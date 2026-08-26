from contextvars import ContextVar
from typing import TYPE_CHECKING

import asyncio

if TYPE_CHECKING:
    from .context import LapisContext

_current_context = ContextVar(
    "lapis_current_context",
    default=None,
)


class Runtime:

    def __init__(self, package_name):
        self.package_name = package_name
        self.context = None
        self.module = None

    async def start(self) -> None:
        # 建立 Java 连接
        await self.context.client.connect()
        # 统一注册 Listener
        await self.context.event_registry.register_all()
        # 长期运行
        await run()

async def run() -> None:

    # 只要 Client 的 reader_task 还活着，
    # Runtime 就应该持续存在。

    while True:
        await asyncio.sleep(3600)

def get_context() -> LapisContext|None:
    context = _current_context.get()

    if context is None:
        raise RuntimeError(
            "No LapisContext is currently active"
        )

    return context

def set_context(context):
    return _current_context.set(context)

def reset_context(token):
    _current_context.reset(token)