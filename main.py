from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from redis.asyncio import Redis

from api.api_handlers import router as api_router
from api.auth_handlers import api_router as auth_api_router, html_router as auth_html_router
from api.handlers import router as html_router
from core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    app.state.session_cookie_name = settings.SESSION_COOKIE_NAME
    try:
        yield
    finally:
        await app.state.redis.aclose()


app = FastAPI(
    title="Greenhouse Gases",
    description=(
        "Сервис прогнозирования изменения температуры Земли "
        "в зависимости от содержания парниковых газов в атмосфере. "
        "ЛР4: регистрация, cookie-аутентификация, роли и Redis-сессии."
    ),
    version="4.0.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(auth_html_router)
app.include_router(html_router)
app.include_router(api_router)
app.include_router(auth_api_router)


@app.get("/health", tags=["System"])
async def health():
    return {"status": "ok", "service": "greenhouse-gases"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
