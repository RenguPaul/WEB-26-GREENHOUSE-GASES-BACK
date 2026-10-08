from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from api.api_handlers import router as api_router
from api.handlers import router


app = FastAPI(
    title="Greenhouse Gases",
    description=(
        "Сервис прогнозирования изменения температуры Земли "
        "в зависимости от содержания парниковых газов "
        "в атмосфере."
    ),
)


app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static",
)


# ЛР2: HTML/Jinja2 интерфейс
app.include_router(router)

# ЛР3: REST API
app.include_router(api_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )