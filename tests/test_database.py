from __future__ import annotations

import asyncio
from pathlib import Path
import tempfile

import pytest

from lapis.ast import (
    VoidOperator,
    Eq,
    Lt,
    And,
    Or,
    Not,
    Xor,
)
from lapis.database import (
    Column,
    Database,
    Table,
    _warn_if_bulk_mutation,
    init_database,
    get_table,
    TableNotFoundError,
    InvalidASTError,
    DatabaseNotInitializedError,
)
from lapis.runtime import set_context, reset_context
from lapis.context import LapisContext


@pytest.fixture
def db_ctx():
    """把临时数据库目录写入 Config.DATABASE_DIR，并设置好 Context。"""
    with tempfile.TemporaryDirectory() as tmp:
        # 延迟导入，避免过早冻结 Config
        from lapis.config import Config
        old_dir = Config.DATABASE_DIR
        Config.DATABASE_DIR = tmp

        ctx = LapisContext(
            package_name="pytest_db",
            client=None,
            event_registry=None,
            database=None,
        )
        token = set_context(ctx)
        try:
            yield ctx
        finally:
            reset_context(token)
            Config.DATABASE_DIR = old_dir


def _make_users_table() -> Table:
    return Table(
        "users",
        Column("id", "INTEGER PRIMARY KEY AUTOINCREMENT"),
        Column("name", "TEXT NOT NULL"),
        Column("age", "INTEGER NOT NULL DEFAULT 0"),
    )


# ==================================================================
# AST 编译
# ==================================================================

def test_compile_void_is_placeholder():
    sql, params = Table._compile_ast(VoidOperator())
    assert sql == "1"
    assert params == []


def test_compile_eq_and_null_handling():
    sql, params = Table._compile_ast(Eq("name", "alice"))
    assert params == ["alice"]
    assert '"name" = ?' in sql

    sql, params = Table._compile_ast(Eq("name", None))
    assert '"name" IS NULL' in sql
    assert params == []

    sql, params = Table._compile_ast(Not(Eq("name", None)))
    assert '"name" IS NOT NULL' in sql or "IS NULL" in sql


def test_compile_and_or_empty():
    sql, params = Table._compile_ast(And())
    assert sql == "1"
    assert params == []

    sql, params = Table._compile_ast(Or())
    assert sql == "0"
    assert params == []


def test_compile_xor_symmetric():
    a = Lt("age", 10)
    b = Eq("name", "bob")
    sql, params = Table._compile_ast(Xor(a, b))
    assert "OR" in sql and "AND" in sql
    assert len(params) == 4  # a_params + b_params + a_params + b_params


def test_compile_invalid_raises():
    with pytest.raises(InvalidASTError):
        Table._compile_ast_node({"not a dict": 1})  # type: ignore[arg-type]
    with pytest.raises(InvalidASTError):
        Table._compile_ast_node({"op_type": "condition", "op_name": "???"})


# ==================================================================
# 基本 CRUD
# ==================================================================

def test_database_crud_sync(db_ctx):
    users = _make_users_table()
    db = init_database(users)

    # 确认数据库文件被创建到了临时目录
    assert Path(db.database_path).exists()

    id1 = users.add(name="alice", age=30)
    id2 = users.add(name="bob", age=10)
    _ = users.add(name="carol", age=15)
    assert id1 != id2

    all_rows = users.find()
    assert len(all_rows) == 3

    # LIMIT 参数绑定 — 必须真正生效，只返回 2 条
    limited = users.find(limit=2)
    assert len(limited) == 2

    # WHERE 条件查询
    rows = users.find(Eq("name", "alice"))
    assert len(rows) == 1 and rows[0]["age"] == 30

    # 组合 AND 查询
    rows = users.find(And(Lt("age", 20), Eq("name", "carol")))
    assert len(rows) == 1 and rows[0]["name"] == "carol"

    # 修改 — 带条件
    count = users.modify({"age": 31}, Eq("name", "alice"))
    assert count == 1
    rows = users.find(Eq("name", "alice"))
    assert rows[0]["age"] == 31

    # 删除 — 带条件
    count = users.delete(Eq("name", "bob"))
    assert count == 1
    assert len(users.find()) == 2

    # get_table 能找到表
    ref = get_table("users")
    assert ref is users

    with pytest.raises(TableNotFoundError):
        get_table("nope")

    db.close()


@pytest.mark.asyncio
async def test_database_crud_async(db_ctx):
    users = _make_users_table()
    db = init_database(users)

    id1 = await users.add_async(name="a", age=1)
    id2 = await users.add_async(name="b", age=2)
    id3 = await users.add_async(name="c", age=3)
    assert len({id1, id2, id3}) == 3

    rows = await users.find_async(limit=2)
    assert len(rows) == 2

    rows = await users.find_async(Eq("name", "b"))
    assert rows[0]["age"] == 2

    assert 1 == await users.modify_async({"age": 99}, Eq("name", "c"))
    rows = await users.find_async(Eq("name", "c"))
    assert rows[0]["age"] == 99

    assert 1 == await users.delete_async(Eq("name", "a"))
    assert len(await users.find_async()) == 2

    await db.close_async()


# ==================================================================
# 安全：无 WHERE 的 UPDATE/DELETE 确实修改全表
# ==================================================================

def test_bulk_mutation_without_where_is_effective(db_ctx):
    users = _make_users_table()
    db = init_database(users)
    try:
        users.add(name="x", age=1)
        users.add(name="y", age=2)
        users.add(name="z", age=3)

        # 无 WHERE 的 modify — 所有行 age 被置为 0
        count = users.modify({"age": 0})
        assert count == 3
        assert all(row["age"] == 0 for row in users.find())

        # 无 WHERE 的 delete — 全表清空
        count = users.delete()
        assert count == 3
        assert users.find() == []

        with pytest.raises(TableNotFoundError):
            get_table("nope")
    finally:
        db.close()


# ==================================================================
# Database 构造函数边界
# ==================================================================

def test_database_not_initialised(db_ctx):
    users = _make_users_table()
    db = Database(db_ctx.package_name)
    assert db._initialized is False

    with pytest.raises(DatabaseNotInitializedError):
        db.create_table(users)
