好的，我们正式启动路线图的第二步。

在这一步，我们将为 `Engine` 赋予广播实时事件的能力。我们将通过在 `LocalConnector` 内部实现一个基于 Unix Domain Socket (UDS) 的 `UdsTelemetryServer` 来完成此项工作。当 `Engine` 运行时，这个服务器会监听内部的遥测事件，并将它们实时广播给任何连接的客户端（例如 `cs-observer watch`）。

## [WIP] feat(connector): 在 LocalConnector 中实现 UDS Telemetry 服务器

### 用户需求
执行“路线图：实现统一的 `local` 后端与实时 `watch` 功能”中的第二步，即“[核心机制] 实现基于 UDS 的 Telemetry 事件服务器”。这要求我们：
1.  创建一个 `UdsTelemetryServer` 类，它能够通过 UDS 广播消息。
2.  将该服务器集成到 `LocalConnector` 的生命周期中（在 `connect` 时启动，在 `disconnect` 时停止）。
3.  修改 `LocalConnector.publish` 方法，使其能够将遥测（telemetry）事件路由到 UDS 服务器进行广播，同时保持对约束（constraint）消息的数据库处理。

### 评论
这是一个关键的功能实现，它将点亮 `watch` 模式的本地后端支持。将服务器逻辑封装在 `LocalConnector` 内部是一个优雅的架构决策，它遵循了关注点分离原则：`LocalConnector` 成为了所有“本地”通信（状态持久化和实时事件）的统一网关，而无需修改 `Engine` 或 `TelemetrySubscriber` 等核心组件。

### 目标
1.  **创建新模块**: 在 `packages/cascade-connector-local/src/cascade/connectors/local/` 目录下创建一个新的 `uds_server.py` 文件，并实现 `UdsTelemetryServer` 类。该类将负责管理 UDS 服务器的生命周期和客户端连接。
2.  **集成到连接器**: 修改 `LocalConnector`，使其在非 Windows 平台上实例化 `UdsTelemetryServer`。
3.  **生命周期管理**: 在 `LocalConnector.connect()` 中启动 UDS 服务器，在 `disconnect()` 中关闭它。
4.  **事件路由**: 增强 `LocalConnector.publish()` 方法，使其能够根据主题（topic）区分遥测事件和约束更新，并将遥测事件通过 UDS 服务器广播出去。

### 基本原理
通过 `asyncio.start_unix_server`，我们可以创建一个高性能的本地 IPC 服务器。`LocalConnector` 作为 `Engine` 与外部世界（即使是本地的）的桥梁，是管理这个服务器生命周期的最合适位置。`TelemetrySubscriber` 已经会将事件发布到 `Connector`，我们只需在 `LocalConnector` 的 `publish` 方法中增加一个逻辑分支，即可将这些事件“重定向”到 UDS，从而以最小的侵入性实现功能。所有 UDS 相关代码都将受到平台检查的保护，以确保在 Windows 系统上不会执行。

### 标签
#intent/build #flow/ready #priority/high #comp/engine #concept/sync #scope/core #ai/instruct #task/domain/storage #task/object/uds-server #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 创建 UDS 服务器实现

我们首先创建 `uds_server.py` 文件。这个类包含了启动/停止服务器、处理新客户端连接以及向所有已连接客户端广播消息的全部逻辑。

~~~~~act
write_file
packages/cascade-connector-local/src/cascade/connectors/local/uds_server.py
~~~~~
~~~~~python
import asyncio
import json
import sys
from pathlib import Path
from typing import List, Set


class UdsTelemetryServer:
    """
    A server that broadcasts telemetry messages over a Unix Domain Socket.
    """

    def __init__(self, uds_path: str):
        self.uds_path = Path(uds_path)
        self._server: asyncio.Server | None = None
        self._clients: Set[asyncio.StreamWriter] = set()

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        """Callback for new client connections."""
        self._clients.add(writer)
        try:
            # Keep connection open until client closes it or an error occurs
            await reader.read(1)  # Wait for EOF or data
        except (ConnectionResetError, BrokenPipeError):
            pass  # Client disconnected
        finally:
            if not writer.is_closing():
                writer.close()
                await writer.wait_closed()
            self._clients.discard(writer)

    async def start(self):
        """Starts the UDS server."""
        if self._server:
            return
        # Ensure the socket file does not exist from a previous unclean shutdown
        self.uds_path.unlink(missing_ok=True)
        self._server = await asyncio.start_unix_server(
            self._handle_client, path=str(self.uds_path)
        )

    async def stop(self):
        """Stops the server and disconnects all clients."""
        if not self._server:
            return

        # Close the main server socket
        self._server.close()
        await self._server.wait_closed()
        self._server = None

        # Disconnect all active clients
        for writer in list(self._clients):
            if not writer.is_closing():
                writer.close()
                await writer.wait_closed()
        self._clients.clear()

        # Clean up the socket file
        self.uds_path.unlink(missing_ok=True)

    async def broadcast(self, message: dict):
        """Broadcasts a JSON-lined message to all connected clients."""
        if not self._clients:
            return

        # Serialize once
        try:
            json_line = (json.dumps(message) + "\n").encode("utf-8")
        except TypeError:
            # Ignore non-serializable messages silently
            return

        dead_clients = set()
        for writer in self._clients:
            if writer.is_closing():
                dead_clients.add(writer)
                continue
            try:
                writer.write(json_line)
                await writer.drain()
            except (ConnectionResetError, BrokenPipeError):
                dead_clients.add(writer)

        # Clean up any clients that disconnected during broadcast
        for writer in dead_clients:
            self._clients.discard(writer)
~~~~~

#### Acts 2: 将 UDS 服务器集成到 LocalConnector

现在，我们修改 `LocalConnector` 来管理 `UdsTelemetryServer` 的生命周期，并路由遥测事件。

~~~~~act
patch_file
packages/cascade-connector-local/src/cascade/connectors/local/connector.py
~~~~~
~~~~~python
import asyncio
import json
import sqlite3
import time
import sys
import socket
from pathlib import Path
from typing import Callable, Awaitable, Dict, Any, List

from cascade.spec.protocols import Connector, SubscriptionHandle
~~~~~
~~~~~python
import asyncio
import json
import sqlite3
import time
import sys
import socket
from pathlib import Path
from typing import Callable, Awaitable, Dict, Any, List

from cascade.spec.protocols import Connector, SubscriptionHandle
from .uds_server import UdsTelemetryServer
~~~~~

~~~~~act
patch_file
packages/cascade-connector-local/src/cascade/connectors/local/connector.py
~~~~~
~~~~~python
DEFAULT_UDS_PATH = "/tmp/cascade.sock"
~~~~~
~~~~~python
DEFAULT_UDS_PATH = "/tmp/cascade.sock"
DEFAULT_TELEMETRY_UDS_PATH = "/tmp/cascade-telemetry.sock"
~~~~~

~~~~~act
patch_file
packages/cascade-connector-local/src/cascade/connectors/local/connector.py
~~~~~
~~~~~python
class LocalConnector(Connector):
    def __init__(
        self,
        db_path: str = "~/.cascade/control.db",
        uds_path: str = DEFAULT_UDS_PATH,
    ):
        self.db_path = Path(db_path).expanduser()
        self.uds_path = uds_path
        self._conn: sqlite3.Connection | None = None
        self._is_connected = False
        self._background_tasks: List[asyncio.Task] = []
        self._last_known_constraints: Dict[str, Dict[str, Any]] = {}
        self._use_polling = sys.platform == "win32"
        self._uds_recv_event = asyncio.Event()

    async def connect(self) -> None:
        def _connect_and_setup():
~~~~~
~~~~~python
class LocalConnector(Connector):
    def __init__(
        self,
        db_path: str = "~/.cascade/control.db",
        uds_path: str = DEFAULT_UDS_PATH,
        telemetry_uds_path: str = DEFAULT_TELEMETRY_UDS_PATH,
    ):
        self.db_path = Path(db_path).expanduser()
        self.uds_path = uds_path
        self._conn: sqlite3.Connection | None = None
        self._is_connected = False
        self._background_tasks: List[asyncio.Task] = []
        self._last_known_constraints: Dict[str, Dict[str, Any]] = {}
        self._use_polling = sys.platform == "win32"
        self._uds_recv_event = asyncio.Event()

        # UDS Telemetry Server (only for non-Windows platforms)
        self._telemetry_server: UdsTelemetryServer | None = None
        if not self._use_polling:
            self._telemetry_server = UdsTelemetryServer(telemetry_uds_path)

    async def connect(self) -> None:
        # Start telemetry server if it exists
        if self._telemetry_server:
            await self._telemetry_server.start()

        def _connect_and_setup():
~~~~~

~~~~~act
patch_file
packages/cascade-connector-local/src/cascade/connectors/local/connector.py
~~~~~
~~~~~python
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
            self._background_tasks.clear()
        if self._conn:
            await asyncio.to_thread(self._conn.close)
            self._conn = None
~~~~~
~~~~~python
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
            self._background_tasks.clear()

        # Stop telemetry server
        if self._telemetry_server:
            await self._telemetry_server.stop()

        if self._conn:
            await asyncio.to_thread(self._conn.close)
            self._conn = None
~~~~~

~~~~~act
patch_file
packages/cascade-connector-local/src/cascade/connectors/local/connector.py
~~~~~
~~~~~python
    async def publish(self, topic: str, payload: Dict[str, Any], **kwargs) -> None:
        if not self._is_connected:
            raise RuntimeError("Connector is not connected.")
        scope = self._topic_to_scope(topic)

        def _blocking_publish():
            cursor = self._conn.cursor()
            if not payload:
                cursor.execute("DELETE FROM constraints WHERE scope = ?", (scope,))
            else:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO constraints (id, scope, type, params, expires_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        payload["id"],
                        payload["scope"],
                        payload["type"],
                        json.dumps(payload["params"]),
                        payload.get("expires_at"),
                        time.time(),
                    ),
                )
            self._conn.commit()

        await asyncio.to_thread(_blocking_publish)

        if not self._use_polling:
            await self._send_uds_signal()
~~~~~
~~~~~python
    async def publish(self, topic: str, payload: Dict[str, Any], **kwargs) -> None:
        if not self._is_connected:
            raise RuntimeError("Connector is not connected.")

        # Route message based on topic
        if topic.startswith("cascade/telemetry/"):
            if self._telemetry_server:
                await self._telemetry_server.broadcast(payload)
            return

        if topic.startswith("cascade/constraints/"):
            scope = self._topic_to_scope(topic)

            def _blocking_publish():
                cursor = self._conn.cursor()
                if not payload:
                    cursor.execute("DELETE FROM constraints WHERE scope = ?", (scope,))
                else:
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO constraints (id, scope, type, params, expires_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            payload["id"],
                            payload["scope"],
                            payload["type"],
                            json.dumps(payload["params"]),
                            payload.get("expires_at"),
                            time.time(),
                        ),
                    )
                self._conn.commit()

            await asyncio.to_thread(_blocking_publish)

            if not self._use_polling:
                await self._send_uds_signal()
~~~~~

### 下一步建议
我们已经成功地在 `LocalConnector` 中实现了 UDS Telemetry 服务器的骨架，并完成了与 `Engine` 的集成。当 `Engine` 运行时，它现在应该会在文件系统上创建一个 UDS socket 文件，并准备好接受 `watch` 客户端的连接。

下一步是 **步骤 3: [功能闭环] 实现 `cs-observer watch` 的 UDS 客户端**。这将使 `cs-observer` 能够连接到我们刚刚创建的服务器，并实时接收和渲染遥测事件流。
