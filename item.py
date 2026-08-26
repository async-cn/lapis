from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .nbt import NBT

class Item:
    item_id: str
    nbt: NBT
    def __init__(self, item_id: str, nbt: NBT):
        self.item_id = item_id
        self.nbt = nbt
    def raw(self):
        return {
            "item_id": self.item_id,
            "nbt": self.nbt.raw()
        }

class ItemStack(Item):
    count: int
    def __init__(self, item_id: str, nbt: NBT, count: int):
        super().__init__(item_id, nbt)
        self.count = count
    def raw(self):
        return {
            **super().raw(),
            "count": self.count
        }