from typing import Any

class NBT:
    data: dict[str, Any]

    def __init__(self, data: dict[str, Any] = None):
        if data is None:
            data = {}
        self.data=data

    def raw(self):
        return self.data