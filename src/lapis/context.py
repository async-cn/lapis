from __future__ import annotations
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .client import LapisClient
    from .event import EventRegistry
    from .database import Database

@dataclass
class LapisContext:
    package_name: str
    client: LapisClient | None
    event_registry: EventRegistry | None
    database: Database | None