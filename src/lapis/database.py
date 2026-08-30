from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterable
from pathlib import Path
import sqlite3

import aiosqlite

from .runtime import get_context
from .ast import VoidOperator
from .config import Config
from .log import warning as _log_warning

if TYPE_CHECKING:
    from .ast import ASTOperator
    from sqlite3 import Connection as SQLConnection
    from aiosqlite import Connection as AsyncSQLConnection


# ============================================================
# Exceptions
# ============================================================

class DatabaseError(Exception):
    """Lapis Database 基础异常。"""


class DatabaseNotInitializedError(DatabaseError):
    """数据库尚未初始化。"""

class TableError(DatabaseError):
    """Table 基础异常。"""

class TableNotFoundError(TableError):
    """指定的 Table 不存在。"""


class InvalidASTError(DatabaseError):
    """AST 无法转换为 SQL。"""


# ============================================================
# Utilities
# ============================================================

def _quote_identifier(identifier: str) -> str:
    """
    安全引用 SQLite identifier。

    例如：

        users
        -> "users"

    identifier 不能使用 SQLite 的 ? 参数绑定，
    因此需要手动进行转义。
    """

    if not isinstance(identifier, str):
        raise TypeError("identifier must be str")

    if not identifier:
        raise ValueError("identifier cannot be empty")

    return '"' + identifier.replace(
        '"',
        '""'
    ) + '"'


def _rows_to_dict(
    rows: Iterable[sqlite3.Row],
) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def _warn_if_bulk_mutation(
    operation: str,
    table_name: str,
    data_filter: ASTOperator,
) -> None:
    """对于无条件的 UPDATE / DELETE 发出安全警告。"""
    if isinstance(data_filter, VoidOperator):
        _log_warning(
            f"Database.{operation} called on table {table_name!r} "
            "without a WHERE clause — this will affect EVERY row in the table."
        )


# ============================================================
# Database
# ============================================================

class Database:

    database_name: str
    database_path: str

    tables: dict[str, Table]

    connection: SQLConnection | None
    async_connection: AsyncSQLConnection | None

    def __init__(
        self,
        database_name: str,
    ):
        self.database_name = database_name
        self.tables = {}

        self.connection = None
        self.async_connection = None

        self._initialized = False

    # --------------------------------------------------------
    # Initialization
    # --------------------------------------------------------

    def init(self):
        """
        初始化数据库。

        这里只建立同步 SQLite connection。

        async_connection 不在这里初始化，
        而是在第一次异步操作时懒加载。
        """

        package_name = (
            get_context().package_name
        )

        # 数据库目录。
        #
        # 可通过 Config.DATABASE_DIR 自定义。
        # 支持相对路径（相对于当前工作目录）或绝对路径。
        database_dir = (
            Path(Config.DATABASE_DIR)
            if Path(Config.DATABASE_DIR).is_absolute()
            else Path.cwd() / Config.DATABASE_DIR
        )

        database_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        # 按要求：
        #
        # <package_name>.sqlite
        #
        self.database_path = str(
            database_dir
            / f"{package_name}.sqlite"
        )

        # 同步连接
        self.connection = sqlite3.connect(
            self.database_path,
            check_same_thread=False,
        )

        self.connection.row_factory = (
            sqlite3.Row
        )

        self._initialized = True

        # 创建已经注册的表
        for table in self.tables.values():
            self.create_table(table)

        return self

    # --------------------------------------------------------
    # Async connection
    # --------------------------------------------------------

    async def ensure_async_connection(
        self,
    ) -> AsyncSQLConnection:

        if not self._initialized:
            raise DatabaseNotInitializedError("Database has not been initialized")

        if self.async_connection is None:
            self.async_connection = await aiosqlite.connect(self.database_path)
            self.async_connection.row_factory = aiosqlite.Row

        return self.async_connection

    # --------------------------------------------------------
    # Execute
    # --------------------------------------------------------

    def execute(
        self,
        sql_command: str,
        parameters: Iterable[Any] = (),
        commit: bool = False,
    ):
        """
        同步执行 SQL。

        这是底层 API。
        一般情况下推荐使用 Table API。
        """

        if not self._initialized:
            raise DatabaseNotInitializedError("Database has not been initialized")

        cursor = self.connection.execute(
            sql_command,
            tuple(parameters),
        )

        if commit:
            self.connection.commit()

        return cursor

    async def async_execute(
        self,
        sql_command: str,
        parameters: Iterable[Any] = (),
        commit: bool = False,
    ):
        """
        异步执行 SQL。

        如果 async_connection 尚未建立，
        在这里进行 lazy initialization。
        """

        connection = await self.ensure_async_connection()

        cursor = await connection.execute(
            sql_command,
            tuple(parameters),
        )

        if commit:
            await connection.commit()

        return cursor

    # --------------------------------------------------------
    # Create table
    # --------------------------------------------------------

    def create_table(
        self,
        table: Table,
    ):
        """
        同步创建 Table。
        """

        if not self._initialized:
            raise DatabaseNotInitializedError(
                "Database has not been initialized"
            )
        if not isinstance(table, Table):
            raise TypeError(
                "table must be a Table"
            )
        if not table.columns:
            raise ValueError(
                f"Table {table.table_name!r} "
                "must have at least one column"
            )

        column_sql = ", ".join(
            (
                f"{_quote_identifier(column.column_name)} "
                f"{column.column_type}"
            )
            for column in table.columns
        )
        sql = (
            "CREATE TABLE IF NOT EXISTS "
            f"{_quote_identifier(table.table_name)} "
            f"({column_sql})"
        )
        self.execute(
            sql,
            commit=True,
        )

        table.database = self
        self.tables[table.table_name] = table

        return table

    async def create_table_async(
        self,
        table: Table,
    ):
        """
        异步创建 Table。
        """

        if not isinstance(table, Table):
            raise TypeError(
                "table must be a Table"
            )

        if not table.columns:
            raise ValueError(
                f"Table {table.table_name!r} "
                "must have at least one column"
            )

        column_sql = ", ".join(
            (
                f"{_quote_identifier(column.column_name)} "
                f"{column.column_type}"
            )
            for column in table.columns
        )

        sql = (
            "CREATE TABLE IF NOT EXISTS "
            f"{_quote_identifier(table.table_name)} "
            f"({column_sql})"
        )

        await self.async_execute(
            sql,
            commit=True,
        )

        table.database = self

        self.tables[
            table.table_name
        ] = table

        return table

    # --------------------------------------------------------
    # get_table
    # --------------------------------------------------------


    # --------------------------------------------------------
    # Close
    # --------------------------------------------------------

    def close(self):
        """
        同步关闭数据库。

        注意：
        如果 async_connection 已经建立，
        应优先使用 close_async()。
        """

        if self.connection is not None:
            self.connection.close()

        self.connection = None
        self._initialized = False

    async def close_async(self):
        """
        异步关闭数据库。
        """

        if self.async_connection is not None:
            await self.async_connection.close()

        self.async_connection = None

        if self.connection is not None:
            self.connection.close()

        self.connection = None
        self._initialized = False


# ============================================================
# Table
# ============================================================

class Table:

    table_name: str
    columns: list[Column]

    # 所属 Database
    database: Database | None

    def __init__(
        self,
        table_name: str,
        *columns: Column,
    ):
        self.table_name = table_name
        self.columns = list(columns)
        self.database = None

    # ========================================================
    # AST compiler
    # ========================================================

    @staticmethod
    def _compile_ast(
        data_filter: ASTOperator,
    ) -> tuple[str, list[Any]]:
        """
        将 ASTOperator 编译为：

            (SQL expression, parameters)

        例如：

            And(
                Eq("is_admin", False),
                Lt("last_login_ts", 1787155200)
            )

        →

            (
                '"is_admin" = ? AND '
                '"last_login_ts" < ?'
            )

        parameters：

            [False, 1787155200]
        """

        node = (
            data_filter.to_node()
            if hasattr(data_filter, "to_node")
            else data_filter
        )

        return Table._compile_ast_node(node)

    @staticmethod
    def _compile_ast_node(
        node: dict[str, Any],
    ) -> tuple[str, list[Any]]:
        """
        编译 AST node。

        node 的结构来自 ast.py：

        {
            "op_type": "...",
            "op_name": "...",
            ...
        }
        """

        if not isinstance(node, dict):
            raise InvalidASTError(
                f"AST node must be dict, "
                f"got {type(node).__name__}"
            )

        op_type = node.get(
            "op_type"
        )

        op_name = node.get(
            "op_name"
        )

        if op_type is None:
            raise InvalidASTError(
                f"AST node has no op_type: {node!r}"
            )

        if op_name is None:
            raise InvalidASTError(
                f"AST node has no op_name: {node!r}"
            )

        op_name = str(op_name).lower()

        # ====================================================
        # Void
        # ====================================================

        if op_type == "void":

            if op_name != "void":
                raise InvalidASTError(
                    f"Unknown void operator: "
                    f"{op_name!r}"
                )

            # WHERE 1 永远成立
            return "1", []

        # ====================================================
        # Logic operators
        # ====================================================

        if op_type == "logic":

            # ------------------------------------------------
            # NOT
            # ------------------------------------------------

            if op_name == "not":

                if "a" not in node:
                    raise InvalidASTError(
                        "NOT requires 'a'"
                    )

                sql, parameters = (
                    Table._compile_ast_node(
                        node["a"]
                    )
                )

                return (
                    f"(NOT ({sql}))",
                    parameters,
                )

            # ------------------------------------------------
            # AND / OR
            # ------------------------------------------------

            if op_name in {
                "and",
                "or",
            }:

                operands = node.get(
                    "operands"
                )

                if operands is None:
                    raise InvalidASTError(
                        f"{op_name.upper()} "
                        "requires 'operands'"
                    )

                if not isinstance(
                    operands,
                    list,
                ):
                    raise InvalidASTError(
                        "'operands' must be list"
                    )

                # 空 AND：
                #
                # True
                #
                # 空 OR：
                #
                # False
                if not operands:

                    if op_name == "and":
                        return "1", []

                    return "0", []

                expressions = []
                parameters = []

                for operand in operands:

                    sql, params = (
                        Table._compile_ast_node(
                            operand
                        )
                    )

                    expressions.append(
                        f"({sql})"
                    )

                    parameters.extend(
                        params
                    )

                sql_operator = (
                    " AND "
                    if op_name == "and"
                    else " OR "
                )

                return (
                    "("
                    + sql_operator.join(
                        expressions
                    )
                    + ")",
                    parameters,
                )

            # ------------------------------------------------
            # XOR
            # ------------------------------------------------

            if op_name == "xor":

                if (
                    "a" not in node
                    or "b" not in node
                ):
                    raise InvalidASTError(
                        "XOR requires 'a' and 'b'"
                    )

                a_sql, a_params = (
                    Table._compile_ast_node(
                        node["a"]
                    )
                )

                b_sql, b_params = (
                    Table._compile_ast_node(
                        node["b"]
                    )
                )

                # SQLite 没有直接的 SQL XOR
                #
                # A XOR B
                #
                # = (A OR B) AND NOT (A AND B)

                sql = (
                    f"("
                    f"(({a_sql}) OR ({b_sql})) "
                    f"AND "
                    f"NOT (({a_sql}) AND ({b_sql}))"
                    f")"
                )

                return (
                    sql,
                    [
                        *a_params,
                        *b_params,
                        *a_params,
                        *b_params,
                    ],
                )

            raise InvalidASTError(
                f"Unsupported logic operator: "
                f"{op_name!r}"
            )

        # ====================================================
        # Condition operators
        # ====================================================

        if op_type == "condition":

            if (
                "a" not in node
                or "b" not in node
            ):
                raise InvalidASTError(
                    f"Condition operator "
                    f"{op_name!r} requires "
                    "'a' and 'b'"
                )

            column = node["a"]
            value = node["b"]

            # a 应该是列名
            if not isinstance(
                column,
                str,
            ):
                raise InvalidASTError(
                    "Condition left operand "
                    "must be a column name"
                )

            column_sql = _quote_identifier(
                column
            )

            # ------------------------------------------------
            # NULL 特殊处理
            # ------------------------------------------------

            if value is None:

                if op_name == "eq":
                    return (
                        f"{column_sql} IS NULL",
                        [],
                    )

                if op_name == "ne":
                    return (
                        f"{column_sql} IS NOT NULL",
                        [],
                    )

                raise InvalidASTError(
                    f"Cannot use NULL with "
                    f"{op_name!r}"
                )

            # ------------------------------------------------
            # 普通比较
            # ------------------------------------------------

            sql_operators = {
                "eq": "=",
                "ne": "!=",
                "lt": "<",
                "gt": ">",
                "le": "<=",
                "ge": ">=",
            }

            if op_name not in sql_operators:
                raise InvalidASTError(
                    f"Unsupported condition "
                    f"operator: {op_name!r}"
                )

            sql_operator = (
                sql_operators[op_name]
            )

            return (
                f"{column_sql} "
                f"{sql_operator} ?",
                [value],
            )

        # ====================================================
        # Special conditions
        # ====================================================

        if op_type == "special_condition":

            raise InvalidASTError(
                f"Special condition "
                f"{op_name!r} is not implemented"
            )

        raise InvalidASTError(
            f"Unknown AST operator type: "
            f"{op_type!r}"
        )

    # ========================================================
    # Find
    # ========================================================

    def find(
        self,
        data_filter: ASTOperator = VoidOperator(),
        limit: int = -1,
    ) -> list[dict[str, Any]]:
        """
        同步查询。

        limit=-1 表示不限制数量。
        """

        if self.database is None:
            raise DatabaseNotInitializedError(
                f"Table {self.table_name!r} "
                "is not attached to a Database"
            )

        where_sql, parameters = (
            self._compile_ast(
                data_filter
            )
        )

        sql = (
            "SELECT * FROM "
            f"{_quote_identifier(self.table_name)} "
            f"WHERE {where_sql}"
        )

        if limit != -1:

            if limit < 1:
                raise ValueError(
                    "limit must be -1 or >= 1"
                )

            sql += " LIMIT ?"
            parameters.append(int(limit))

        cursor = self.database.execute(
            sql,
            parameters,
        )

        return _rows_to_dict(
            cursor.fetchall()
        )

    async def find_async(
        self,
        data_filter: ASTOperator = VoidOperator(),
        limit: int = -1,
    ) -> list[dict[str, Any]]:

        if self.database is None:
            raise DatabaseNotInitializedError(
                f"Table {self.table_name!r} "
                "is not attached to a Database"
            )

        where_sql, parameters = (
            self._compile_ast(
                data_filter
            )
        )

        sql = (
            "SELECT * FROM "
            f"{_quote_identifier(self.table_name)} "
            f"WHERE {where_sql}"
        )

        if limit != -1:
            if limit < 1:
                raise ValueError("limit must be -1 or >= 1")
            sql += " LIMIT ?"
            parameters.append(int(limit))

        connection = await self.database.ensure_async_connection()

        cursor = await connection.execute(
            sql,
            tuple(parameters),
        )

        rows = await cursor.fetchall()

        return [
            dict(row)
            for row in rows
        ]

    # ========================================================
    # Add
    # ========================================================

    def add(
        self,
        **data,
    ) -> int:

        if self.database is None:
            raise DatabaseNotInitializedError()

        if not data:
            raise ValueError(
                "data cannot be empty"
            )

        columns = list(
            data.keys()
        )

        sql = (
            "INSERT INTO "
            f"{_quote_identifier(self.table_name)} "
            "("
            + ", ".join(
                _quote_identifier(column)
                for column in columns
            )
            + ") VALUES ("
            + ", ".join(
                "?"
                for _ in columns
            )
            + ")"
        )

        cursor = self.database.execute(
            sql,
            [
                data[column]
                for column in columns
            ],
            commit=True,
        )

        return cursor.lastrowid

    async def add_async(
        self,
        **data,
    ) -> int:

        if self.database is None:
            raise DatabaseNotInitializedError()

        if not data:
            raise ValueError(
                "data cannot be empty"
            )

        columns = list(
            data.keys()
        )

        sql = (
            "INSERT INTO "
            f"{_quote_identifier(self.table_name)} "
            "("
            + ", ".join(
                _quote_identifier(column)
                for column in columns
            )
            + ") VALUES ("
            + ", ".join(
                "?"
                for _ in columns
            )
            + ")"
        )

        cursor = await self.database.async_execute(
            sql,
            [
                data[column]
                for column in columns
            ],
            commit=True,
        )

        return cursor.lastrowid

    # ========================================================
    # Modify
    # ========================================================

    def modify(
        self,
        data: dict[str, Any],
        data_filter: ASTOperator = VoidOperator(),
    ) -> int:

        if self.database is None:
            raise DatabaseNotInitializedError()

        if not data:
            raise ValueError(
                "data cannot be empty"
            )

        _warn_if_bulk_mutation("modify", self.table_name, data_filter)

        where_sql, where_parameters = (
            self._compile_ast(
                data_filter
            )
        )

        set_sql = ", ".join(
            f"{_quote_identifier(column)} = ?"
            for column in data
        )

        sql = (
            "UPDATE "
            f"{_quote_identifier(self.table_name)} "
            f"SET {set_sql} "
            f"WHERE {where_sql}"
        )

        parameters = [
            data[column]
            for column in data
        ]

        parameters.extend(
            where_parameters
        )

        cursor = self.database.execute(
            sql,
            parameters,
            commit=True,
        )

        return cursor.rowcount

    async def modify_async(
        self,
        data: dict[str, Any],
        data_filter: ASTOperator = VoidOperator(),
    ) -> int:

        if self.database is None:
            raise DatabaseNotInitializedError()

        if not data:
            raise ValueError(
                "data cannot be empty"
            )

        _warn_if_bulk_mutation("modify_async", self.table_name, data_filter)

        where_sql, where_parameters = (
            self._compile_ast(
                data_filter
            )
        )

        set_sql = ", ".join(
            f"{_quote_identifier(column)} = ?"
            for column in data
        )

        sql = (
            "UPDATE "
            f"{_quote_identifier(self.table_name)} "
            f"SET {set_sql} "
            f"WHERE {where_sql}"
        )

        parameters = [
            data[column]
            for column in data
        ]

        parameters.extend(
            where_parameters
        )

        cursor = await self.database.async_execute(
            sql,
            parameters,
            commit=True,
        )

        return cursor.rowcount

    # ========================================================
    # Delete
    # ========================================================

    def delete(
        self,
        data_filter: ASTOperator = VoidOperator(),
    ) -> int:

        if self.database is None:
            raise DatabaseNotInitializedError()

        _warn_if_bulk_mutation("delete", self.table_name, data_filter)

        where_sql, parameters = (
            self._compile_ast(
                data_filter
            )
        )

        sql = (
            "DELETE FROM "
            f"{_quote_identifier(self.table_name)} "
            f"WHERE {where_sql}"
        )

        cursor = self.database.execute(
            sql,
            parameters,
            commit=True,
        )

        return cursor.rowcount

    async def delete_async(
        self,
        data_filter: ASTOperator = VoidOperator(),
    ) -> int:

        if self.database is None:
            raise DatabaseNotInitializedError()

        _warn_if_bulk_mutation("delete_async", self.table_name, data_filter)

        where_sql, parameters = (
            self._compile_ast(
                data_filter
            )
        )

        sql = (
            "DELETE FROM "
            f"{_quote_identifier(self.table_name)} "
            f"WHERE {where_sql}"
        )

        cursor = await self.database.async_execute(
            sql,
            parameters,
            commit=True,
        )

        return cursor.rowcount


# ============================================================
# Column
# ============================================================

class Column:

    column_name: str
    column_type: str

    def __init__(
        self,
        column_name: str,
        column_type: str,
    ):
        self.column_name = column_name
        self.column_type = column_type


# ============================================================
# Initialization API
# ============================================================

def init_database(
    *tables: Table,
) -> Database:
    """
    初始化当前 Runtime 的 Database，
    并自动 CREATE TABLE。

    示例：

        users = Table(
            "users",
            [
                Column(
                    "id",
                    "INTEGER PRIMARY KEY AUTOINCREMENT",
                ),
                Column(
                    "name",
                    "TEXT NOT NULL",
                ),
                Column(
                    "is_admin",
                    "INTEGER NOT NULL DEFAULT 0",
                ),
            ]
        )

        db = init_database([users])
    """

    context = get_context()

    database = Database(
        context.package_name
    )

    # 先登记 Table
    for table in tables:

        if table.table_name in database.tables:
            raise TableError(
                f"Duplicate table: "
                f"{table.table_name!r}"
            )

        database.tables[table.table_name] = table

        table.database = database

    # 初始化数据库
    database.init()

    # 保存到 Runtime Context
    context.database = database

    return database

def get_table(
    table_name: str,
) -> Table:
    """
    获取数据库中指定的表
    :param table_name: 表名
    """

    database = get_context().database

    if database is None:
        raise DatabaseNotInitializedError(
            "Current runtime has no database"
        )

    if table_name not in database.tables:
        raise TableNotFoundError(
            f"Table {table_name!r} "
            "does not exist"
        )

    return database.tables[
        table_name
    ]