from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

def format_message(message:str|dict[str, Any]) -> dict[str, Any]:
    return {
        "message_type": "pure_text" if isinstance(message, str) else "text_component",
        "message_content": message
    }