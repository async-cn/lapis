"""Lapis 自定义异常体系。

所有对外可抛异常的根类为 :class:`LapisError`。
按子系统进一步细分，便于调用方精确捕获。
"""

from __future__ import annotations


# ============================================================
# 根异常
# ============================================================

class LapisError(Exception):
    """Lapis SDK 所有异常的基类。"""


# ============================================================
# Player 子系统
# ============================================================

class PlayerError(LapisError):
    """玩家操作相关异常。"""


class PlayerInconcreteError(PlayerError):
    """尝试对非 concrete（占位）Player 实例执行具体操作。"""

    def __init__(self) -> None:
        super().__init__(
            "Cannot perform this operation on an inconcrete Player instance. "
            "Use a Player obtained from event data instead."
        )


# ============================================================
# Config 子系统
# ============================================================

class ConfigError(LapisError):
    """配置加载 / 校验异常。"""


# ============================================================
# Package Loader 子系统
# ============================================================

class PackageLoadError(LapisError):
    """Package 加载 / 导入失败。"""


class PackageFormatError(PackageLoadError):
    """Package 结构不合法（缺少 __init__.py / main() 等）。"""


# ============================================================
# Block / World 子系统
# ============================================================

class BlockError(LapisError):
    """方块相关异常。"""


# ============================================================
# NBT 子系统
# ============================================================

class NBTError(LapisError):
    """NBT 操作异常。"""


class NBTReservedKeyError(NBTError):
    """试图使用 NBT 保留字段作为 key。"""

    def __init__(self, key: str) -> None:
        super().__init__(f"NBT key {key!r} is reserved and cannot be used")


# ============================================================
# Event 子系统
# ============================================================

class EventError(LapisError):
    """事件系统异常。"""
