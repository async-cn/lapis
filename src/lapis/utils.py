from __future__ import annotations

from typing import Any
import warnings

class Data:
    """按点号分隔的路径访问嵌套字典的便捷容器。"""

    data: dict[str, Any]

    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data

    def get(self, path: str):
        """按 ``a.b.c`` 路径获取嵌套值；不存在时返回 ``None``。"""
        current: Any = self.data
        for p in path.split("."):
            if hasattr(current, "__getitem__") and p in current.keys():
                current = current[p]
            else:
                return None
        return current

    def __getitem__(self, key: str) -> Any:
        return self.get(key)

    def raw(self) -> dict[str, Any]:
        return self.data

    def __repr__(self) -> str:
        return f"Data({self.data})"


class Vector:
    """三维向量。

    .. deprecated:: 0.1.0
       :class:`Vector` 将在后续版本中移除，请直接在
       :class:`lapis.pos.Pos` 中使用 ``x``/``y``/``z`` 属性。
    """

    x: float
    y: float
    z: float

    def __init__(self, x: float, y: float, z: float) -> None:
        # 首次实例化时只提示一次，避免日志刷屏
        if not getattr(Vector, "_deprecation_warned", False):
            warnings.warn(
                "Vector is deprecated and will be removed in a future release; "
                "use lapis.pos.Pos (or a plain dataclass) instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            Vector._deprecation_warned = True  # type: ignore[attr-defined]
        self.x = x
        self.y = y
        self.z = z

    def __add__(self, other: "Vector") -> "Vector":
        return Vector(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: "Vector") -> "Vector":
        return Vector(self.x - other.x, self.y - other.y, self.z - other.z)

    def __str__(self) -> str:
        return f"{self.x} {self.y} {self.z}"

    def __repr__(self) -> str:
        return f"Vector({self.x}, {self.y}, {self.z})"

    def raw(self) -> list[float]:
        return [self.x, self.y, self.z]


def dict_trans(
    d: dict[str, Any],
    map: dict[str, str],
) -> dict[str, Any]:
    """按 ``{旧key: 新key}`` 的映射转换字典；key 不在映射中的丢弃。"""
    result: dict[str, Any] = {}
    for key, value in d.items():
        if key in map:
            result[map[key]] = value
    return result

