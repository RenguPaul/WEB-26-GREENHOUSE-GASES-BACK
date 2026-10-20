import json
import secrets

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, require_moderator
from core.config import settings
from core.security import hash_password, verify_password
from db.session import get_db
from models.user import User
from repositories.user import create_user, get_user_by_username, list_users
from schemas.user import AuthResponse, UserLoginRequest, UserPublic, UserRegisterRequest, UserRegisterResponse

api_router = APIRouter(prefix="/api/users", tags=["Users and authentication"])
html_router = APIRouter(tags=["HTML authentication"])
templates = Jinja2Templates(directory="templates")


async def _create_session(request: Request, response: Response, user: User) -> None:
    redis = getattr(request.app.state, "redis", None)
    if redis is None:
        raise HTTPException(status_code=503, detail="Хранилище сессий Redis недоступно")
    token = secrets.token_urlsafe(32)
    payload = json.dumps({"user_id": user.id})
    await redis.setex(f"session:{token}", settings.SESSION_TTL_SECONDS, payload)
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=token,
        max_age=settings.SESSION_TTL_SECONDS,
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite="lax",
        path="/",
    )


async def _delete_session(request: Request, response: Response) -> None:
    token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    redis = getattr(request.app.state, "redis", None)
    if token and redis is not None:
        await redis.delete(f"session:{token}")
    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite="lax",
    )


async def _verify_user_password(session: AsyncSession, user: User, password: str) -> bool:
    if verify_password(password, user.password):
        return True
    # Совместимость с пользователями из предыдущей лабораторной,
    # где пароль мог быть сохранён открытым текстом. При успешном входе
    # сразу заменяем его на scrypt-хеш.
    if not user.password.startswith("scrypt$") and secrets.compare_digest(password, user.password):
        user.password = hash_password(password)
        await session.commit()
        return True
    return False


async def _register(session: AsyncSession, request: UserRegisterRequest) -> User:
    username = request.username.strip()
    if len(username) < 3:
        raise HTTPException(status_code=400, detail="Имя пользователя должно содержать не менее 3 символов")
    if await get_user_by_username(session, username):
        raise HTTPException(status_code=409, detail="Пользователь с таким именем уже существует")
    # Обычная регистрация никогда не выдаёт права модератора автоматически.
    return await create_user(session, username, hash_password(request.password), role="user")


@api_router.post(
    "/register",
    response_model=UserRegisterResponse,
    status_code=201,
    summary="Зарегистрировать пользователя",
    description="Создаёт учётную запись. Пароль сохраняется в виде scrypt-хеша; роль user назначается автоматически.",
    responses={400: {"description": "Некорректное имя пользователя"}, 409: {"description": "Имя уже занято"}},
)
async def register_user(data: UserRegisterRequest, session: AsyncSession = Depends(get_db)):
    user = await _register(session, data)
    return UserRegisterResponse(id=user.id, username=user.username, role=user.role)


@api_router.post(
    "/auth",
    response_model=AuthResponse,
    summary="Войти и создать сессию",
    description="Проверяет имя и пароль, сохраняет серверную сессию в Redis и устанавливает HttpOnly cookie greenhouse_session.",
    responses={401: {"description": "Неверное имя пользователя или пароль"}, 503: {"description": "Хранилище сессий недоступно"}},
)
async def authenticate_user(data: UserLoginRequest, request: Request, response: Response, session: AsyncSession = Depends(get_db)):
    user = await get_user_by_username(session, data.username.strip())
    if user is None or not await _verify_user_password(session, user, data.password):
        raise HTTPException(status_code=401, detail="Неверное имя пользователя или пароль")
    await _create_session(request, response, user)
    return AuthResponse(message="Вход выполнен", user_id=user.id, username=user.username, role=user.role)


@api_router.post(
    "/deauth",
    summary="Выйти из учётной записи",
    description="Удаляет серверную сессию из Redis и очищает cookie.",
)
async def deauthenticate_user(request: Request, response: Response):
    await _delete_session(request, response)
    return {"message": "Выход выполнен"}


@api_router.get(
    "/me",
    response_model=UserPublic,
    summary="Получить текущего пользователя",
    description="Требуется действующая cookie greenhouse_session.",
    responses={401: {"description": "Не выполнен вход или сессия недействительна"}},
)
async def current_user(user: User = Depends(get_current_user)):
    return user


@api_router.get(
    "/moderators/users",
    response_model=list[UserPublic],
    summary="Получить пользователей (только модератор)",
    description="Требуется действующая сессия пользователя с ролью moderator.",
    responses={401: {"description": "Не выполнен вход"}, 403: {"description": "Недостаточно прав"}},
)
async def moderator_users(session: AsyncSession = Depends(get_db), moderator: User = Depends(require_moderator)):
    return await list_users(session)


@html_router.get("/auth/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse(request=request, name="auth_register.html", context={"request": request, "error": None})


@html_router.post("/auth/register", response_class=HTMLResponse)
async def register_page_submit(request: Request, username: str = Form(...), password: str = Form(...), session: AsyncSession = Depends(get_db)):
    try:
        data = UserRegisterRequest(username=username, password=password)
        user = await _register(session, data)
    except HTTPException as exc:
        return templates.TemplateResponse(request=request, name="auth_register.html", context={"request": request, "error": exc.detail}, status_code=exc.status_code)
    except Exception:
        return templates.TemplateResponse(request=request, name="auth_register.html", context={"request": request, "error": "Проверьте введённые данные"}, status_code=400)
    return RedirectResponse(url="/auth/login?registered=1", status_code=status.HTTP_303_SEE_OTHER)


@html_router.get("/auth/login", response_class=HTMLResponse)
async def login_page(request: Request, registered: int = 0):
    return templates.TemplateResponse(request=request, name="auth_login.html", context={"request": request, "error": None, "registered": bool(registered)})


@html_router.post("/auth/login", response_class=HTMLResponse)
async def login_page_submit(request: Request, username: str = Form(...), password: str = Form(...), session: AsyncSession = Depends(get_db)):
    user = await get_user_by_username(session, username.strip())
    if user is None or not await _verify_user_password(session, user, password):
        return templates.TemplateResponse(request=request, name="auth_login.html", context={"request": request, "error": "Неверное имя пользователя или пароль", "registered": False}, status_code=401)
    response = RedirectResponse(url="/greenhouse-gases/catalog", status_code=status.HTTP_303_SEE_OTHER)
    await _create_session(request, response, user)
    return response


@html_router.post("/auth/logout")
async def logout_page(request: Request):
    response = RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)
    await _delete_session(request, response)
    return response
