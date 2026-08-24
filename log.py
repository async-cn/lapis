import os
from datetime import datetime
from .config import Config

COLORS = {
    "none": "\033[0m",
    "info": "\033[92m",
    "warning": "\033[93m",
    "error": "\033[91m",
    "remind": "\033[94m",
    "debug": "\033[95m"
}
RESET = COLORS["none"]

# 日志目录
LOG_DIR = "logs"

def log(msg, level:str="INFO", write:bool = True) -> None:
    """输出带颜色的日志到控制台，同时写入日志文件（不含颜色代码）。"""
    print(f"{RESET}[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}][{COLORS[level.lower()]}{level.upper()}{RESET}] {str(msg)}{RESET}")

def info(msg:str) -> None: log(msg, "info")
def warning(msg:str) -> None: log(msg, "warning")
def error(msg:str) -> None: log(msg, "error")
def remind(msg:str) -> None: log(msg, "remind")
def debug(msg:str) -> None:
    if Config.DEBUG: log(msg, "debug")
