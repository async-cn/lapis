from __future__ import annotations
from typing import TYPE_CHECKING
from functools import wraps
from uuid import uuid4

import inspect

from .runtime import get_context
from .ast import VoidOperator
from .log import *
from .server_message import message_handler, register_message_handler, ServerMessageHandler
from .utils import Data, dict_trans

from .player import Player, create_player
from .block import create_block

if TYPE_CHECKING:
    from typing import Callable
    from uuid import UUID
    from .ast import ASTOperator
    from .server_message import ServerMessage
    from .block import Block

class EventRegistry:
    def __init__(self):
        self._registry:dict[str, EventListener] = {}
        self._registration_pool:list[EventListener] = []
        # event_dispatcher 每个 Package 只需要注册一次
        self._event_dispatcher_registered = False

    def pre_register_listener(self, event_listener: EventListener) -> None:
        """
        登记事件监听器，但不注册
        :param event_listener: 事件监听器
        :return:
        """
        self._registration_pool.append(event_listener)
        debug(f"{event_listener} pre registered")

    async def register_all(self) -> None:

        # ---- 首次注册时绑定 SDK 内置的 event 分发器 ----
        if not self._event_dispatcher_registered:
            register_message_handler(
                ServerMessageHandler("event", event_dispatcher)
            )
            self._event_dispatcher_registered = True

        for event_listener in self._registration_pool:
            response = await get_context().client.command(
                "register_event_listener",
                {
                    "package_name": get_context().package_name,
                    "listener_uuid": str(event_listener.uuid),
                    "event_type": event_listener.event_type,
                    "filter": event_listener.event_filter.to_nodes(),
                    "subscription": event_listener.subscription.to_list(),
                    "proxy": event_listener.proxy
                },
            )
            if response.response_type != "register_event_listener_response":
                raise RuntimeError(
                    "Unexpected response type: "
                    f"{response.response_type}"
                )

            data = response.data
            if data.get("listener_uuid") != (str(event_listener.uuid)):
                raise RuntimeError("Listener UUID mismatch")
            if data.get("state") != "ok":
                raise RuntimeError(
                    "Failed to register event listener: "
                    f"{data.get('state')}"
                )

            self._registry[str(event_listener.uuid)] = event_listener
            debug(
                f"{event_listener} registered"
            )
        self._registration_pool = []

    async def unregister_listener(self, uuid:UUID) -> bool:
        """
        卸载事件监听器
        :param uuid: 事件监听器UUID
        :return:
        """
        if not str(uuid) in self._registry:
            error(f"Failed to unregister EventListener: EventLister(#{str(uuid)}) is not found")
            return False
        await get_context().client.command(
            "unregister_event_listener",
            {
                "listener_uuid": str(uuid)
            }
        )
        del self._registry[str(uuid)]
        debug(f"{uuid} unregistered")
        return True

    async def dispatch(self, event:Event) -> None:
        """
        接收到Java端发送的事件且JSON被转换为Event对象后自动调用此函数
        :param event: 事件
        :return:
        """
        debug(f"Received Event ({event.event_type}) dispatched -> {event.listener_uuid})")
        debug(event.data)
        event_listener_uuid:str = str(event.listener_uuid)
        if event_listener_uuid not in self._registry:
            error(f"Undefined EventListener UUID: {event_listener_uuid}")
            return
        event_listener = self._registry[event_listener_uuid]
        r = event_listener.handler(event)
        result:None|bool = (await r) if inspect.isawaitable(r) else r
        if event_listener.proxy:
            await get_context().client.send_message_response(
                "event_proxy_result",
                {
                    "event_id": event.event_id,
                    "continue": result
                }
            )

class Event:
    """
    接收到Java端发送的事件数据时，自动将JSON转换为Event对象
    """
    event_type: str
    listener_uuid: str
    data: Data
    proxy: bool
    event_id: str

    def __init__(self, raw_data:dict) -> None:
        self.event_type = raw_data["event_type"]
        self.listener_uuid = raw_data["listener_uuid"]
        self.data = Data(raw_data["data"])
        if "proxy" in raw_data:
            self.proxy = raw_data["proxy"]
            self.event_id = raw_data["event_id"]
        else:
            self.proxy: bool = False
            self.event_id = "00000000-0000-0000-0000-000000000000"
    def get_target_player(self) -> Player:
        return Player(self.data.get("player.uuid"))
    def get_player(self) -> Player:
        """从事件数据中的完整 player 字典构造 Player（含 name/nbt 快照属性）。"""
        return create_player(self.data.get("player") or {})
    def get_block(self) -> Block:
        return create_block(
            **dict_trans(self.data.get("block"), {
                "id": "block_id",
                "world": "world",
                "pos": "pos_raw",
                "state": "block_state",
                "nbt": "nbt_raw"
            })
        )

class EventFilter:
    """
    事件过滤器，用于Java端过滤所需的事件
    空过滤器代表接受所有指定event_type的事件
    """
    def __init__(self, filter_ast:ASTOperator=None):
        if filter_ast is None:
            filter_ast = VoidOperator()
        self.filter_ast = filter_ast
    def to_nodes(self):
        return self.filter_ast.to_node()

class EventSubscription:
    """
    事件订阅，用于Java端筛选附带在指定事件中发送的信息
    空订阅代表事件触发时发回全部事件数据
    """
    def __init__(self, subscriptions=None):
        if subscriptions is None:
            subscriptions = []
        self.subscriptions: list = subscriptions
    def to_list(self):
        return self.subscriptions

class EventListener:
    """
    事件监听器
    """
    def __init__(self,
            handler:Callable,
            event_type:str,
            event_filter:EventFilter,
            subscription:EventSubscription,
            proxy:bool=False
        ):
        self.event_type = event_type
        self.handler = handler
        self.event_filter = event_filter
        self.subscription = subscription
        self.uuid:UUID = uuid4()
        self.proxy: bool = proxy

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.event_type}#{str(self.uuid)})"

class DefinedEventListener:
    """
    由 on(auto_register=False) 装饰产生的未注册事件监听器定义
    调用实例等价于调用被装饰的handler函数，可由调用者通过
    register()/register_dyna() 自主控制注册时机
    """
    def __init__(self,
            func:Callable,
            event_type:str,
            event_filter:EventFilter,
            subscription:EventSubscription,
            proxy:bool=False
        ):
        self.func = func
        self.event_type = event_type
        self.event_filter = event_filter
        self.subscription = subscription
        self.proxy = proxy
        self.event_listener: EventListener|None = None

    @property
    def uuid(self) -> UUID|None:
        return self.event_listener.uuid if self.event_listener else None

    def __call__(self, *args, **kwargs):
        return self.func(*args, **kwargs)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.event_type}#{str(self.uuid)})"

    def register(self) -> None:
        """创建EventListener，自动调用pre_register_listener加入等待池"""
        self.event_listener = EventListener(
            self.func, self.event_type, self.event_filter, self.subscription, self.proxy
        )
        get_context().event_registry.pre_register_listener(self.event_listener)

    async def register_dyna(self) -> str:
        """调用register方法，然后自动调用register_all进行实际注册"""
        self.register()
        await get_context().event_registry.register_all()
        return str(self.uuid)

def on(event_type:str, event_filter:ASTOperator|None = None, event_subscription:list|None = None, proxy:bool=False, auto_register:bool=True) -> Callable | DefinedEventListener:
    """
    装饰器，对事件handler函数使用，原始handler函数应接受一个Event参数
    :param event_type: 事件类型
    :param event_filter: 事件过滤器，为空则接受所有指定类型的事件
    :param event_subscription: 订阅事件信息，为空则返回事件的全部信息
    :param proxy: 是否使用事件代理模式
    :param auto_register: 是否在装饰时自动预注册；为False时返回DefinedEventListener实例，由调用者手动注册
    :return: auto_register=True时无有效返回值；auto_register=False时返回DefinedEventListener实例
    """
    if event_filter is None:
        event_filter = VoidOperator()
    if event_subscription is None:
        event_subscription = []
    event_filter = EventFilter(event_filter)
    event_subscription = EventSubscription(event_subscription)
    def decorator(func:Callable[[Event], None|bool]): # proxy为true时返回类型应为bool
        if not auto_register:
            return DefinedEventListener(func, event_type, event_filter, event_subscription, proxy)
        event_listener = EventListener(func, event_type, event_filter, event_subscription, proxy)
        get_context().event_registry.pre_register_listener(event_listener)
        @wraps(func)
        def wrapper(*args, **kwargs):
           return func(*args, **kwargs)
        return wrapper
    return decorator

async def event_dispatcher(message: ServerMessage) -> bool:
    event = Event(message.data)
    await get_context().event_registry.dispatch(event)
    return True
