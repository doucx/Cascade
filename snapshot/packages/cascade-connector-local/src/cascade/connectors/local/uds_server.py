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