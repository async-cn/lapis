# Lapis

Lapis 是一个面向 Minecraft 服务端的 Python 开发生态，让你可以用纯 Python 编写功能完整的插件 / 模组，支持注册事件、操作玩家、修改世界、执行指令、管理数据库等实用功能。

### TODO

> [!NOTE]
> - [ ] 修改 README，去AI味
> - [ ] 补充更多 TODO
> - [ ] 移除已废弃的 `nbt.NBT` 和 `utils.Vector`，以及其他已废弃的方法。
> - [ ] 实现 `Player.show_notice`
> - [ ] 支持实体配置文件（yaml, toml等）
> - [ ] 换一个更简单的示例程序

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

将构建得到的 `.jar` 放入服务端的 `plugins/` 目录，然后**启动一次服务端**以生成默认配置文件。按需修改插件配置中的监听地址、端口与密码：

```yaml
# lapis-plugin 配置示例
server:
  host: localhost
  port: 9331
  password: mypassword114514
```

### Lapis SDK

克隆本仓库并安装：

```bash
git clone https://github.com/async-cn/lapis.git
cd lapis
pip install -e .
```

安装成功后，查看并修改 `config.toml`，填写自定义密码等关键配置。

---

## 架构概览

Lapis 由两部分协同工作：

| 组件 | 说明 |
| --- | --- |
| **Lapis Plugin（Java 端）** | 安装在 Minecraft 服务端上的桥接插件，负责转发指令与事件。 |
| **Lapis SDK（本仓库，Python 端）** | 开发者使用的 Python SDK，提供玩家 / 世界 / 事件 / 数据库等 API，并内置 Loader 运行你的 Python 包。 |

两者通过 TCP 通信，支持 request/response 与 Java 端主动推送消息（事件等）。

---

## 快速开始

### 示例 Package

```
my_package/
├── package.json
└── __init__.py
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
import lapis
from lapis import event
from lapis.log import *
from lapis.ast import *

lapis.init("my_package")

@event.on("PlayerJoin")
async def hello(event):
    player = event.get_target_player()
    await player.send_message(
        f"欢迎加入本服务器！"
    )

@event.on(
    "BlockBreak", 
    Or(
        Eq("block.id", "minecraft:bamboo"),
        Eq("block.id", "minecraft:cobweb")
    ), 
    ["player.nbt.SelectedItem.id"]
)
async def on_blockbreak(event):
    player = event.get_target_player()
    block = event.get_block()
    tool = event.data.get("player.nbt.SelectedItem.id")
    is_bamboo = block.block_id == "minecraft:bamboo"
    best_tool = "剑" if is_bamboo else "剑或剪刀"
    block_name = "竹子" if is_bamboo else "蜘蛛网"
    if (
            (is_bamboo and not "sword" in tool)
            or (not is_bamboo and "sword" not in tool and tool != "minecraft:scissors")
    ):
        await player.send_message(
            f"你正在使用 {tool} 破坏 {block_name}；"
            f"温馨提示：该方块的最适破坏工具为{best_tool}。"
        )

async def main():
    info("Package启动成功")
    await lapis.start()
```

### 启动你的 Package

1. 先启动安装了 lapis-plugin 的 Minecraft 服务端，确认桥接端口已监听；
2. 使用 Lapis Loader 运行你的包：

```bash
python -m lapis run ./my_package
```

---

## Package 规范速览

| 要素                           | 说明 |
|------------------------------| --- |
| `lapis.init(name)`           | 在模块导入阶段调用，创建 Client、EventRegistry、Database 等上下文。 |
| `async def main()`           | 必须定义；Loader 会在同一事件循环中 `await` 它。 |
| `await lapis.start()`        | 在 `main()` 内调用：建立 Java 连接、批量注册事件监听器并保持常驻。 |
| `@event.on(event_type, ...)` | 装饰器：注册事件处理器；支持过滤条件、订阅字段与事件代理。 |
| `init_database(*tables)`     | 为当前包创建独立 SQLite 数据库。 |

---

## SDK 核心能力一览

- **通信层**：异步 TCP + 自定义 JSON 协议，与 Java 端可靠地命令 / 响应配对。
- **玩家 API**：发送消息、请求输入、给予 / 扣除物品、自定义 KV 数据、经济（eco）操作等。
- **世界 / 方块**：在任意维度设置方块，支持 BlockState 与 NBT。
- **事件系统**：基于 `@on` 装饰器注册，支持服务端过滤（`EventFilter` AST）与字段订阅（`EventSubscription`），可选代理模式拦截事件。
- **数据库**：基于 SQLite + aiosqlite 的同步 / 异步 ORM 风格 API，使用 AST 表达式表达查询条件。
- **内置 Loader**：`python -m lapis run <path>` 一键导入并运行 Package，管理事件循环生命周期。

> 详细的接口文档与示例将在后续独立文档中补充，本仓库只提供基础介绍与入门示例。

---

## 配置

默认配置见 [src/lapis/config.py](src/lapis/config.py)，常用字段：

| 字段 | 默认值 | 说明 |
| --- | --- | --- |
| `SERVER_ADDR` | `localhost` | lapis-plugin 所在地址 |
| `SERVER_PORT` | `9331` | lapis-plugin 监听端口 |
| `SERVER_PASSWORD` | `pw114514` | 与 Java 端握手的密码 |
| `DEBUG` | `False` | 是否开启 debug 级日志 |

在 `lapis.init(...)` 之前修改 `Config` 对应字段即可生效。

---

## 目录结构

```
lapis/
├── src/
│   └── lapis/              # SDK 源码
│       ├── __init__.py     # 对外公开 API & init()/start()
│       ├── __main__.py     # python -m lapis CLI（Loader）
│       ├── client.py       # TCP 客户端 & 协议
│       ├── event.py        # 事件注册 / 分发 / 装饰器
│       ├── runtime.py      # 运行时与 ContextVar 上下文
│       ├── context.py      # LapisContext 数据类
│       ├── server_message.py  # Java 主动消息分发
│       ├── commands.py     # 执行原版指令
│       ├── player.py       # 玩家对象 API
│       ├── world.py / block.py / entity.py / item.py / nbt.py / pos.py
│       ├── database.py     # SQLite 同步 / 异步数据库封装
│       ├── ast.py          # 过滤器 / 查询用 AST 运算符
│       ├── config.py       # 默认配置
│       ├── log.py          # 带色彩的日志
│       ├── message.py      # 消息组件工具
│       └── utils.py
├── standards/              # 协议 JSON Schema
├── pyproject.toml
├── LICENSE
└── README.md
```

---

## 协议

`standards/` 目录下以 JSON Schema 形式定义了 handshake、事件订阅、事件数据、响应等报文结构，便于跨语言实现或二次开发 Bridge。

---

## License

本项目以 **MIT License** 开源，详见 [LICENSE](LICENSE)。

> Copyright (c) 2026 Oasis Studio
