import uuid
import logging
from typing import Callable, Awaitable

from anyio import ClosedResourceError
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Populate request.state with request_id and user."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        user = request.headers.get("X-User", "anonymous")
        request.state.request_id = request_id
        request.state.user = user
        response = await call_next(request)
        response.headers.setdefault("X-Request-ID", request_id)
        return response


def closed_resource_handler(
    endpoint_name: str,
) -> Callable[[Callable[..., Awaitable]], Callable[..., Awaitable]]:
    """Decorator to handle ClosedResourceError uniformly."""

    def decorator(func: Callable[..., Awaitable]):
        async def wrapper(*args, **kwargs):
            request: Request = kwargs.get("request")
            try:
                return await func(*args, **kwargs)
            except ClosedResourceError:
                request_id = (
                    getattr(request.state, "request_id", "unknown")
                    if request
                    else "unknown"
                )
                user = (
                    getattr(request.state, "user", "anonymous")
                    if request
                    else "anonymous"
                )
                logger.warning(
                    f"MCP connection closed while calling {endpoint_name} "
                    f"(request_id={request_id}, user={user})"
                )
                raise HTTPException(
                    status_code=503,
                    detail={
                        "message": (
                            "MCP server connection closed. "
                            "Please retry your request after a short delay. "
                            "If the problem persists, contact support."
                        )
                    },
                    headers={"Retry-After": "10"},
                )

        return wrapper

    return decorator
