"""Lapis 配置模块。

配置来源（优先级从高到低）：
    1. ``CONFIG_PATH`` 指向的 TOML 文件中的显式值；
    2. 本模块内定义的默认值。

默认情况下，``CONFIG_PATH`` 指向 Lapis 包目录下的 ``config.toml``；
也可以通过环境变量 ``LAPIS_CONFIG_PATH`` 覆盖。

TOML 文件中允许的顶层 key 与 :class:`Config` 的属性名一一对应，例如::

    VERSION = "0.1.0"
    DEBUG = true
    SERVER_ADDR = "127.0.0.1"
    SERVER_PORT = 9331
    SERVER_PASSWORD = "pw114514"
    MAX_PACKET_SIZE = 16777215
    LOADER_PACKAGES_DIR = "../../../packages"

    [DIMENSIONS]
    overworld = "world"
    the_nether = "world_nether"
    the_end = "world_end"

``DIMENSIONS`` 为 TOML table 时，会与默认值 **合并**（TOML 中的同名 key
会覆盖默认值，未出现的 key 继续沿用默认）。

使用方式与原实现保持一致，仍然通过类属性访问::

    from lapis.config import Config
    print(Config.SERVER_ADDR, Config.SERVER_PORT, Config.DIMENSIONS)

也允许在导入后、``lapis.init()`` 调用之前通过类属性临时覆盖，这种写法
不会写入 TOML 文件，仅对当前进程生效::

    Config.SERVER_ADDR = "mc.example.com"
    Config.SERVER_PORT = 19331
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict


# ============================================================
# TOML 解析库：tomllib (>=3.11) -> tomli (<3.11) -> toml（兜底）
# ============================================================

if sys.version_info >= (3, 11):
    import tomllib as _tomllib  # type: ignore[no-redef]
else:
    try:
        import tomli as _tomllib  # type: ignore[no-redef]
    except ImportError:  # pragma: no cover - 作为最后的兜底
        try:
            import toml as _toml_backend  # type: ignore

            class _TomlCompat:
                """兼容旧版 ``toml`` 包的 loads 接口。"""

                @staticmethod
                def loads(s: str) -> Dict[str, Any]:
                    return _toml_backend.loads(s)

            _tomllib = _TomlCompat  # type: ignore[assignment]
        except ImportError as exc:  # pragma: no cover - 安装时缺依赖
            raise ImportError(
                "No TOML parser available. "
                "Install 'tomli' for Python <3.11, or use Python >=3.11 "
                "(which ships tomllib in the standard library)."
            ) from exc


# ============================================================
# CONFIG_PATH 解析
# ============================================================

_PACKAGE_DIR = Path(__file__).resolve().parent
"""Lapis 包所在目录（即本文件所在目录）。"""

_ENV_CONFIG_PATH = os.environ.get("LAPIS_CONFIG_PATH")
"""可选的环境变量覆盖。"""

CONFIG_PATH: Path = (
    Path(_ENV_CONFIG_PATH).resolve()
    if _ENV_CONFIG_PATH
    else _PACKAGE_DIR / "config.toml"
)
"""实际使用的 TOML 配置文件路径。

默认值：``<lapis包目录>/config.toml``；
可通过环境变量 ``LAPIS_CONFIG_PATH`` 覆盖。
"""


# ============================================================
# 默认值（保留原字段名 & 默认值，仅 VERSION 从 0.0.9 对齐到 0.1.0）
# ============================================================

_DEFAULT_VERSION: str = "0.1.0"
_DEFAULT_DEBUG: bool = False
_DEFAULT_LOADER_PACKAGES_DIR: str = "../../../packages"
_DEFAULT_SERVER_ADDR: str = "localhost"
_DEFAULT_SERVER_PORT: int = 9331
_DEFAULT_SERVER_PASSWORD: str = "pw114514"
_DEFAULT_MAX_PACKET_SIZE: int = 0xFFFFFF  # 16 * 1024 * 1024
_DEFAULT_DIMENSIONS: Dict[str, str] = {
    "overworld": "world",
    "the_nether": "world_nether",
    "the_end": "world_end",
}


# ============================================================
# TOML 读取 & 类型转换
# ============================================================

def _load_toml_file(path: Path) -> Dict[str, Any]:
    """读取并解析 TOML 文件；文件不存在时返回空 dict。"""

    if not path.is_file():
        return {}
    raw_bytes = path.read_bytes()
    return _tomllib.loads(raw_bytes.decode("utf-8"))  # type: ignore[no-any-return]


def _coerce_bool(value: Any) -> bool:
    """把常见的布尔表示（bool / 数字 / 字符串）安全转换为 bool。"""

    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    raise TypeError(f"Cannot coerce {type(value).__name__} to bool")


def _apply_overrides(
    cls: type,
    data: Dict[str, Any],
) -> None:
    """把 TOML 中读取到的字段按名覆盖到 ``Config`` 类属性。

    - 未在 TOML 中出现的字段保持默认值；
    - ``DIMENSIONS`` 采用合并策略（TOML 表的 key 覆盖默认 key）；
    - 标量字段会经过安全的类型转换，非法值抛出 ``ValueError``；
    - 未识别的顶层 key 会被忽略（避免用户在 TOML 里写了别的配置导致崩溃）。
    """

    # TOML key -> (Config 类属性名, 类型转换函数)
    scalar_fields: Dict[str, Any] = {
        "VERSION": ("VERSION", str),
        "DEBUG": ("DEBUG", _coerce_bool),
        "LOADER_PACKAGES_DIR": ("LOADER_PACKAGES_DIR", str),
        "SERVER_ADDR": ("SERVER_ADDR", str),
        "SERVER_PORT": ("SERVER_PORT", int),
        "SERVER_PASSWORD": ("SERVER_PASSWORD", str),
        "MAX_PACKET_SIZE": ("MAX_PACKET_SIZE", int),
    }

    for key, (attr, caster) in scalar_fields.items():
        if key not in data:
            continue
        try:
            setattr(cls, attr, caster(data[key]))
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Invalid value for config key {key!r}: {data[key]!r}"
            ) from exc

    # DIMENSIONS：table 合并
    dimensions = data.get("DIMENSIONS")
    if dimensions is not None:
        if not isinstance(dimensions, dict):
            raise ValueError(
                "Config key 'DIMENSIONS' must be a TOML table (dict), "
                f"got {type(dimensions).__name__}"
            )
        merged = dict(cls.DIMENSIONS)
        merged.update({str(k): str(v) for k, v in dimensions.items()})
        cls.DIMENSIONS = merged


# ============================================================
# Config 容器（保持"类属性访问"风格，与现有调用点兼容）
# ============================================================

class Config:
    """Lapis 运行时配置容器。

    所有字段均可通过 :data:`CONFIG_PATH` 指向的 TOML 文件覆盖。
    """

    VERSION: str = _DEFAULT_VERSION
    DEBUG: bool = _DEFAULT_DEBUG
    LOADER_PACKAGES_DIR: str = _DEFAULT_LOADER_PACKAGES_DIR
    SERVER_ADDR: str = _DEFAULT_SERVER_ADDR
    SERVER_PORT: int = _DEFAULT_SERVER_PORT
    SERVER_PASSWORD: str = _DEFAULT_SERVER_PASSWORD
    MAX_PACKET_SIZE: int = _DEFAULT_MAX_PACKET_SIZE
    DIMENSIONS: Dict[str, str] = dict(_DEFAULT_DIMENSIONS)

    # 运行时诊断字段：实际使用的配置文件路径 & 是否成功加载到了非空 TOML
    CONFIG_FILE_USED: str = str(CONFIG_PATH)
    CONFIG_FILE_LOADED: bool = False


# ============================================================
# 模块加载时自动应用 TOML 覆盖
# ============================================================

def _initialize_from_file() -> None:
    toml_data = _load_toml_file(CONFIG_PATH)
    if toml_data:
        _apply_overrides(Config, toml_data)
        Config.CONFIG_FILE_LOADED = True
    # 即便文件不存在，也同步一下最终使用的路径，便于排查
    Config.CONFIG_FILE_USED = str(CONFIG_PATH)


_initialize_from_file()
