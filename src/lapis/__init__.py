from .context import LapisContext
from .runtime import (
    Runtime,
    get_context,
    set_context,
    reset_context,
)

from .client import LapisClient
from .event import EventRegistry
from .config import Config
from .server_message import init_message_dispatcher
from .database import Database

# ---- 领域对象 & 顶层命令模块（方便用户 `import lapis; lapis.commands.xxx`）----
from . import commands as commands  # noqa: E402
from .player import Player, create_player  # noqa: E402
from .block import Block, set_block, get_block  # noqa: E402
from .entity import Entity, get_entity  # noqa: E402

_runtimes: dict[str, Runtime] = {}


def init(package_name: str) -> LapisContext:
    """创建当前 Package 的 Runtime + Context，并将其设为活动上下文。

    :returns: 新创建的 :class:`LapisContext`。
    :raises RuntimeError: 同一 ``package_name`` 已在当前进程中初始化。
    """

    if package_name in _runtimes:
        raise RuntimeError(
            f"Package {package_name!r} is already initialized"
        )

    runtime: Runtime = Runtime(package_name)
    context = LapisContext(
        package_name=package_name,
        client=LapisClient(Config.SERVER_ADDR, Config.SERVER_PORT, package_name),
        event_registry=EventRegistry(),
        database=Database(package_name),
    )
    runtime.context = context
    # 内部绑定：Runtime 记住 set_context 的 token，便于后续多 package 切换
    runtime.bind_context(context)
    _runtimes[package_name] = runtime

    init_message_dispatcher()

    return context


async def start() -> None:
    """启动当前 Package 的 Runtime：连接 Java 桥、注册事件、持续保活。"""
    package_name = get_context().package_name
    runtime = _runtimes[package_name]
    # 切换到该 Runtime 绑定的 Context（防御：即使 caller 切换过也保证正确）
    token = runtime.activate()
    try:
        await runtime.start()
    finally:
        reset_context(token)
