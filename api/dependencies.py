import json

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from models.user import User
from repositories.user import get_user_by_id
from core.redis_sessions import run_session_script


async def _user_from_session_token(
    request: Request,
    token: str,
    session: AsyncSession,
) -> User | None:
    """Resolve a user from the Redis session cookie, if it is valid."""
    redis = getattr(request.app.state, "redis", None)
    if redis is None:
        return None

    try:
        raw = await run_session_script(request, "GET", f"session:{token}")
    except Exception:
        # Public GET endpoints must remain readable if session storage is
        # temporarily unavailable; protected endpoints handle this below.
        return None

    if not raw:
        return None

    try:
        payload = json.loads(raw)
        user_id = int(payload["user_id"])
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        try:
            await run_session_script(request, "DEL", f"session:{token}")
        except Exception:
            pass
        return None

    user = await get_user_by_id(session, user_id)
    if user is None:
        try:
            await run_session_script(request, "DEL", f"session:{token}")
        except Exception:
            pass
        return None
    return user


async def get_optional_current_user(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> User | None:
    """Return the current user when a valid session exists, otherwise None.

    Intended for public read-only endpoints: missing, expired, or invalid
    cookies must not prevent anonymous users from reading published content.
    """
    token = request.cookies.get(request.app.state.session_cookie_name)
    if not token:
        return None
    return await _user_from_session_token(request, token, session)


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> User:
    token = request.cookies.get(request.app.state.session_cookie_name)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется авторизация",
        )

    redis = getattr(request.app.state, "redis", None)
    if redis is None:
        raise HTTPException(status_code=503, detail="Хранилище сессий недоступно")

    try:
        user = await _user_from_session_token(request, token, session)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Не удалось проверить сессию") from exc

    if user is None:
        # Distinguish an unavailable Redis store from an invalid/expired token.
        try:
            await redis.ping()
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Хранилище сессий недоступно") from exc
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Сессия истекла или недействительна",
        )
    return user


async def get_optional_current_user_id(
    user: User | None = Depends(get_optional_current_user),
) -> int | None:
    return user.id if user is not None else None


async def get_current_user_id(user: User = Depends(get_current_user)) -> int:
    return user.id


async def require_moderator(user: User = Depends(get_current_user)) -> User:
    if user.role != "moderator":
        raise HTTPException(status_code=403, detail="Требуются права модератора")
    return user
