# Lapis

[简体中文](README.md) | [English](README_EN.md) | [日本語](README_JP.md)

Lapis is a Python development ecosystem for Minecraft servers, allowing you to write fully functional plugins/mods in pure Python. It supports event registration, player manipulation, world modification, command execution, database management, and many other practical features.

---

## Installation

### Requirements

| Environment             | Requirements                                                      |
| ----------------------- | ----------------------------------------------------------------- |
| **Python**              | `>= 3.9`                                                          |
| **Minecraft Server**    | Minecraft servers that support plugin installation, such as Paper |
| **Prerequisite Plugin** | [lapis-plugin](https://github.com/async-cn/lapis-plugin)          |

### Prerequisite Bridge Plugin

Download and install the bridge plugin [lapis-plugin](https://github.com/async-cn/lapis-plugin)

Place the built `.jar` file into the server's `plugins/` directory, then **start the server once** to generate the default configuration files. Modify the listening address, port, and password in the plugin configuration as needed:

### Lapis SDK

Choose one of the following installation methods:

#### Install from a whl file

Download the whl file from the [Releases](https://github.com/async-cn/lapis/releases) page, then run the installation command:

(Using v0.1.0 as an example)

```bash
pip install lapis-0.1.0-py3-none-any.whl
```

#### Install from source

```bash
git clone https://github.com/async-cn/lapis.git
cd lapis
pip install -e .
```

After successful installation, review and modify `config.toml`, filling in critical configurations such as your custom password.

---

## Quick Start

### Example Package

Below is an example package that includes simple features such as a welcome message on join, preventing TNT placement, and mining tool reminders.

Package structure:

```
my_package/
├── package.json
├── __init__.py
├── tnt_blocker.py
└── tool_reminder.py
```

#### package.json

```json
{
    "package_name": "my_package",
    "package_display_name": "MyPackage",
    "version": "11.45.14",
    "dependencies": {}
}
```

#### \_\_init\_\_.py

```python
from lapis import init, start
from lapis.event import on
from lapis.log import *

from .tool_reminder import on_blockbreak
from .tnt_blocker import on_blockplace

init("my_package")

on_blockbreak.register()
on_blockplace.register()

@on("PlayerJoin")
async def hello(event):
    player = event.get_target_player()
    await player.send_message(
        f"§aWelcome to this server!"
    )

async def main():
    info("MyPackage started successfully")
    await start()
```

#### tnt_blocker.py

```python
from lapis.event import on, Event
from lapis.ast import *
from lapis.log import remind

import asyncio

@on(
    "BlockPlace",
    Eq("block.id", "minecraft:tnt"),
    ["player.uuid", "player.name"],
    proxy=True,
    auto_register=False
)
async def on_blockplace(event: Event):
    asyncio.create_task(event.get_target_player().send_message(
        "§cTNT placement is prohibited on this server. Placement cancelled!"
    ))
    remind(f"Player {event.data.get("player.name")} attempted to place TNT!")
    return False
```

#### tool_reminder.py

```python
from lapis.event import on, Event
from lapis.ast import *
from lapis.lang import get_item_name

@on(
    "BlockBreak",
    Or(
        Eq("block.id", "minecraft:bamboo"),
        Eq("block.id", "minecraft:cobweb")
    ),
    [
        "player",
        "block"
    ],
    auto_register=False
)
async def on_blockbreak(event: Event):
    player = event.get_player()
    block = event.get_block()
    tool = player.selected_item.get("id")
    is_bamboo:bool = block.block_id == "minecraft:bamboo"
    best_tool = "Sword" if is_bamboo else "Sword or Shears"
    if (
            (is_bamboo and "sword" not in tool)
            or (not is_bamboo and "sword" not in tool and tool != "minecraft:shears")
    ):
        await player.send_message(
            f"You are using §e{get_item_name(tool)}§r to break §e{get_item_name(block.block_id)}§r;\n"
            f"Tip: The optimal tool for this block is §e{best_tool}§r."
        )
```

### Running Your Package

1. Start the Minecraft server with lapis-plugin installed;
2. Use the Lapis Loader to run your package: (the working directory must be the parent directory of my_package)

```bash
python -m lapis run my_package
```

### FastShop

FastShop is an example shop package modeled after the QuickShop plugin. You can obtain it by clicking [here](https://github.com/async-cn/fastshop). It is for demonstration purposes only — do not use it in production environments, for resale, charging fees, or any other commercial purposes.

---

## Architecture Overview

Lapis consists of two components working in tandem:

| Component                                    | Description                                                                                                                    |
| -------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| **Lapis Plugin (Java side)**                 | A bridge plugin installed on the Minecraft server, responsible for forwarding commands and events.                             |
| **Lapis SDK (this repository, Python side)** | The Python SDK for developers, providing Player/World/Event/Database APIs, with a built-in Loader to run your Python packages. |

Both communicate via TCP, supporting request/response patterns and Java-side active message pushes (events, etc.).

---

## Package Specification Quick Reference

| Element                      | Description                                                                                     |
| ---------------------------- | ----------------------------------------------------------------------------------------------- |
| `init(name)`                 | Called during module import to create the context.                                              |
| `async def main()`           | Must be defined; the Loader will call it within the same event loop.                            |
| `await start()`              | Called inside `main()`.                                                                         |
| `@event.on(event_type, ...)` | Decorator: registers event handlers; supports filters, field subscriptions, and event proxying. |
| `init_database(*tables)`     | Creates an independent SQLite database for the current package.                                 |

---

## SDK Core Capabilities

- **Communication Layer**: Highly encapsulated, no manual access required. Asynchronous TCP with a custom JSON protocol for reliable command/response pairing with the Java side.

- **Player API**: Send messages, request input, give/remove items, custom KV data, economy (eco) operations, and more.

- **World / Blocks**: Set blocks in any dimension, with BlockState and NBT support.

- **Event System**: Registered via the `@on` decorator, supporting server-side filtering (`EventFilter` AST) and field subscriptions (`EventSubscription`), with optional proxy mode for intercepting events.

- **Database**: SQLite + aiosqlite based sync/async ORM-style API, using AST expressions to express query conditions.

- **Built-in Loader**: `python -m lapis run <path>` one-click import and run a Package, managing the event loop lifecycle.

- Detailed API documentation and examples will be supplemented in separate documentation later; this repository only provides a basic introduction and getting-started examples.

---

## License

This project is open-sourced under the **MIT License**, see [LICENSE](LICENSE) for details.

> Copyright (c) 2026 Oasis Studio
