"""Lapis 配置模块。

配置来源（优先级从高到低）：
    1. ``CONFIG_PATH`` 指向的 TOML 文件中的显式值；
    2. 本模块内定义的默认值。

默认情况下，``CONFIG_PATH`` 指向 Lapis 包目录下的 ``config.toml``；
也可以通过环境变量 ``LAPIS_CONFIG_PATH`` 覆盖。

TOML 支持两种书写风格（可混用），最终都会被归一化到平铺键后再应用：

* **平铺风格（推荐）**：

  .. code-block:: toml

      VERSION = "0.1.0"
      SERVER_ADDR = "127.0.0.1"
      SERVER_PASSWORD = "your-secret"

      [DIMENSIONS]
      overworld = "world"

* **嵌套分组风格（兼容 lapis-plugin 示例）**：

  .. code-block:: toml

      [SERVER]
      ADDR = "127.0.0.1"
      PASSWORD = "your-secret"

      [CLIENT]
      MAX_PACKET_SIZE = 16777215

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
from types import MappingProxyType
from typing import Any, Dict, Mapping

# 延迟导入：避免在 import config 时触发循环导入日志
# 密码警告需要日志，使用函数内局部 import。


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
# 默认值
# ============================================================

_DEFAULT_VERSION: str = "0.1.0"
_DEFAULT_DEBUG: bool = False
_DEFAULT_LOADER_PACKAGES_DIR: str = "../../../packages"
_DEFAULT_DATABASE_DIR: str = "./databases"
_DEFAULT_SERVER_ADDR: str = "localhost"
_DEFAULT_SERVER_PORT: int = 9331
_DEFAULT_SERVER_PASSWORD: str = "pw114514"
_DEFAULT_MAX_PACKET_SIZE: int = 0xFFFFFF  # 16 * 1024 * 1024
_DEFAULT_MAX_RECONNECT_ATTEMPTS: int = 5
_DEFAULT_RECONNECT_BASE_DELAY: float = 1.0
_DEFAULT_LANG: str = "zh_cn"
"""默认语言代码——对应 ``assets/lang/`` 下的语言目录名。"""

_DEFAULT_DIMENSIONS: Mapping[str, str] = MappingProxyType(
    {
        "overworld": "world",
        "the_nether": "world_nether",
        "the_end": "world_end",
    }
)
"""不可变的默认维度映射——避免被外部代码意外修改。"""


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


# ---- TOML 嵌套 table → 平铺字段映射 ------------------------------------------
# 例如 [SERVER] ADDR = "x"  →  SERVER_ADDR = "x"
_NESTED_GROUP_MAP: Dict[str, Dict[str, str]] = {
    "SERVER": {
        "ADDR": "SERVER_ADDR",
        "PORT": "SERVER_PORT",
        "PASSWORD": "SERVER_PASSWORD",
    },
    "CLIENT": {
        "MAX_PACKET_SIZE": "MAX_PACKET_SIZE",
    },
    "LOADER": {
        "PACKAGES_PATH": "LOADER_PACKAGES_DIR",
    },
    "LAPIS": {
        "VERSION": "VERSION",
        "DEBUG": "DEBUG",
    },
}


def _normalize_toml_data(raw: Dict[str, Any]) -> Dict[str, Any]:
    """将嵌套分组风格归一化为平铺字段字典（平铺风格原样保留）。

    维度表 ``DIMENSIONS`` 保持原样单独处理。
    """

    normalized: Dict[str, Any] = {}

    for key, value in raw.items():
        if isinstance(value, dict):
            # 分组 table
            if key in _NESTED_GROUP_MAP:
                sub_fields = _NESTED_GROUP_MAP[key]
                for sub_key, sub_value in value.items():
                    flat_key = sub_fields.get(str(sub_key).upper())
                    if flat_key is None:
                        # 未识别的子字段：尝试直接拼接（如 [DATABASE] PATH → DATABASE_PATH）
                        flat_key = f"{key.upper()}_{str(sub_key).upper()}"
                    normalized[flat_key] = sub_value
            elif key.upper() == "DIMENSIONS":
                # 保留给 dimensions 合并流程，键全部小写化
                normalized["DIMENSIONS"] = {
                    str(k).lower(): str(v) for k, v in value.items()
                }
            # 其他未知 table 忽略（避免用户写错导致 crash）
        else:
            # 顶层平铺键：按原样应用；DIMENSIONS 在此场景为非法，忽略
            if str(key).upper() == "DIMENSIONS" and isinstance(value, dict):
                normalized["DIMENSIONS"] = {
                    str(k).lower(): str(v) for k, v in value.items()
                }
            else:
                normalized[str(key).upper()] = value

    return normalized


def _apply_overrides(
    cls: type,
    data: Dict[str, Any],
) -> None:
    """把 TOML 中读取到的字段按名覆盖到 ``Config`` 类属性。

    - 未在 TOML 中出现的字段保持默认值；
    - ``DIMENSIONS`` 采用合并策略（TOML 表的 key 覆盖默认 key）；
    - 标量字段会经过安全的类型转换，非法值抛出 ``ValueError``；
    - 未识别的顶层 key 会被忽略。
    """

    normalized = _normalize_toml_data(data)

    # TOML key -> (Config 类属性名, 类型转换函数)
    scalar_fields: Dict[str, Any] = {
        "VERSION": ("VERSION", str),
        "DEBUG": ("DEBUG", _coerce_bool),
        "LOADER_PACKAGES_DIR": ("LOADER_PACKAGES_DIR", str),
        "DATABASE_DIR": ("DATABASE_DIR", str),
        "SERVER_ADDR": ("SERVER_ADDR", str),
        "SERVER_PORT": ("SERVER_PORT", int),
        "SERVER_PASSWORD": ("SERVER_PASSWORD", str),
        "MAX_PACKET_SIZE": ("MAX_PACKET_SIZE", int),
        "MAX_RECONNECT_ATTEMPTS": ("MAX_RECONNECT_ATTEMPTS", int),
        "RECONNECT_BASE_DELAY": ("RECONNECT_BASE_DELAY", float),
        "DEFAULT_LANG": ("DEFAULT_LANG", str),
    }

    for toml_key, (attr, caster) in scalar_fields.items():
        if toml_key not in normalized:
            continue
        try:
            setattr(cls, attr, caster(normalized[toml_key]))
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Invalid value for config key {toml_key!r}: "
                f"{normalized[toml_key]!r}"
            ) from exc

    # DIMENSIONS：table 合并
    dimensions = normalized.get("DIMENSIONS")
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
    DATABASE_DIR: str = _DEFAULT_DATABASE_DIR
    SERVER_ADDR: str = _DEFAULT_SERVER_ADDR
    SERVER_PORT: int = _DEFAULT_SERVER_PORT
    SERVER_PASSWORD: str = _DEFAULT_SERVER_PASSWORD
    MAX_PACKET_SIZE: int = _DEFAULT_MAX_PACKET_SIZE
    MAX_RECONNECT_ATTEMPTS: int = _DEFAULT_MAX_RECONNECT_ATTEMPTS
    RECONNECT_BASE_DELAY: float = _DEFAULT_RECONNECT_BASE_DELAY
    DEFAULT_LANG: str = _DEFAULT_LANG
    DIMENSIONS: Dict[str, str] = dict(_DEFAULT_DIMENSIONS)

    # 运行时诊断字段：实际使用的配置文件路径 & 是否成功加载到了非空 TOML
    CONFIG_FILE_USED: str = str(CONFIG_PATH)
    CONFIG_FILE_LOADED: bool = False


# ============================================================
# 模块加载时自动应用 TOML 覆盖 + 安全警告
# ============================================================

def _warn_if_default_password() -> None:
    """密码仍为默认公开值时打印警告。

    使用函数内延迟 import 避免循环导入。
    """
    if Config.SERVER_PASSWORD != _DEFAULT_SERVER_PASSWORD:
        return
    # 延迟导入，防止与 log.py 相互引用
    try:
        from .log import warning  # type: ignore
    except Exception:  # pragma: no cover - log 模块本身异常的兜底
        import warnings as _w
        _w.warn(
            "[Lapis] Using default SERVER_PASSWORD 'pw114514' is insecure; "
            "please set a custom password in config.toml or via Config.SERVER_PASSWORD.",
            stacklevel=2,
        )
        return
    warning(
        "Using default SERVER_PASSWORD 'pw114514' — this is publicly known and insecure.\n"
        "         Please edit config.toml and set a strong SERVER_PASSWORD, "
        "or assign Config.SERVER_PASSWORD before calling lapis.init()."
    )


def _initialize_from_file() -> None:
    toml_data = _load_toml_file(CONFIG_PATH)
    if toml_data:
        _apply_overrides(Config, toml_data)
        Config.CONFIG_FILE_LOADED = True
    # 即便文件不存在，也同步一下最终使用的路径，便于排查
    Config.CONFIG_FILE_USED = str(CONFIG_PATH)

    # 配置加载结束后再检查密码：用户可能在 TOML 中改了
    _warn_if_default_password()


_initialize_from_file()
