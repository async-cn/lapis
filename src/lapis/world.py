from .config import Config

class WORLDS:
    overworld: str
    the_nether: str
    the_end: str

for dimension, world_name in Config.DIMENSIONS.items():
    setattr(WORLDS, dimension, world_name)