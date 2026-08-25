from __future__ import annotations

import asyncio
import json
import struct
from typing import Any, Awaitable, Callable

from .config import Config

class LapisClientError(Exception):
    """Lapis Client 基础异常。"""

class LapisConnectionError(LapisClientError):
    """连接相关异常。"""

class LapisProtocolError(LapisClientError):
    """协议错误。"""

class LapisCommandError(LapisClientError):
    """Java 端返回 ok=false。"""

    def __init__(
        self,
        response_type: str,
        command_id: int,
        data: Any = None,
    ):
        self.response_type = response_type
        self.command_id = command_id
        self.data = data

        super().__init__(
            f"Command failed: "
            f"{response_type}#{command_id}, "
            f"data={data!r}"
        )


class LapisClient:
    """
    Lapis Python Client。

    负责：
        - 与 Java Lapis Bridge 建立 TCP 连接
        - JSON Packet 编解码
        - command / response 配对
        - 接收 Java 主动发送的数据
    """

    def __init__(
        self,
        host: str,
        port: int,
        package_name: str,
    ):
        self.host = host
        self.port = port

        self.package_name = package_name
        self.password = Config.SERVER_PASSWORD

        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None

        self._request_id = 0
        self._pending: dict[int, asyncio.Future] = {}

        self._reader_task: asyncio.Task | None = None

        self._connected = asyncio.Event()
        self._handshaked = asyncio.Event()

        self._closing = False

        # Java → Python 的主动消息处理器。
        #
        # 例如以后 events.py 可以：
        #
        # client.set_message_handler(events.dispatch)
        #
        self._message_handler: (
            Callable[[dict[str, Any]], Awaitable[None]]
            | None
        ) = None

    # ============================================================
    # Connection
    # ============================================================

    async def connect(self) -> None:
        """
        建立 TCP 连接并执行 handshake。

        connect() 返回时意味着：

            TCP connection established
            +
            handshake successful
        """

        if self._connected.is_set():
            return

        self._closing = False

        try:
            self.reader, self.writer = await asyncio.open_connection(
                self.host,
                self.port,
            )

        except OSError as e:
            raise LapisConnectionError(
                f"Failed to connect to "
                f"{self.host}:{self.port}"
            ) from e

        self._connected.set()

        # 启动接收循环。
        self._reader_task = asyncio.create_task(
            self._reader_loop()
        )

        try:
            await self.handshake()

        except Exception:
            await self.close()
            raise

    async def close(self) -> None:
        """
        主动关闭连接。
        """

        self._closing = True

        self._connected.clear()
        self._handshaked.clear()

        # 让所有正在等待 response 的 command 结束。
        self._fail_pending_requests(
            LapisConnectionError(
                "Lapis connection closed"
            )
        )

        if self.writer is not None:
            self.writer.close()

            try:
                await self.writer.wait_closed()
            except OSError:
                pass

        self.writer = None
        self.reader = None

        if self._reader_task is not None:
            if self._reader_task is not asyncio.current_task():
                self._reader_task.cancel()

                try:
                    await self._reader_task
                except asyncio.CancelledError:
                    pass

        self._reader_task = None

    # ============================================================
    # Handshake
    # ============================================================

    async def handshake(self) -> None:
        """
        执行 Lapis handshake。

        command:

        {
            "command_type": "handshake",
            "id": 1,
            "data": {
                "package_name": "MyPackage",
                "password": "pw114514"
            }
        }
        """

        response = await self.command(
            "handshake",
            {
                "package_name": self.package_name,
                "password": self.password,
            },
        )

        # command() 已经检查了 ok。
        #
        # 这里额外检查 response_type，
        # 防止 Java 返回了错误类型的 response。

        if response["response_type"] != "handshake_ack":
            raise LapisProtocolError(
                "Unexpected handshake response type: "
                f"{response['response_type']!r}"
            )

        self._handshaked.set()

    # ============================================================
    # Command
    # ============================================================

    async def command(
        self,
        command_type: str,
        data: dict[str, Any] | None = None,
        *,
        timeout: float | None = 10,
    ) -> dict[str, Any]:
        """
        向 Java 端发送一个 command，并等待对应 response。

        例如：

            await client.command(
                "register_event_listener",
                {...}
            )

        会自动生成：

            {
                "command_type": "register_event_listener",
                "id": 2,
                "data": {...}
            }

        然后等待：

            {
                "response_type": "...",
                "id": 2,
                "ok": true,
                "data": {...}
            }
        """

        if not self._connected.is_set():
            raise LapisConnectionError(
                "Lapis client is not connected"
            )

        # 除 handshake 外，其余 command 要求已经完成 handshake。
        if (
            command_type != "handshake"
            and not self._handshaked.is_set()
        ):
            raise LapisConnectionError(
                "Lapis handshake has not completed"
            )

        self._request_id += 1
        command_id = self._request_id

        loop = asyncio.get_running_loop()

        future: asyncio.Future = loop.create_future()

        self._pending[command_id] = future

        packet = {
            "command_type": command_type,
            "id": command_id,
            "data": data if data is not None else {},
        }

        try:
            await self._send_packet(packet)

            if timeout is None:
                response = await future
            else:
                response = await asyncio.wait_for(
                    future,
                    timeout,
                )

            return response

        finally:
            r = self._pending.pop(command_id, None)

    # ============================================================
    # Packet Sending
    # ============================================================

    async def _send_packet(
        self,
        packet: dict[str, Any],
    ) -> None:
        """
        将 Python dict 编码为：

            [4-byte length][JSON payload]

        然后通过 TCP 发送。
        """

        if self.writer is None:
            raise LapisConnectionError(
                "Lapis client is not connected"
            )

        try:
            payload = json.dumps(
                packet,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")

        except (TypeError, ValueError) as e:
            raise LapisProtocolError(
                "Failed to serialize packet"
            ) from e

        if len(payload) > Config.MAX_PACKET_SIZE:
            raise LapisProtocolError(
                f"Packet too large: "
                f"{len(payload)} bytes"
            )

        # 4-byte unsigned big-endian integer。
        header = struct.pack(
            ">I",
            len(payload),
        )

        try:
            self.writer.write(header)
            self.writer.write(payload)

            await self.writer.drain()

        except (ConnectionError, OSError) as e:
            raise LapisConnectionError(
                "Failed to send packet"
            ) from e

    # ============================================================
    # Packet Receiving
    # ============================================================

    async def _read_packet(self) -> dict[str, Any]:
        """
        从 TCP Stream 中读取一个完整 Packet。
        """

        if self.reader is None:
            raise LapisConnectionError(
                "Lapis client is not connected"
            )

        try:
            # 首先读取 4-byte payload length。
            header = await self.reader.readexactly(4)

        except asyncio.IncompleteReadError as e:
            raise LapisConnectionError(
                "Connection closed while reading packet header"
            ) from e

        length = struct.unpack(
            ">I",
            header,
        )[0]

        if length > Config.MAX_PACKET_SIZE:
            raise LapisProtocolError(
                f"Packet too large: {length} bytes"
            )

        try:
            payload = await self.reader.readexactly(length)

        except asyncio.IncompleteReadError as e:
            raise LapisConnectionError(
                "Connection closed while reading packet body"
            ) from e

        try:
            packet = json.loads(
                payload.decode("utf-8")
            )

        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as e:
            raise LapisProtocolError(
                "Invalid JSON packet"
            ) from e

        if not isinstance(packet, dict):
            raise LapisProtocolError(
                "Packet root must be a JSON object"
            )

        return packet

    # ============================================================
    # Reader Loop
    # ============================================================

    async def _reader_loop(self) -> None:
        """
        持续接收 Java → Python 的 Packet。

        response:
            → _handle_response()

        其他主动消息：
            → _message_handler()
        """

        try:
            while not self._closing:
                packet = await self._read_packet()

                await self._handle_packet(packet)

        except asyncio.CancelledError:
            raise

        except Exception as e:
            await self._handle_disconnect(e)

    # ============================================================
    # Packet Dispatch
    # ============================================================

    async def _handle_packet(
        self,
        packet: dict[str, Any],
    ) -> None:
        """
        根据 Packet 类型分发。

        当前协议中：
            response_type → command response

        未来：
            event_type / notification_type / ...
            可以交给上层处理。
        """

        if "response_type" in packet:
            await self._handle_response(packet)
            return

        # 非 response 类型属于 Java 主动发送的数据。
        #
        # client.py 不应该理解这些业务数据是什么。
        #
        # 例如以后可能是：
        #
        # {
        #     "event_type": "event",
        #     ...
        # }
        #
        # 直接交给上层。

        if self._message_handler is not None:
            await self._message_handler(packet)

    # ============================================================
    # Response
    # ============================================================

    async def _handle_response(
        self,
        response: dict[str, Any],
    ) -> None:
        """
        处理 Java → Python 的 response。
        """

        if "id" not in response:
            raise LapisProtocolError(
                "Response does not contain id"
            )

        command_id = response["id"]

        if not isinstance(command_id, int):
            raise LapisProtocolError(
                "Response id must be an integer"
            )

        future = self._pending.get(command_id)

        # 可能是超时后才收到的 response。
        # 此时直接丢弃即可。
        if future is None:
            return

        if future.done():
            return

        response_type = response.get(
            "response_type"
        )

        ok = response.get("ok")

        if ok is True:
            future.set_result(response)

        elif ok is False:
            future.set_exception(
                LapisCommandError(
                    response_type=response_type,
                    command_id=command_id,
                    data=response.get("data"),
                )
            )

        else:
            future.set_exception(
                LapisProtocolError(
                    "Response field 'ok' must be boolean"
                )
            )

    # ============================================================
    # Message Handler
    # ============================================================

    def set_message_handler(
        self,
        handler: Callable[
            [dict[str, Any]],
            Awaitable[None],
        ],
    ) -> None:
        """
        设置 Java 主动消息处理器。

        例如：

            client.set_message_handler(
                events.dispatch
            )
        """

        self._message_handler = handler

    # ============================================================
    # Disconnect
    # ============================================================

    async def _handle_disconnect(
        self,
        exception: Exception | None = None,
    ) -> None:
        """
        处理非主动断线。

        v0.1 暂时只负责清理状态。
        自动重连可以在上层 Runtime 实现。
        """

        if self._closing:
            return

        self._connected.clear()
        self._handshaked.clear()

        self.reader = None
        self.writer = None

        if exception is None:
            exception = LapisConnectionError(
                "Connection to Java server was lost"
            )

        self._fail_pending_requests(
            LapisConnectionError(
                "Connection to Java server was lost"
            )
        )

    # ============================================================
    # Pending Requests
    # ============================================================

    def _fail_pending_requests(
        self,
        exception: Exception,
    ) -> None:
        """
        让所有等待中的 command 立即失败。
        """

        for future in self._pending.values():
            if not future.done():
                future.set_exception(exception)

        self._pending.clear()