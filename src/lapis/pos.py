from typing import Any

from .utils import Vector

class Pos(Vector):
    world:str

    def __init__(self, world:str, x:int, y:int, z:int):
        super().__init__(x, y, z)
        self.world = world

    def raw(self) -> dict[str, Any]:
        return {
            "world": self.world,
            "pos": super().raw(),
        }

    def __repr__(self) -> str:
        return f"Pos({self.world}: {self.x}, {self.y}, {self.z})"


