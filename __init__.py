from .context import LapisContext
from .runtime import (
    PackageRuntime,
    get_context,
    set_context,
    reset_context,
)

from .client import create_client
from .events import EventRegistry

_runtimes = {}


def init(package_name: str) -> LapisContext:

    if package_name in _runtimes:
        raise RuntimeError(
            f"Package {package_name!r} is already initialized"
        )

    runtime = PackageRuntime(package_name)

    context = LapisContext(
        package_name=package_name,
        client=create_client(),
        event_registry=EventRegistry(),
    )

    runtime.context = context

    _runtimes[package_name] = runtime

    set_context(context)

    return context