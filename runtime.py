from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .context import LapisContext

_current_context = ContextVar(
    "lapis_current_context",
    default=None,
)

class PackageRuntime:

    def __init__(self, package_name):
        self.package_name = package_name
        self.context = None
        self.module = None

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