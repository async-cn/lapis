"""彩色日志输出。

基础用法::

    from lapis.log import info, warning, error, debug, remind

    info("package 启动成功")
    warning("未找到配置文件，使用默认值")
    error("连接 Java Bridge 失败")

特性
----
* 统一前缀：``[时间][级别][包名] 消息``
* 基于 colorama 的彩色输出（检测到非 TTY 时自动关闭）
* 可选的日志文件输出（Config.LOG_FILE / Config.LOG_FILE_LEVEL）
* 日志级别过滤（除 DEBUG 单独开关外，INFO/WARN/ERROR 也可独立开关）
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import colorama
from colorama import Fore

from .config import Config


# ============================================================
# 颜色 / TTY 检测
# ============================================================

def _supports_color() -> bool:
    """判断当前 stdout 是否可以安全地打印彩色输出。"""
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        # colorama 仍需 init，让它在 Windows 上转换 ANSI 序列
        colorama.init()
        return True
    stream = sys.stdout
    if not hasattr(stream, "isatty") or not stream.isatty():
        return False
    # colorama.init() 会自动处理 Windows 旧终端的 ANSI 转换，
    # 其他平台基本是 no-op，可以安全调用。
    colorama.init()
    return True


_COLORS = {
    "info": Fore.LIGHTGREEN_EX,
    "warning": Fore.LIGHTYELLOW_EX,
    "error": Fore.LIGHTRED_EX,
    "remind": Fore.LIGHTBLUE_EX,
    "debug": Fore.LIGHTMAGENTA_EX,
}

_USE_COLOR = _supports_color()
_RESET = Fore.RESET if _USE_COLOR else ""


# ============================================================
# 日志级别开关（默认都开启，DEBUG 受 Config.DEBUG 也影响）
# ============================================================

_LEVEL_ENABLED: dict[str, bool] = {
    "info": True,
    "warning": True,
    "error": True,
    "remind": True,
    # debug 额外受 Config.DEBUG 控制
    "debug": True,
}


def set_level_enabled(level: str, enabled: bool) -> None:
    """开启或关闭指定级别的日志。"""
    _LEVEL_ENABLED[level.lower()] = bool(enabled)


# ============================================================
# 文件日志（可选）
# ============================================================

_LOG_FILE_HANDLE: Any = None
_LOG_FILE_LEVEL: str = "info"


def _ensure_log_file() -> Any:
    """根据 Config 延迟打开日志文件，只打开一次。"""
    global _LOG_FILE_HANDLE

    if _LOG_FILE_HANDLE is not None:
        return _LOG_FILE_HANDLE

    log_path = getattr(Config, "LOG_FILE", None)
    if not log_path:
        return None

    try:
        path = Path(log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        _LOG_FILE_HANDLE = path.open("a", encoding="utf-8")
    except OSError:
        # 打不开就静默降级，不要因为日志影响业务
        return None

    # 记住设定的日志文件级别（默认 info 及以上）
    global _LOG_FILE_LEVEL
    _LOG_FILE_LEVEL = getattr(Config, "LOG_FILE_LEVEL", "info").lower()

    return _LOG_FILE_HANDLE


_LEVEL_RANK = {
    "debug": 0,
    "info": 1,
    "remind": 2,
    "warning": 3,
    "error": 4,
}


def _write_log_file(level: str, timestamp: str, package: str, message: str) -> None:
    fh = _ensure_log_file()
    if fh is None:
        return
    if _LEVEL_RANK.get(level, 0) < _LEVEL_RANK.get(_LOG_FILE_LEVEL, 0):
        return
    try:
        fh.write(f"[{timestamp}][{level.upper()}][{package}] {message}\n")
        fh.flush()
    except OSError:
        pass


# ============================================================
# 核心 log()
# ============================================================

def log(msg: Any, level: str = "INFO") -> None:
    """输出一行日志。

    :param msg: 任意可字符串化对象。
    :param level: ``INFO`` / ``WARNING`` / ``ERROR`` / ``REMIND`` / ``DEBUG``。
    """
    level_lower = level.lower()
    if not _LEVEL_ENABLED.get(level_lower, True):
        return
    if level_lower == "debug" and not Config.DEBUG:
        return

    try:
        from .runtime import get_context as _ctx
        package = _ctx().package_name
    except Exception:
        package = "lapis"

    text = str(msg)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ---- 控制台（彩色或纯文本）----
    if _USE_COLOR:
        color = _COLORS.get(level_lower, "")
        prefix = (
            f"[{ts}][{color}{level.upper()}{_RESET}]"
            f"[{package}] "
        )
        print(f"{prefix}{text}")
    else:
        print(f"[{ts}][{level.upper()}][{package}] {text}")

    # ---- 文件（纯文本，可选）----
    _write_log_file(level_lower, ts, package, text)


# ============================================================
# 便捷函数
# ============================================================

def info(msg: Any) -> None:
    log(msg, "info")


def warning(msg: Any) -> None:
    log(msg, "warning")


def error(msg: Any) -> None:
    log(msg, "error")


def remind(msg: Any) -> None:
    log(msg, "remind")


def debug(msg: Any) -> None:
    log(msg, "debug")
