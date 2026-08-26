from .utils import Vector

class Pos(Vector):
    def __repr__(self) -> str:
        return f"Pos({self.x}, {self.y}, {self.z})"

class BlockPos(Pos):
    x: int
    y: int
    z: int
    def __init__(self, x:int, y:int, z:int):
        super().__init__(x, y, z)

    def raw(self) -> list:
        return [int(self.x), int(self.y), int(self.z)]

class EntityPos(Pos):
    def __repr__(self) -> str:
        return f"EntityPos({self.x}, {self.y}, {self.z})"