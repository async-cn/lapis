from .context import LapisContext
from .runtime import (
    PackageRuntime,
    get_context,
    set_context,
    reset_context,
)

from .client import LapisClient
from .events import EventRegistry
from .config import Config
from .message import init_message_dispatcher

_runtimes = {}

def init(package_name: str) -> LapisContext:

    if package_name in _runtimes:
        raise RuntimeError(
            f"Package {package_name!r} is already initialized"
        )

    runtime = PackageRuntime(package_name)
    context = LapisContext(
        package_name=package_name,
        client=LapisClient(Config.SERVER_ADDR, Config.SERVER_PORT, package_name),
        event_registry=EventRegistry(),
    )
    runtime.context = context

    init_message_dispatcher()

    _runtimes[package_name] = runtime
    set_context(context)
    return context