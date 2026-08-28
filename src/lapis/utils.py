from typing import Any

class Data:

    data: dict[str, Any]

    def __init__(self, data:dict[str, Any]):
        self.data = data

    def get(self, path:str) -> Any | None:
        """
        获取指定路径对应的值
        :param path: 路径字符串，用“.”分隔
        :return: 获取到的结果，若路径错误则为None
        """
        current = self.data
        for p in path.split("."):
            if hasattr(current, "__getitem__") and p in current.keys():
                current = current[p]
            else:
                return None
        return current

    def raw(self) -> dict[str, Any]:
        return self.data

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

def dict_trans(
        d: dict[str, Any],
        map: dict[str, str]
):
    result = {}
    for key, value in d.items():
        if key in map:
            result[map[key]] = value
    return result
