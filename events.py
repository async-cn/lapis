from __future__ import annotations
from typing import TYPE_CHECKING
from functools import wraps
from uuid import uuid4 as uuid

import inspect
import json

from .runtime import get_context
from .ast import VoidOperator
from .log import *
from .message import message_handler

from .player import TargetPlayer

if TYPE_CHECKING:
    from typing import Callable
    from uuid import UUID
    from .ast import Operator
    from .message import Message

class EventRegistry():
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
                    "filter": event_listener.event_filter.to_json(),
                    "subscription": event_listener.subscription.to_json(),
                },
            )
            if response["response_type"] != (
                "register_event_listener_response"
            ):
                raise RuntimeError(
                    "Unexpected response type: "
                    f"{response['response_type']}"
                )

            data = response["data"]
            if data["listener_uuid"] != (
                str(event_listener.uuid)
            ):
                raise RuntimeError(
                    "Listener UUID mismatch"
                )
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

    def unregister_listener(self, uuid:UUID) -> bool:
        """
        卸载事件监听器
        :param uuid: 事件监听器UUID
        :return:
        """
        if not str(uuid) in self._registry:
            error(f"Failed to unregister EventListener: Eventlister(#{str(uuid)}) is not found")
            return False
        ... # TODO 向Java端发送解除指定EventListener的指令
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
        result = event_listener.handler(event)
        if inspect.isawaitable(result):
            await result

class Event(): # TODO
    """
    接收到Java端发送的事件数据时，自动将JSON转换为Event对象
    """
    def __init__(self, raw_data:dict) -> None:
        self.event_type: str = raw_data["event_type"]
        self.listener_uuid: str = raw_data["listener_uuid"]
        self.data: dict = raw_data["data"]
    def get_target_player(self) -> TargetPlayer:
        return TargetPlayer(self.data["player"]["uuid"])

class EventFilter(): # TODO
    """
    事件过滤器，用于Java端过滤所需的事件
    空过滤器代表接受所有指定event_type的事件
    """
    def __init__(self, filter_ast:Operator=None):
        if filter_ast is None:
            filter_ast = VoidOperator()
        self.filter_ast = filter_ast
    def to_json(self):
        return self.filter_ast.to_node()

class EventSubscription: # TODO
    """
    事件订阅，用于Java端筛选附带在指定事件中发送的信息
    空订阅代表事件触发时发回全部事件数据
    """
    def __init__(self, subscriptions=None):
        if subscriptions is None:
            subscriptions = []
        self.subscriptions: list = subscriptions
    def to_json(self):
        return self.subscriptions

class EventListener():
    """
    事件监听器
    """
    def __init__(self, handler:Callable, event_type:str, event_filter:EventFilter, subscription:EventSubscription):
        self.event_type = event_type
        self.handler = handler
        self.event_filter = event_filter
        self.subscription = subscription
        self.uuid:UUID = uuid()
        pass
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.event_type}#{str(self.uuid)})"

def on(event_type:str, event_filter:Operator=None, event_subscription:list=None):
    """
    装饰器，对事件handler函数使用，原始handler函数应接受一个Event参数
    :param event_type: 事件类型
    :param event_filter: 事件过滤器，为空则接受所有指定类型的事件
    :param event_subscription: 订阅事件信息，为空则返回事件的全部信息
    :return: 事件监听器UUID
    """
    if event_filter is None:
        event_filter = VoidOperator()
    if event_subscription is None:
        event_subscription = []
    event_filter = EventFilter(event_filter)
    event_subscription = EventSubscription(event_subscription)
    def decorator(func):
        event_listener = EventListener(func, event_type, event_filter, event_subscription)
        get_context().event_registry.pre_register_listener(event_listener)
        @wraps(func)
        def wrapper(*args, **kwargs):
           return func(*args, **kwargs)
        return wrapper
    return decorator

@message_handler("event")
async def event_dispatcher(message: Message) -> bool:
    event = Event(message.data)
    await get_context().event_registry.dispatch(event)
    return True
