class Vector:
    x: float
    y: float
    z: float

    def __init__(self, x:float, y:float, z:float):
        self.x = x
        self.y = y
        self.z = z

    def __add__(self, other:Vector) -> Vector:
        return Vector(
            self.x + other.x,
            self.y + other.y,
            self.z + other.z
        )

    def __sub__(self, other:Vector) -> Vector:
        return Vector(
            self.x - other.x,
            self.y - other.y,
            self.z - other.z
        )

    def __str__(self) -> str:
        return f"{self.x} {self.y} {self.z}"

    def __repr__(self) -> str:
        return f"Vector({self.x}, {self.y}, {self.z})"

    def raw(self) -> list:
        return [self.x, self.y, self.z]