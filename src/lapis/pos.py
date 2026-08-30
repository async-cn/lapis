from typing import Any

class Pos:

    world:str
    x: float
    y: float
    z: float

    def __init__(self, world:str, x:float, y:float, z:float):
        self.world = world
        self.x = x
        self.y = y
        self.z = z

    def raw(self) -> dict[str, Any]:
        return {
            "world": self.world,
            "pos": [self.x, self.y, self.z],
        }

    def __repr__(self) -> str:
        return f"Pos({self.world}: {self.x}, {self.y}, {self.z})"


