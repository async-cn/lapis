from __future__ import annotations

from lapis.config import Config
from lapis.runtime import (
    Runtime,
    set_context,
    reset_context,
    get_context,
)
from lapis.context import LapisContext


def test_version_exists():
    assert isinstance(Config.VERSION, str)
    parts = Config.VERSION.split(".")
    assert len(parts) >= 2


def test_default_password_exists_on_config():
    assert isinstance(Config.SERVER_PASSWORD, str)
    assert hasattr(Config, "DEBUG")


def test_runtime_set_get_reset():
    ctx = LapisContext(
        package_name="pytest_pkg",
        client=None,
        event_registry=None,
        database=None,
    )
    token = set_context(ctx)
    try:
        assert get_context().package_name == "pytest_pkg"
    finally:
        reset_context(token)


def test_runtime_activate_and_bind():
    runtime = Runtime("demo_pkg")
    ctx = LapisContext(
        package_name="demo_pkg",
        client=None,
        event_registry=None,
        database=None,
    )
    runtime.context = ctx

    # bind_context 不返回 token，但会把 context 设置为当前
    runtime.bind_context(ctx)
    try:
        assert get_context() is ctx
    finally:
        # bind_context 内部使用 set_context，这里通过 activate 拿到 token 来 unwind
        token_to_reset = runtime.activate()
        # activate 是重新 set，所以等价于当前还是 ctx；真正的 reset
        # 依赖 runtime._context_token，但它是私有字段。所以最稳妥是再手动
        # set 回 original (None)。
        reset_context(token_to_reset)

    # 切换到其他 context，再 activate() 应该 restore
    other = LapisContext("other", None, None, None)
    t2 = set_context(other)
    t3 = runtime.activate()
    try:
        assert get_context() is ctx
    finally:
        reset_context(t3)
        reset_context(t2)
