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

class BlockPos(Pos):
    x: int
    y: int
    z: int
    def __init__(self, world:str, x:int, y:int, z:int):
        super().__init__(world, x, y, z)

    def raw(self) -> dict[str, Any]:
        return {
            "world": self.world,
            "pos": [int(self.x), int(self.y), int(self.z)]
        }

    def __repr__(self) -> str:
        return f"BlockPos({self.world}: {self.x}, {self.y}, {self.z})"

class EntityPos(Pos):
    def __repr__(self) -> str:
        return f"EntityPos({self.world}: {self.x}, {self.y}, {self.z})"