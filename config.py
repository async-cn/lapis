from dataclasses import dataclass

@dataclass
class Config:
    VERSION = "0.1.0"
    DEBUG: bool = False
    LOADER_PACKAGES_DIR: str = "../packages"
    SERVER_ADDR: str = "localhost"
    SERVER_PORT: int = 9331
    SERVER_PASSWORD: str = "pw114514"
    MAX_PACKET_SIZE: int = 0xffffff # 16 * 1024 * 1024

    DIMENSIONS = {
        "overworld": "world",
        "the_nether": "world_nether",
        "the_end": "world_end"
    }