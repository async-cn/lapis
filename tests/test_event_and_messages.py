from __future__ import annotations

import asyncio

from lapis.context import LapisContext
from lapis.runtime import set_context, reset_context
from lapis.event import EventRegistry, Event, on as event_handler
from lapis.ast import VoidOperator
from lapis.server_message import (
    dispatcher,
    init_message_dispatcher,
    message_handler,
    ServerMessageHandler,
)
from lapis.utils import Data


# ==================================================================
# Stubs
# ==================================================================

class DummyClient:
    def __init__(self):
        self.calls = []
        self._msg_handler = None

    async def send_command(self, command_type, data):
        self.calls.append((command_type, data))
        return {"ok": True, "data": None}

    async def command(self, command_type, data):
        class _Resp:
            def __init__(self, rt, d):
                self.response_type = rt
                self.data = Data(d)
        # register_event_listener 时模拟返回 ok
        listener_uuid = data.get("listener_uuid", "")
        self.calls.append((command_type, data))
        return _Resp(
            "register_event_listener_response",
            {"listener_uuid": listener_uuid, "state": "ok"},
        )

    def set_message_handler(self, h):
        self._msg_handler = h


def _make_ctx(package_name: str, with_registry: bool = True):
    client = DummyClient()
    ctx = LapisContext(
        package_name=package_name,
        client=client,
        event_registry=EventRegistry() if with_registry else None,
        database=None,
    )
    token = set_context(ctx)
    return ctx, client, token


# ==================================================================
# EventRegistry: 监听器能被记录 & register_all 会调用 client
# ==================================================================

def test_event_handler_registers_and_runs_in_order():
    ctx, client, token = _make_ctx("evt_pkg")
    reg = ctx.event_registry

    seen: list[str] = []

    @event_handler("player_join")
    def first(evt):
        seen.append("first")

    @event_handler("player_join")
    def second(evt):
        seen.append("second")

    assert len(reg._registration_pool) == 2

    async def main():
        await reg.register_all()
        # 直接按注册顺序遍历 EventListener 并执行 handler —— 模拟 Java 桥
        # 逐个 listener_uuid 触发事件的行为。
        dummy_raw = {
            "event_type": "player_join",
            "listener_uuid": "",   # 下面填真实的
            "data": {"player": "alice"},
            "proxy": False,
            "event_id": "e-1",
        }
        for uuid_str, listener in reg._registry.items():
            dummy_raw["listener_uuid"] = uuid_str
            evt = Event(dummy_raw)
            r = listener.handler(evt)
            import inspect as _inspect
            if _inspect.isawaitable(r):
                await r

    asyncio.run(main())

    # listener 按注册顺序被调用（FIFO），且 client 收到了注册请求
    assert seen == ["first", "second"]
    cmd_names = [c[0] for c in client.calls]
    assert all(c == "register_event_listener" for c in cmd_names)
    assert len(cmd_names) == 2

    reset_context(token)


# ==================================================================
# server_message: 按 Package 隔离 + 未匹配时仅 warning 不崩溃
# ==================================================================

def test_server_message_handlers_are_context_isolated():
    # --- pkg_a ---
    ctx_a, _, ta = _make_ctx("pkg_a", with_registry=False)

    received_a: list[str] = []

    @message_handler("greeting")
    def handle_a(msg):
        received_a.append("a:" + msg.data["text"])
        return True

    reset_context(ta)

    # --- pkg_b ---
    ctx_b, _, tb = _make_ctx("pkg_b", with_registry=False)
    received_b: list[str] = []

    @message_handler("greeting")
    def handle_b(msg):
        received_b.append("b:" + msg.data["text"])
        return True

    # 当前 context 是 b：dispatch 给 b
    asyncio.run(dispatcher({"message_type": "greeting", "data": {"text": "hello"}}))
    assert received_b == ["b:hello"]
    assert received_a == []

    # 切到 a 再分发
    reset_context(tb)
    set_context(ctx_a)
    asyncio.run(dispatcher({"message_type": "greeting", "data": {"text": "hi"}}))
    assert received_a == ["a:hi"]
    assert received_b == ["b:hello"]  # b 没新增

    # 各自 message_handlers 是分开的
    assert len(ctx_a.message_handlers) == 1
    assert len(ctx_b.message_handlers) == 1

    # 清理
    reset_context(set_context(ctx_a))


def test_init_message_dispatcher_hooks_client():
    client = DummyClient()
    ctx = LapisContext("pkg_x", client=client, event_registry=None, database=None)
    token = set_context(ctx)
    init_message_dispatcher()
    try:
        assert client._msg_handler is dispatcher
    finally:
        reset_context(token)
