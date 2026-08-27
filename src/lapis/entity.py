from lapis.pos import Pos


class EntityPos(Pos):
    def __repr__(self) -> str:
        return f"EntityPos({self.world}: {self.x}, {self.y}, {self.z})"
