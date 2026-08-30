from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

# ============================================================
# 本地化名称查找（懒加载）
# ============================================================

_LANG_DIR = Path(__file__).resolve().parent / "assets" / "lang"
"""语言资源目录：``assets/lang/``。"""

_categories: Optional[frozenset[str]] = None
"""有效分类集合；首次调用 :func:`get_display_name` 时才加载 categories.json。"""

_lang_cache: dict[tuple[str, str], dict[str, str]] = {}
"""``(语言, 分类) -> 名称映射`` 缓存；对应的 JSON 文件仅在首次访问时加载。"""


def _load_categories() -> frozenset[str]:
    """懒加载 ``categories.json``，返回有效分类集合。"""
    global _categories
    if _categories is None:
        path = _LANG_DIR / "categories.json"
        _categories = frozenset(json.loads(path.read_text(encoding="utf-8")))
    return _categories


def _load_category(lang: str, category: str) -> dict[str, str]:
    """懒加载 ``assets/lang/{lang}/{category}.json``，命中缓存则直接返回。

    文件不存在（语言或分类缺失）时缓存为空字典，避免反复探测磁盘。
    """
    key = (lang, category)
    if key not in _lang_cache:
        path = _LANG_DIR / lang / f"{category}.json"
        if path.is_file():
            _lang_cache[key] = json.loads(path.read_text(encoding="utf-8"))
        else:
            _lang_cache[key] = {}
    return _lang_cache[key]


def get_display_name(namespace_id: str, *categories: str, lang: Optional[str] = None) -> str:
    """根据命名空间ID和指定分类获取实体的本地化显示名称。

    参数说明：
    - namespace_id: 实体的命名空间ID，支持带或不带 ``"minecraft:"`` 前缀，
      方法内部会自动检测并去除前缀；
    - categories: 指定查找范围的分类列表（按提供顺序依次查找，返回第一个
      匹配项），必须为 ``assets/lang/categories.json`` 中定义的有效分类，
      且至少提供一个分类；
    - lang: 语言代码（如 ``"zh_cn"`` / ``"en_us"``）；为 ``None`` 时使用
      :class:`lapis.config.Config` 中的默认语言（``DEFAULT_LANG``）。

    :raises ValueError: 未提供任何分类，或存在无效分类。

    :returns: 查找到的本地化显示名称；若所有指定分类中均未找到对应名称，
              则返回已去除 ``"minecraft:"`` 前缀的原始 ``namespace_id``。
    """
    if not categories:
        raise ValueError(
            "get_display_name() requires at least one category, got none"
        )

    # 1. 处理 namespace_id：自动检测并移除 "minecraft:" 前缀
    if namespace_id.startswith("minecraft:"):
        namespace_id = namespace_id[len("minecraft:"):]

    # 2. 验证 categories：必须全部为 categories.json 中定义的有效分类
    valid_categories = _load_categories()
    invalid = [c for c in categories if c not in valid_categories]
    if invalid:
        raise ValueError(
            f"Invalid category/categories: {invalid!r}; "
            f"valid categories are {sorted(valid_categories)!r}"
        )

    # 3. 语言处理：lang 为 None 时回退到 Config 中的默认语言
    if lang is None:
        from .config import Config  # 函数内导入，避免模块级循环导入
        lang = Config.DEFAULT_LANG

    # 4. 按提供顺序依次在 assets/lang/{lang}/{category}.json 中查找
    for category in categories:
        name = _load_category(lang, category).get(namespace_id)
        if name is not None:
            return name

    # 5. 全部未命中：回退为去除前缀后的原始 namespace_id
    return namespace_id

def get_item_name(namespace_id:str, lang: Optional[str] = None) -> str:
    return get_display_name(namespace_id, "items", "blocks", lang=lang)