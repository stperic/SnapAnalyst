"""
SnapAnalyst FastAPI Dependencies

Shared dependencies for API endpoints.
"""

from collections.abc import Generator
from contextvars import ContextVar

from sqlalchemy.orm import Session

from src.database.engine import get_db

# Thread-safe request context for user identification
# ContextVar is preferred over threading.local() for asyncio compatibility
_request_user_id: ContextVar[str | None] = ContextVar("request_user_id", default=None)


def set_request_user(user_id: str) -> None:
    """
    Set user ID for current request context.

    Thread-safe: Uses ContextVar which works correctly with asyncio and threads.

    Args:
        user_id: User identifier for this request
    """
    _request_user_id.set(user_id)


def get_request_user() -> str | None:
    """
    Get user ID from current request context.

    Returns:
        User ID for this request, or None if not set
    """
    return _request_user_id.get()


def get_database() -> Generator[Session, None, None]:
    """
    FastAPI dependency to get database session.

    Yields:
        Database session

    Example:
        @app.get("/items")
        async def get_items(db: Session = Depends(get_database)):
            return db.query(Item).all()
    """
    yield from get_db()


async def verify_api_key(api_key: str = None) -> bool:
    """
    Verify API key (placeholder for future authentication).

    Args:
        api_key: API key from header

    Returns:
        True if valid, raises HTTPException otherwise
    """
    # TODO: Implement actual API key verification
    # For now, allow all requests in development
    return True


async def rate_limit_check() -> bool:
    """
    Check rate limiting (placeholder for future implementation).

    Returns:
        True if within rate limit, raises HTTPException otherwise
    """
    # TODO: Implement actual rate limiting with Redis
    return True
