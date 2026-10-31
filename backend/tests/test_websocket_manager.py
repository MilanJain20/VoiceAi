"""
WebSocket manager unit tests.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.websocket.connection import ConnectionState, VoiceConnection
from app.websocket.manager import ConnectionManager
from app.schemas.websocket import WSMessage, WSMessageType


@pytest.mark.asyncio
async def test_connection_manager_connect_disconnect() -> None:
    manager = ConnectionManager()

    # Create a mock WebSocket
    mock_ws = AsyncMock()
    mock_ws.accept = AsyncMock()
    mock_ws.client_state = MagicMock()

    conn = VoiceConnection(mock_ws, session_id="test-session-1")

    await manager.connect(conn)
    assert manager.active_count == 1
    assert manager.get_connection("test-session-1") is conn

    await manager.disconnect("test-session-1")
    assert manager.active_count == 0
    assert manager.get_connection("test-session-1") is None


@pytest.mark.asyncio
async def test_connection_manager_replaces_duplicate_session() -> None:
    manager = ConnectionManager()

    mock_ws1 = AsyncMock()
    mock_ws1.accept = AsyncMock()
    mock_ws1.client_state = MagicMock()

    mock_ws2 = AsyncMock()
    mock_ws2.accept = AsyncMock()
    mock_ws2.client_state = MagicMock()

    conn1 = VoiceConnection(mock_ws1, session_id="dup-session")
    conn2 = VoiceConnection(mock_ws2, session_id="dup-session")

    await manager.connect(conn1)
    await manager.connect(conn2)

    assert manager.active_count == 1
    assert manager.get_connection("dup-session") is conn2


@pytest.mark.asyncio
async def test_connection_cancel_and_reset() -> None:
    mock_ws = AsyncMock()
    conn = VoiceConnection(mock_ws, session_id="cancel-test")

    assert not conn.is_cancelled
    conn.cancel()
    assert conn.is_cancelled
    conn.reset_cancel()
    assert not conn.is_cancelled


@pytest.mark.asyncio
async def test_metrics() -> None:
    manager = ConnectionManager()
    metrics = manager.get_metrics()
    assert metrics["active_connections"] == 0
    assert metrics["total_served"] == 0
