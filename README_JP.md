<div align="center" style="margin-top: 32px">
    <img src="src/lapis/assets/images/lapis-title.png" height="84" alt="title" style="margin-top: 16px">
    <p>Minecraft サーバー向けの Python 開発エコシステム</p>
    <p>
        <a href="README.md">简体中文</a> |
        <a href="README_EN.md">English</a> |
        <a href="README_JP.md">日本語</a>
    </p>
    <img alt="License MIT" src="https://img.shields.io/badge/license-MIT-blue.svg">
    <img alt="GitHub Release" src="https://img.shields.io/github/v/release/async-cn/lapis?color=green">
    <img alt="Last Commit" src="https://img.shields.io/github/last-commit/async-cn/lapis"><br/>
    <img alt="Contributors" src="https://img.shields.io/github/contributors/async-cn/lapis?color=violet">
    <img alt="Stars" src="https://img.shields.io/github/stars/async-cn/lapis?style=flat&logo=github&label=Stars&color=yellow">
    <img alt="GitHub Issues" src="https://img.shields.io/github/issues/async-cn/lapis?color=deepskyblue">

</div>

---

## インストール

### 環境要件

| 環境                 | 要件                                                       |
| ------------------ | -------------------------------------------------------- |
| **Python**         | `>= 3.9`                                                 |
| **Minecraft サーバー** | Paper などプラグイン導入に対応した Minecraft サーバー                      |
| **前提プラグイン**        | [lapis-plugin](https://github.com/async-cn/lapis-plugin) |

### 前提ブリッジプラグイン

ブリッジプラグイン [lapis-plugin](https://github.com/async-cn/lapis-plugin) をダウンロードしてインストールしてください。

ビルドして得られた `.jar` をサーバーの `plugins/` ディレクトリに配置し、**一度サーバーを起動**してデフォルト設定ファイルを生成します。プラグイン設定内の待受アドレス、ポート、パスワードを必要に応じて編集してください：

### Lapis SDK

以下のいずれかの方法でインストールしてください：

#### whl ファイルからインストール

[Releases](https://github.com/async-cn/lapis/releases) ページから whl ファイルをダウンロードし、インストールコマンドを実行します：

（v0.1.0 を例として記載）

```bash
pip install lapis-0.1.0-py3-none-any.whl
```

#### ソースコードからインストール

```bash
git clone https://github.com/async-cn/lapis.git
cd lapis
pip install -e .
```

インストール成功後、`config.toml` を確認・編集し、カスタムパスワードなどの重要な設定を記入してください。

---

## クイックスタート

### サンプル Package

以下は、サーバー入場時の挨拶、TNT 設置の阻止、採掘ツールのリマインダーなどの簡単な機能を含むサンプルパッケージです。

パッケージ構成：

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
        f"§aサーバーへようこそ！"
    )

async def main():
    info("MyPackageが起動しました")
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
        "§cこのサーバーではTNTの設置は禁止されています。設置をキャンセルしました！"
    ))
    remind(f"プレイヤー {event.data.get("player.name")} がTNTを設置しようとしました！")
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
    best_tool = "剣" if is_bamboo else "剣またはハサミ"
    if (
            (is_bamboo and "sword" not in tool)
            or (not is_bamboo and "sword" not in tool and tool != "minecraft:shears")
    ):
        await player.send_message(
            f"§e{get_item_name(tool)}§r で §e{get_item_name(block.block_id)}§r を壊しています；\n"
            f"お知らせ：このブロックを最も効率よく壊せるツールは§e{best_tool}§rです。"
        )
```

### Package の起動

1. lapis-plugin を導入した Minecraft サーバーを起動します；
2. Lapis Loader でパッケージを実行します：（作業ディレクトリは my_package の親ディレクトリである必要があります）

```bash
python -m lapis run my_package
```

### FastShop

FastShop は QuickShop プラグインを模したサンプルショップパッケージです。[こちら](https://github.com/async-cn/fastshop)から入手できます。機能デモ専用であり、本番環境での実装や転売・有料化などの商業的用途には使用しないでください。

---

## アーキテクチャ概要

Lapis は2つのコンポーネントが連携して動作します：

| コンポーネント                        | 説明                                                                                        |
| ------------------------------ | ----------------------------------------------------------------------------------------- |
| **Lapis Plugin（Java 側）**       | Minecraft サーバーに導入するブリッジプラグイン。コマンドとイベントの転送を担います。                                           |
| **Lapis SDK（本リポジトリ、Python 側）** | 開発者が使用する Python SDK。プレイヤー/ワールド/イベント/データベースなどの API を提供し、Python パッケージを実行する Loader を内蔵しています。 |

両者は TCP で通信し、request/response パターンと Java 側からの能動的なメッセージプッシュ（イベントなど）をサポートしています。

---

## Package 仕様早見表

| 要素                           | 説明                                            |
| ---------------------------- | --------------------------------------------- |
| `init(name)`                 | モジュールインポート時に呼び出し、コンテキストを作成します。                |
| `async def main()`           | 必須定義。Loader が同一のイベントループ内で呼び出します。              |
| `await start()`              | `main()` 内で呼び出します。                            |
| `@event.on(event_type, ...)` | デコレータ：イベントハンドラを登録。フィルタ条件、フィールド購読、イベントプロキシに対応。 |
| `init_database(*tables)`     | 現在のパッケージ用に独立した SQLite データベースを作成します。           |

---

## SDK 主要機能一覧

- **通信層**：高度にカプセル化されており、手動で操作する必要はありません。非同期 TCP + カスタム JSON プロトコルにより、Java 側とのコマンド/レスポンスのペアリングを確実に行います。

- **プレイヤー API**：メッセージ送信、入力要求、アイテムの付与/削除、カスタム KV データ、経済（eco）操作など。

- **ワールド / ブロック**：任意のディメンションでブロックを設置可能。BlockState と NBT に対応。

- **イベントシステム**：`@on` デコレータで登録し、サーバー側フィルタ（`EventFilter` AST）とフィールド購読（`EventSubscription`）に対応。オプションのプロキシモードでイベントをインターセプト可能。

- **データベース**：SQLite + aiosqlite ベースの同期/非同期 ORM 風 API。AST 式でクエリ条件を表現します。

- **内蔵 Loader**：`python -m lapis run <path>` で Package をワンクリックでインポート・実行し、イベントループのライフサイクルを管理します。

- 詳細な API ドキュメントとサンプルは今後別ドキュメントで補足されます。本リポジトリでは基本的な紹介と導入例のみを提供しています。

---

## ライセンス

本プロジェクトは **MIT License** に基づいてオープンソース化されています。詳細は [LICENSE](LICENSE) をご覧ください。

> Copyright (c) 2026 Oasis Studio
