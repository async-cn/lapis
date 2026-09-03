<div align="center">
    <img src="src/lapis/assets/images/lapis-title.png" height="84" alt="title"><br/><br/>
    <p>面向 Python 的 Minecraft 开发生态</p>
    <p>
        <a href="README.md">简体中文</a> |
        <a href="README_EN.md">English</a> |
        <a href="README_JP.md">日本語</a>
    </p>
    <img alt="License MIT" src="https://img.shields.io/badge/license-MIT-blue.svg">
    <img alt="GitHub Release" src="https://img.shields.io/github/v/release/async-cn/lapis?color=blue">
    <img alt="Last Commit" src="https://img.shields.io/github/last-commit/async-cn/lapis"><br/>
    <img alt="Contributors" src="https://img.shields.io/github/contributors/async-cn/lapis?color=violet">
    <img alt="Stars" src="https://img.shields.io/github/stars/async-cn/lapis?style=flat&logo=github&label=Stars&color=yellow">
    <img alt="GitHub Issues" src="https://img.shields.io/github/issues/async-cn/lapis?color=brightgreen">
</div>

---

## 安装

### 环境要求

| 环境                | 要求                                                       |
|-------------------|----------------------------------------------------------|
| **Python**        | `>= 3.9`                                                 |
| **Minecraft 服务端** | Paper 等支持安装插件的 Minecraft 服务端                             |
| **前置插件**          | [lapis-plugin](https://github.com/async-cn/lapis-plugin) |

### 前置桥接插件

下载并安装迁至插件 [lapis-plugin](https://github.com/async-cn/lapis-plugin)

将构建得到的 `.jar` 放入服务端的 `plugins/` 目录，然后**启动一次服务端**生成默认配置文件。按需修改插件配置中的监听地址、端口与密码：

### Lapis SDK

以下安装方式二选一：

#### 从源码安装（推荐）

```bash
git clone https://github.com/async-cn/lapis.git
cd lapis
pip install -e .
```

#### 从whl文件安装

从 [Releases](https://github.com/async-cn/lapis/releases) 页面下载whl文件，然后执行安装命令：

（此处以v0.1.0为例）

```bash
pip install lapis-0.1.0-py3-none-any.whl
```

> [!NOTE]
> 安装成功后，查看并修改 `config.toml`，填写自定义密码等关键配置。

---

## 快速开始

### 示例 Package

以下是一个示例包，包含进服欢迎、阻止TNT放置、挖掘工具提示等简单的功能。

包结构：

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

init("my_package", "MyPackage")

on_blockbreak.register()
on_blockplace.register()

@on("PlayerJoin")
async def hello(event):
    player = event.target_player
    await player.send_message(
        f"§a欢迎加入本服务器！"
    )

async def main():
    info("MyPackage启动成功")
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
    asyncio.create_task(event.target_player.send_message(
        "§c本服务器禁止放置tnt，已取消放置！"
    ))
    remind(f"玩家 {event.data.get("player.name")} 尝试放置TNT！")
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
    auto_register=False
)
async def on_blockbreak(event: Event):
    player = event.player
    block = event.block
    tool = player.selected_item
    tool_name = get_item_name(tool.get("id")) if tool else "手"
    is_bamboo:bool = block.block_id == "minecraft:bamboo"
    best_tool = "剑" if is_bamboo else "剑或剪刀"
    if (
            (is_bamboo and "sword" not in tool_name)
            or (not is_bamboo and "sword" not in tool_name and tool_name != "minecraft:shears")
    ):
        await player.send_message(
            f"你正在使用 §e{tool_name}§r 破坏 §e{get_item_name(block.block_id)}§r；\n"
            f"温馨提示：该方块的最适破坏工具为§e{best_tool}§r。"
        )
```


### 启动你的 Package

1. 启动安装了 lapis-plugin 的 Minecraft 服务端；
2. 使用 Lapis Loader 运行你的包：（工作目录需在my_package的父目录）

```bash
python -m lapis run my_package
```

### FastShop

> [!NOTE]
> 此示例包已不适用于最新的 Lapis SDK

FastShop 是一款仿制 QuickShop 插件的商店示例包，你可以点击[此处](https://github.com/async-cn/fastshop)前往获取。仅用于功能演示，请勿用于生产环境实装或倒卖收费等其他用途。

---

## 架构概览

Lapis 由两部分协同工作：

| 组件 | 说明 |
| --- | --- |
| **Lapis Plugin（Java 端）** | 安装在 Minecraft 服务端上的桥接插件，负责转发指令与事件。 |
| **Lapis SDK（本仓库，Python 端）** | 开发者使用的 Python SDK，提供玩家 / 世界 / 事件 / 数据库等 API，并内置 Loader 运行你的 Python 包。 |

两者通过 TCP 通信，支持 request/response 与 Java 端主动推送消息（事件等）。

---

## Package 规范速览

| 要素                         | 说明                                                       |
|------------------------------|------------------------------------------------------------|
| `init(name)`                 | 在模块导入阶段调用，创建上下文。                           |
| `async def main()`           | 必须定义，Loader 会在同一事件循环中调用。                  |
| `await start()`              | 在 `main()` 内调用。                                       |
| `@event.on(event_type, ...)` | 装饰器：注册事件处理器；支持过滤条件、订阅字段与事件代理。 |
| `init_database(*tables)`     | 为当前包创建独立 SQLite 数据库。                           |

---

## SDK 核心能力一览

- **通信层**：已高度封装，无需手动访问。异步 TCP + 自定义 JSON 协议，与 Java 端可靠地命令 / 响应配对。
- **玩家 API**：发送消息、请求输入、给予 / 扣除物品、自定义 KV 数据、经济（eco）操作等。
- **世界 / 方块**：在任意维度设置方块，支持 BlockState 与 NBT。
- **事件系统**：基于 `@on` 装饰器注册，支持服务端过滤（`EventFilter` AST）与字段订阅（`EventSubscription`），可选代理模式拦截事件。
- **数据库**：基于 SQLite + aiosqlite 的同步 / 异步 ORM 风格 API，使用 AST 表达式表达查询条件。
- **内置 Loader**：`python -m lapis run <path>` 一键导入并运行 Package，管理事件循环生命周期。

- 详细的接口文档与示例将在后续独立文档中补充，本仓库只提供基础介绍与入门示例。

---

## 帮助与支持

> [!IMPORTANT]
> 加入 Lapis 开发者社区 QQ 群 [806492643](https://qm.qq.com/q/Uu4mGaTaee) 或论坛 [Lapis World](https://www.lapis.world)

---

## License

本项目以 **MIT License** 开源，详见 [LICENSE](LICENSE)。

> Copyright (c) 2026 Oasis Studio

> [!NOTE]
> 
> 我们计划未来开发 Fabric/Forge 移植 Mod 版本。