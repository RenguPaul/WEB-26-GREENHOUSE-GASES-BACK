import json

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from models.user import User
from repositories.user import get_user_by_id


async def get_current_user(request: Request, session: AsyncSession = Depends(get_db)) -> User:
    token = request.cookies.get(request.app.state.session_cookie_name)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Требуется авторизация")
    redis = getattr(request.app.state, "redis", None)
    if redis is None:
        raise HTTPException(status_code=503, detail="Хранилище сессий недоступно")
    raw = await redis.get(f"session:{token}")
    if not raw:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Сессия истекла или недействительна")
    try:
        payload = json.loads(raw)
        user_id = int(payload["user_id"])
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        await redis.delete(f"session:{token}")
        raise HTTPException(status_code=401, detail="Недействительная сессия")
    user = await get_user_by_id(session, user_id)
    if user is None:
        await redis.delete(f"session:{token}")
        raise HTTPException(status_code=401, detail="Пользователь не найден")
    return user


async def get_current_user_id(user: User = Depends(get_current_user)) -> int:
    return user.id


async def require_moderator(user: User = Depends(get_current_user)) -> User:
    if user.role != "moderator":
        raise HTTPException(status_code=403, detail="Требуются права модератора")
    return user
