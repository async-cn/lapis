from __future__ import annotations
from typing import TYPE_CHECKING
from functools import wraps
from uuid import uuid4

import inspect

from .runtime import get_context
from .ast import VoidOperator
from .log import *
from .server_message import message_handler
from .utils import dict_trans

from .player import Player
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
        self._registration_queue:list[EventListener] = []

    def pre_register_listener(self, event_listener: EventListener) -> None:
        """
        登记事件监听器，但不注册
        :param event_listener: 事件监听器
        :return:
        """
        self._registration_queue.append(event_listener)
        debug(f"{event_listener} pre registered")

    async def register_all(self) -> None:

        for event_listener in self._registration_queue:
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
            if data["listener_uuid"] != (str(event_listener.uuid)):
                raise RuntimeError("Listener UUID mismatch")
            if data["state"] != "ok":
                raise RuntimeError(
                    "Failed to register event listener: "
                    f"{data['state']}"
                )

            self._registry[str(event_listener.uuid)] = event_listener
            debug(
                f"{event_listener} registered"
            )
        self._registration_queue = []

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
    def __init__(self, raw_data:dict) -> None:
        self.event_type: str = raw_data["event_type"]
        self.listener_uuid: str = raw_data["listener_uuid"]
        self.data: dict = raw_data["data"]
        self.proxy: bool = raw_data["proxy"]
        self.event_id: str = raw_data["event_id"]
    def get_target_player(self) -> Player:
        return Player(self.data["player"]["uuid"])
    def get_block(self) -> Block:
        return create_block(
            **dict_trans(self.data["block"], {
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

def on(event_type:str, event_filter:ASTOperator=None, event_subscription:list=None, proxy:bool=False):
    """
    装饰器，对事件handler函数使用，原始handler函数应接受一个Event参数
    :param event_type: 事件类型
    :param event_filter: 事件过滤器，为空则接受所有指定类型的事件
    :param event_subscription: 订阅事件信息，为空则返回事件的全部信息
    :param proxy: 是否使用事件代理模式
    :return: 事件监听器UUID
    """
    if event_filter is None:
        event_filter = VoidOperator()
    if event_subscription is None:
        event_subscription = []
    event_filter = EventFilter(event_filter)
    event_subscription = EventSubscription(event_subscription)
    def decorator(func:Callable[[Event], None|bool]): # proxy为true时返回类型应为bool
        event_listener = EventListener(func, event_type, event_filter, event_subscription, proxy)
        get_context().event_registry.pre_register_listener(event_listener)
        @wraps(func)
        def wrapper(*args, **kwargs):
           return func(*args, **kwargs)
        return wrapper
    return decorator

@message_handler("event")
async def event_dispatcher(message: ServerMessage) -> bool:
    event = Event(message.data)
    await get_context().event_registry.dispatch(event)
    return True
