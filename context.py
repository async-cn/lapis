from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .client import LapisClient
    from .events import EventRegistry

@dataclass
class LapisContext:
    package_name: str
    client: LapisClient
    event_registry: EventRegistry