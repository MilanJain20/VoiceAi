"""
FastAPI middleware stack.

Includes:
- CORS configuration
- Request ID injection (for distributed tracing)
- Request timing
- Structured request logging

IMPORTANT: Uses raw ASGI middleware (not BaseHTTPMiddleware) because
BaseHTTPMiddleware is fundamentally incompatible with WebSocket
connections — it wraps the ASGI scope/receive/send in a way that
breaks the WebSocket upgrade handshake.
"""

from __future__ import annotations

import time
import uuid

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import Settings


def setup_middleware(app: FastAPI, settings: Settings) -> None:
    """Register all middleware on the FastAPI app."""

    # CORS — must be first so preflight requests are handled before other middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.backend_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Custom ASGI middleware (applied in reverse order — last added runs first)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RequestIdMiddleware)


class RequestIdMiddleware:
    """
    Inject a unique request ID into every HTTP request for tracing.
    WebSocket connections pass through untouched.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Extract request ID from headers or generate one
        headers = dict(scope.get("headers", []))
        request_id = (headers.get(b"x-request-id", b"") or b"").decode() or str(uuid.uuid4())

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        async def send_with_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                response_headers = list(message.get("headers", []))
                response_headers.append((b"x-request-id", request_id.encode()))
                message["headers"] = response_headers
            await send(message)

        await self.app(scope, receive, send_with_id)


class RequestLoggingMiddleware:
    """
    Log every HTTP request with timing information.
    WebSocket connections pass through untouched.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        logger = structlog.get_logger("http")
        start = time.perf_counter()
        status_code = 0

        async def send_with_timing(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", 0)
                duration_ms = round((time.perf_counter() - start) * 1000, 2)
                response_headers = list(message.get("headers", []))
                response_headers.append((b"x-response-time-ms", str(duration_ms).encode()))
                message["headers"] = response_headers
            await send(message)

        await self.app(scope, receive, send_with_timing)

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        path = scope.get("path", "")

        # Skip noisy health check logs
        if path not in ("/health", "/healthz", "/ready"):
            client = scope.get("client")
            logger.info(
                "http_request",
                method=scope.get("method", ""),
                path=path,
                status=status_code,
                duration_ms=duration_ms,
                client=client[0] if client else "unknown",
            )
