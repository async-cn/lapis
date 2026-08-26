from .context import LapisContext
from .runtime import (
    Runtime,
    get_context,
    set_context,
    reset_context,
)

from .client import LapisClient
from .events import EventRegistry
from .config import Config
from .server_message import init_message_dispatcher
from .database import Database

import asyncio

_runtimes = {}

def init(package_name: str) -> LapisContext:

    if package_name in _runtimes:
        raise RuntimeError(
            f"Package {package_name!r} is already initialized"
        )

    runtime:Runtime = Runtime(package_name)
    context = LapisContext(
        package_name=package_name,
        client=LapisClient(Config.SERVER_ADDR, Config.SERVER_PORT, package_name),
        event_registry=EventRegistry(),
        database = Database(package_name),
    )
    runtime.context = context
    _runtimes[package_name] = runtime
    set_context(context)

    init_message_dispatcher()

    return context

def start():
    try:
        asyncio.run(
            _runtimes[get_context().package_name].start()
        )
    except KeyboardInterrupt:
        print("KeyboardInterrupt -> Runtime Interrupted")