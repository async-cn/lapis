from typing import Any

class NBT:
    data: dict[str, Any]

    def __init__(self, **data: dict[str, Any]):
        self.data=data

    def raw(self):
        return self.data

    def getvalue(self, key: str) -> Any:
        return self.data[key]

    def setvalue(self, key: str, value: Any):
        if key in [
            "data",
            "__init__",
            "raw",
            "getvalue",
            "setvalue"
        ]:
            raise Exception(f"NBT Key cannot be {key}")

        self.data[key] = value