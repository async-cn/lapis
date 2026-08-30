"""Lapis 运行时上下文与 ContextVar 管理。

在单进程中运行多个 Package 时，:class:`Runtime` 负责在进入
Package 的 ``main()`` 前切换 :data:`ContextVar`，退出时重置，
确保各 Package 访问到的 ``get_context()`` 返回其专属的
:class:`LapisContext`。
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import TYPE_CHECKING

import asyncio

from .config import Config
from .log import debug, info, warning, error

if TYPE_CHECKING:
    from .context import LapisContext
    from .client import LapisClient


_current_context: ContextVar["LapisContext | None"] = ContextVar(
    "lapis_current_context",
    default=None,
)


# ============================================================
# Runtime
# ============================================================

class Runtime:
    """单个 Package 的运行时：上下文生命周期 + 连接保活 + 自动重连。"""

    def __init__(self, package_name: str) -> None:
        self.package_name: str = package_name
        self.context: LapisContext | None = None
        self.module = None  # Loader 导入的 ModuleType，可选

        # set_context() 返回的 token，用于 reset
        self._context_token: Token[LapisContext | None] | None = None

        # 当前活跃的事件循环 task（由 start() 填充）
        self._keepalive_task: asyncio.Task[None] | None = None

    # --------------------------------------------------------
    # ContextVar 管理
    # --------------------------------------------------------

    def bind_context(self, context: LapisContext) -> None:
        """绑定一个 :class:`LapisContext`，并将其设为当前上下文。

        重复调用会先 reset 上一次绑定的上下文。
        """
        if self._context_token is not None:
            try:
                reset_context(self._context_token)
            except Exception:
                pass
            self._context_token = None
        self.context = context
        self._context_token = set_context(context)

    def activate(self) -> Token["LapisContext | None"]:
        """将本 Runtime 的 context 激活为当前上下文。调用方负责 reset。"""
        if self.context is None:
            raise RuntimeError(
                f"Runtime {self.package_name!r} has no LapisContext bound"
            )
        return set_context(self.context)

    # --------------------------------------------------------
    # Startup
    # --------------------------------------------------------

    async def start(self) -> None:
        """建立连接、注册事件，并保活直到任务结束或用户取消。

        包含被动断线后的指数退避自动重连（可通过
        :attr:`Config.MAX_RECONNECT_ATTEMPTS` 调参）。
        """
        if self.context is None:
            raise RuntimeError(
                "Runtime.context is not set; did you call Runtime.bind_context()?"
            )

        client = self.context.client
        if client is None:
            raise RuntimeError(
                "Runtime.context.client is None; this Runtime has no Java Bridge client"
            )

        # 初次连接 + 注册事件监听器
        await self._connect_and_register(client)

        # 进入保活循环，直到被取消 / 达到最大重连次数
        self._keepalive_task = asyncio.current_task()
        await self._keepalive_loop(client)

    # --------------------------------------------------------
    # 内部：连接 & 注册
    # --------------------------------------------------------

    async def _connect_and_register(self, client: "LapisClient") -> None:
        await client.connect()

        registry = self.context.event_registry if self.context else None
        if registry is not None:
            await registry.register_all()

    # --------------------------------------------------------
    # 内部：保活 + 重连
    # --------------------------------------------------------

    async def _keepalive_loop(self, client: "LapisClient") -> None:
        """跟踪 reader_task 的生命周期；被动断线时按策略重连。"""
        while True:
            reader_task = client.reader_task
            if reader_task is None:
                # 极端情况：connect 之后 reader_task 还没赋值？等一下再查
                await asyncio.sleep(0.1)
                continue

            try:
                await reader_task
            except asyncio.CancelledError:
                raise
            except Exception:
                # reader_task 内部已调用 _handle_disconnect 做清理；
                # 这里只需要判断是否需要重连
                pass

            # ---- reader_task 结束了：要么主动 close，要么被动断线 ----
            if client.is_closing_by_user:
                debug("Connection closed by user; keepalive loop exiting")
                return

            # 被动断线 → 尝试重连
            max_attempts = int(Config.MAX_RECONNECT_ATTEMPTS)
            base_delay = float(Config.RECONNECT_BASE_DELAY)
            if max_attempts <= 0:
                warning(
                    "Java Bridge connection lost and MAX_RECONNECT_ATTEMPTS=0; "
                    "exiting keepalive loop."
                )
                return

            info(
                "Java Bridge connection lost; attempting automatic reconnect "
                f"(up to {max_attempts} attempts, base delay={base_delay:.2f}s)."
            )

            connected = False
            for attempt in range(1, max_attempts + 1):
                delay = base_delay * (2 ** (attempt - 1))
                info(f"Reconnect attempt {attempt}/{max_attempts} in {delay:.2f}s ...")
                try:
                    await asyncio.sleep(delay)
                    await self._connect_and_register(client)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    error(f"Reconnect attempt {attempt} failed: {exc!r}")
                    continue

                info(
                    f"Reconnect attempt {attempt} succeeded; "
                    "event listeners re-registered."
                )
                connected = True
                break

            if not connected:
                error(
                    f"All {max_attempts} reconnect attempts exhausted; "
                    "exiting keepalive loop."
                )
                return

            # 重连成功：回到循环顶部继续监听新的 reader_task


# ============================================================
# ContextVar helpers
# ============================================================

def get_context() -> "LapisContext":
    """获取当前 Package 绑定的 :class:`LapisContext`。

    :raises RuntimeError: 当前进程没有活动的 Lapis 上下文（通常是忘记先调用
        ``lapis.init(package_name)``）。
    """
    context = _current_context.get()

    if context is None:
        raise RuntimeError(
            "No LapisContext is currently active. "
            "Please call `lapis.init(<package_name>)` at the top of your package "
            "before using any Lapis API."
        )

    return context


def set_context(context: "LapisContext") -> Token["LapisContext | None"]:
    """设置当前 ContextVar，返回用于还原的 :class:`Token`。"""
    return _current_context.set(context)


def reset_context(token: Token["LapisContext | None"]) -> None:
    """根据 token 还原上一个 ContextVar 状态。"""
    _current_context.reset(token)
