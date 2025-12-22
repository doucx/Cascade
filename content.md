## [WIP] fix: 修复 UdsTelemetryServer 关闭时的死锁问题

### 错误分析
`UdsTelemetryServer.stop()` 在等待服务器关闭 (`wait_closed`) 之前没有主动关闭现有的客户端连接。这导致在 E2E 测试中，当后台客户端保持连接时，`engine.run()` 会在清理阶段无限期挂起，造成死锁。

### 用户需求
修复 `tests/cli/e2e/test_e2e_watch_local_backend.py` 测试挂起的问题。

### 评论
这是一个在编写异步服务器时常见的陷阱。服务器的优雅退出不仅需要停止接受新连接，还需要妥善处理或强制结束现有连接。

### 目标
1.  修改 `packages/cascade-connector-local/src/cascade/connectors/local/uds_server.py`。
2.  调整 `stop()` 方法的顺序：先遍历并关闭 `self._clients` 中的所有 `writer`，然后再执行 `await self._server.wait_closed()`。

### 基本原理
通过先关闭客户端 `writer`，我们触发了客户端侧的连接关闭流程。对于服务器侧的 `_handle_client` 协程，这将导致其等待逻辑返回或抛出异常，从而结束处理函数。一旦所有处理函数结束且连接断开，`self._server.wait_closed()` 就能立即完成，打破死锁。

### 标签
#intent/fix #flow/ready #priority/critical #comp/engine #concept/sync #scope/core #ai/instruct #task/domain/storage #task/object/uds-server #task/action/bug-fix #task/state/continue

---

### Script

#### Acts 1: 优化 UDS 服务器停止逻辑

我们将重写 `stop` 方法，确保先清理客户端。

~~~~~act
patch_file
packages/cascade-connector-local/src/cascade/connectors/local/uds_server.py
~~~~~
~~~~~python
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
~~~~~
~~~~~python
    async def stop(self):
        """Stops the server and disconnects all clients."""
        if not self._server:
            return

        # 1. Stop accepting new connections
        self._server.close()

        # 2. Forcefully disconnect all active clients to unblock wait_closed()
        for writer in list(self._clients):
            try:
                if not writer.is_closing():
                    writer.close()
                    # We don't await wait_closed() here individually to avoid 
                    # sequential blocking; the server's wait_closed will handle it.
            except Exception:
                pass
        self._clients.clear()

        # 3. Now wait for the server and its handlers to fully wind down
        await self._server.wait_closed()
        self._server = None

        # 4. Clean up the socket file
        self.uds_path.unlink(missing_ok=True)
~~~~~

### 下一步建议

修复此逻辑后，`test_watch_local_uds_e2e` 应该能够顺利完成。我建议再次运行该测试。

如果测试通过，我们将完成路线图的最后一步，并准备最后的 `[COMMIT]`。
