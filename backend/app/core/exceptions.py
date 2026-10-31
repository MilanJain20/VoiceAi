"""
Application exception hierarchy and error handlers.

Structured exceptions enable consistent API error responses
and proper error propagation across the WebSocket pipeline.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import ORJSONResponse


class VoiceAIError(Exception):
    """Base exception for all application errors."""

    def __init__(
        self,
        message: str = "An internal error occurred",
        status_code: int = 500,
        error_code: str = "INTERNAL_ERROR",
        details: dict[str, Any] | None = None,
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)


class AuthenticationError(VoiceAIError):
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message=message, status_code=401, error_code="AUTH_FAILED")


class AuthorizationError(VoiceAIError):
    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(message=message, status_code=403, error_code="FORBIDDEN")


class NotFoundError(VoiceAIError):
    def __init__(self, resource: str = "Resource", identifier: str = ""):
        msg = f"{resource} not found"
        if identifier:
            msg = f"{resource} '{identifier}' not found"
        super().__init__(message=msg, status_code=404, error_code="NOT_FOUND")


class ValidationError(VoiceAIError):
    def __init__(self, message: str = "Validation failed", details: dict[str, Any] | None = None):
        super().__init__(
            message=message, status_code=422, error_code="VALIDATION_ERROR", details=details
        )


class RateLimitError(VoiceAIError):
    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(message=message, status_code=429, error_code="RATE_LIMITED")


class ServiceUnavailableError(VoiceAIError):
    def __init__(self, service: str = "External service"):
        super().__init__(
            message=f"{service} is currently unavailable",
            status_code=503,
            error_code="SERVICE_UNAVAILABLE",
        )


class WebSocketError(VoiceAIError):
    """Errors occurring within WebSocket sessions."""

    def __init__(self, message: str = "WebSocket error", error_code: str = "WS_ERROR"):
        super().__init__(message=message, status_code=1011, error_code=error_code)


class STTError(VoiceAIError):
    def __init__(self, message: str = "Speech-to-text processing failed"):
        super().__init__(message=message, error_code="STT_ERROR")


class TTSError(VoiceAIError):
    def __init__(self, message: str = "Text-to-speech processing failed"):
        super().__init__(message=message, error_code="TTS_ERROR")


class LLMError(VoiceAIError):
    def __init__(self, message: str = "Language model processing failed"):
        super().__init__(message=message, error_code="LLM_ERROR")


def register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers on the FastAPI app."""

    @app.exception_handler(VoiceAIError)
    async def voice_ai_error_handler(request: Request, exc: VoiceAIError) -> ORJSONResponse:
        return ORJSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.error_code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> ORJSONResponse:
        from app.core.logging import get_logger

        logger = get_logger(__name__)
        logger.error("unhandled_exception", exc_info=exc, path=str(request.url))
        return ORJSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred",
                    "details": {},
                }
            },
        )
