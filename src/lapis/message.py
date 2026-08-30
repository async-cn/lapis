from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any


def format_message(message: str | dict[str, Any]) -> dict[str, Any]:
    """将纯文本或文本组件 dict 打包为 send_message/actionbar 命令参数。

    * ``str`` → ``message_type="pure_text"`` 原样传递。
    * ``dict`` → ``message_type="text_component"`` 并以 JSON 字符串序列化内容，
      供 Java 端 ``GsonComponentSerializer.gson().deserialize`` 解析。
    """
    if isinstance(message, str):
        return {
            "message_type": "pure_text",
            "message_content": message,
        }
    return {
        "message_type": "text_component",
        "message_content": json.dumps(message, ensure_ascii=False),
    }


def format_title_component(value: str | dict[str, Any]) -> tuple[str, str]:
    """将文本内容转换为 Java 端 show_title 期望的 ``(title_type, title_content)`` 元组。

    :param value: 纯文本字符串，或 Minecraft 文本组件 dict。
    :return: ``(type_str, content_str)`` 可直接填入 ``title_type`` / ``subtitle_type``
             与 ``title`` / ``subtitle`` 字段。
    """
    if isinstance(value, str):
        return ("pure_text", value)
    return (
        "text_component",
        json.dumps(value, ensure_ascii=False),
    )
