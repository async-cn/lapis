from __future__ import annotations
from functools import wraps
from typing import Callable
from uuid import uuid4 as uuid, UUID

import inspect

from .log import *

_event_listeners:dict[str,EventListener] = {}

class Event(): # TODO
    """
    接收到Java端发送的事件数据时，自动将JSON转换为Event对象
    """
    event_type: str = ""
    event_listener_uuid = None
    data: dict = {}
    ... # 时间等其他元信息
    pass

class EventFilter(): # TODO
    """
    事件过滤器，用于Java端过滤所需的事件
    空过滤器代表接受所有指定event_type的事件
    """
    def __init__(self, filterStructure:dict={}):
        pass

class EventSubscription: # TODO
    """
    事件订阅，用于Java端筛选附带在指定事件中发送的信息
    空订阅代表事件触发时发回全部事件数据
    """
    def __init__(self, subscriptionStructure:dict={}):
        pass

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

def register_event_listener(event_listener:EventListener) -> None:
    if not hasattr(event_listener, 'handler'):
        debug(f"{event_listener} is not registered: no handler")
        return
    ... # TODO 向Java端发送注册指定EventListener的指令，附带JSON化的EventFilter和EventSubscription
    _event_listeners[str(event_listener.uuid)]=event_listener
    debug(f"{event_listener} registered")

def unregister_event_listener(uuid:UUID) -> bool:
    if not str(uuid) in _event_listeners:
        error(f"Failed to unregister EventListener: Eventlister(#{str(uuid)}) is not found")
        return False
    ... # TODO 向Java端发送解除指定EventListener的指令
    del _event_listeners[str(uuid)]
    debug(f"{uuid} unregistered")
    return True

def on(event_type:str, event_filter:dict=None, subscription:dict=None):
    """
    装饰器，对事件handler函数使用，原始handler函数应接受一个Event参数
    :param event_type: 事件类型
    :param event_filter: 事件过滤器，为空则接受所有指定类型的事件
    :param subscription: 订阅事件信息，为空则返回事件的全部信息
    :return: 事件监听器UUID
    """
    if event_filter is None:
        event_filter = {}
    if subscription is None:
        subscription = {}
    event_filter = EventFilter(event_filter)
    subscription = EventSubscription(subscription)
    def decorator(func):
        event_listener = EventListener(func, event_type, event_filter, subscription)
        register_event_listener(event_listener)
        def wrapper() -> UUID:
           return event_listener.uuid
        return wrapper
    return decorator

async def dispatch(event:Event) -> None:
    """
    接收到Java端发送的事件且JSON被转换为Event对象后自动调用此函数
    :param event: 事件
    :return:
    """
    event_listener_uuid:str = str(event.event_listener_uuid)
    if event_listener_uuid not in _event_listeners:
        error(f"Undefined EventListener UUID: {event_listener_uuid}")
        return
    event_listener = _event_listeners[event_listener_uuid]
    result = event_listener.handler(event)
    if inspect.isawaitable(result):
        await result