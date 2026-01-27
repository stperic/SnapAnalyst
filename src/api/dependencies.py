"""
SnapAnalyst FastAPI Dependencies

Shared dependencies for API endpoints.
"""
from collections.abc import Generator

from sqlalchemy.orm import Session

from src.database.engine import get_db


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
