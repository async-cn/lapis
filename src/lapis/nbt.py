"""NBT 容器类。

.. deprecated:: 0.1.0
   本模块的 :class:`NBT` 类已被标记为废弃，后续版本将改用
   普通 ``dict`` + :class:`lapis.utils.Data` 表达 NBT 数据。
"""

from __future__ import annotations

import warnings
from typing import Any

from .exceptions import NBTReservedKeyError


_RESERVED_KEYS = frozenset(
    {"data", "__init__", "raw", "getvalue", "setvalue"}
)


class NBT:
    """兼容旧版代码的 NBT 容器。

    .. deprecated:: 0.1.0
       请使用普通 ``dict`` 或 :class:`lapis.utils.Data` 替代。
    """

    data: dict[str, Any]

    def __init__(self, **data: Any) -> None:
        warnings.warn(
            "NBT class is deprecated and will be removed in a future release; "
            "use plain dict or lapis.utils.Data instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.data = data

    def raw(self) -> dict[str, Any]:
        return self.data

    def getvalue(self, key: str) -> Any:
        return self.data[key]

    def setvalue(self, key: str, value: Any) -> None:
        if key in _RESERVED_KEYS:
            raise NBTReservedKeyError(key)
        self.data[key] = value
