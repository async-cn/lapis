from dataclasses import dataclass

@dataclass
class Config:
    VERSION = "0.1.0"
    DEBUG: bool = False
    LOADER_PACKAGES_DIR: str = "../packages"
    SERVER_ADDR: str = "localhost"
    SERVER_PORT: int = 9331