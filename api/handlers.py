import math

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from db.session import async_session_maker
from repositories.greenhouse_gas import (
    create_draft_greenhouse_gas,
    delete_greenhouse_gas,
    get_draft_greenhouse_gas,
    get_likes_counts,
    get_published_greenhouse_gases,
    publish_greenhouse_gas,
)


router = APIRouter()
templates = Jinja2Templates(directory="templates")


CURRENT_USER_ID = 1

DEFAULT_IMAGE_URL = "/static/media/default-greenhouse.svg"
DEFAULT_VIDEO_URL = "/static/media/default-greenhouse.mp4"

REFERENCE_CO2_PPM = 280.0
CLIMATE_SENSITIVITY_C = 3.0


def calculate_temperature_change(
    concentration_ppm: float,
) -> float:
    """
    Упрощённый расчёт изменения средней температуры
    относительно базовой концентрации CO₂ = 280 ppm.

    ΔT = S * log2(C / C0)

    S  = 3 °C
    C0 = 280 ppm
    """

    if concentration_ppm <= 0:
        return 0.0

    return round(
        CLIMATE_SENSITIVITY_C
        * math.log2(
            concentration_ppm / REFERENCE_CO2_PPM
        ),
        1,
    )


def get_media_url(
    value: str | None,
    default_url: str,
) -> str:
    if value and value.strip():
        return value

    return default_url


def serialize_greenhouse_gas(
    greenhouse_gas,
    likes_count: int = 0,
) -> dict:
    return {
        "id": greenhouse_gas.id,
        "name": greenhouse_gas.name,
        "formula": greenhouse_gas.formula,
        "global_warming_potential_100y": (
            greenhouse_gas.global_warming_potential_100y
        ),
        "short_description": greenhouse_gas.short_description,
        "status": greenhouse_gas.status,
        "image_url": get_media_url(
            greenhouse_gas.image_url,
            DEFAULT_IMAGE_URL,
        ),
        "video_url": get_media_url(
            greenhouse_gas.video_url,
            DEFAULT_VIDEO_URL,
        ),
        "concentration_ppm": greenhouse_gas.concentration_ppm,
        "temperature_change_c": greenhouse_gas.temperature_change_c,
        "likes_count": likes_count,
    }


# =========================================================
# POST: УДАЛЕНИЕ
# =========================================================

@router.post(
    "/greenhouse-gases/{greenhouse_gas_id}/delete",
)
async def delete_greenhouse_gas_request(
    greenhouse_gas_id: int,
):
    async with async_session_maker() as session:
        await delete_greenhouse_gas(
            session=session,
            greenhouse_gas_id=greenhouse_gas_id,
        )

    return JSONResponse(
        content={
            "message": "Парниковый газ удалён",
            "id": greenhouse_gas_id,
        }
    )


# =========================================================
# GET: СТРАНИЦА СОЗДАНИЯ / ПУБЛИКАЦИИ
# =========================================================

@router.get(
    "/greenhouse-gases/request",
    response_class=HTMLResponse,
)
async def get_greenhouse_gas_request(
    request: Request,
):
    async with async_session_maker() as session:
        draft = await get_draft_greenhouse_gas(
            session=session,
            creator_id=CURRENT_USER_ID,
        )

        published = await get_published_greenhouse_gases(
            session=session,
        )

    greenhouse_gas = None

    if draft is not None:
        greenhouse_gas = serialize_greenhouse_gas(
            draft
        )

    first_greenhouse_gas_id = (
        published[0].id
        if published
        else None
    )

    return templates.TemplateResponse(
        request=request,
        name="greenhouse_gas_request.html",
        context={
            "request": request,
            "greenhouse_gas": greenhouse_gas,
            "first_greenhouse_gas_id": first_greenhouse_gas_id,
        },
    )


# =========================================================
# POST: СОЗДАНИЕ ЧЕРНОВИКА
# =========================================================

@router.post(
    "/greenhouse-gases/request",
    response_class=HTMLResponse,
)
async def create_greenhouse_gas_request(
    request: Request,
):
    form = await request.form()

    name = str(
        form.get("name", "")
    ).strip()

    if not name:
        raise HTTPException(
            status_code=400,
            detail="Название парникового газа не указано",
        )

    async with async_session_maker() as session:
        existing_draft = await get_draft_greenhouse_gas(
            session=session,
            creator_id=CURRENT_USER_ID,
        )

        if existing_draft is not None:
            greenhouse_gas = serialize_greenhouse_gas(
                existing_draft
            )

            return templates.TemplateResponse(
                request=request,
                name="greenhouse_gas_request.html",
                context={
                    "request": request,
                    "greenhouse_gas": greenhouse_gas,
                },
            )

        draft = await create_draft_greenhouse_gas(
            session=session,
            name=name,
            creator_id=CURRENT_USER_ID,
        )

    greenhouse_gas = serialize_greenhouse_gas(
        draft
    )

    return templates.TemplateResponse(
        request=request,
        name="greenhouse_gas_request.html",
        context={
            "request": request,
            "greenhouse_gas": greenhouse_gas,
        },
    )


# =========================================================
# POST: ПУБЛИКАЦИЯ
# =========================================================

@router.post(
    "/greenhouse-gases/publish",
    response_class=HTMLResponse,
)
async def publish_greenhouse_gas_request(
    request: Request,
):
    form = await request.form()

    short_description = str(
        form.get("short_description", "")
    ).strip()

    formula = str(
        form.get("formula", "")
    ).strip()

    global_warming_potential_raw = form.get(
        "global_warming_potential_100y"
    )

    concentration_raw = form.get(
        "concentration"
    )

    if not short_description:
        raise HTTPException(
            status_code=400,
            detail="Описание парникового газа не указано",
        )

    if not formula:
        raise HTTPException(
            status_code=400,
            detail="Формула парникового газа не указана",
        )

    if (
        global_warming_potential_raw is None
        or str(global_warming_potential_raw).strip() == ""
    ):
        raise HTTPException(
            status_code=400,
            detail="GWP100 не указан",
        )

    if (
        concentration_raw is None
        or str(concentration_raw).strip() == ""
    ):
        raise HTTPException(
            status_code=400,
            detail="Концентрация парникового газа не указана",
        )

    try:
        global_warming_potential = float(
            global_warming_potential_raw
        )
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=400,
            detail="Некорректное значение GWP100",
        )

    try:
        concentration = float(
            concentration_raw
        )
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=400,
            detail="Некорректное значение концентрации",
        )

    if concentration <= 0:
        raise HTTPException(
            status_code=400,
            detail="Концентрация должна быть больше нуля",
        )

    if global_warming_potential < 0:
        raise HTTPException(
            status_code=400,
            detail="GWP100 не может быть отрицательным",
        )

    temperature_change = calculate_temperature_change(
        concentration
    )

    async with async_session_maker() as session:
        draft = await get_draft_greenhouse_gas(
            session=session,
            creator_id=CURRENT_USER_ID,
        )

        if draft is None:
            raise HTTPException(
                status_code=404,
                detail="Черновик парникового газа не найден",
            )

        published = await publish_greenhouse_gas(
            session=session,
            greenhouse_gas_id=draft.id,
            short_description=short_description,
            formula=formula,
            global_warming_potential_100y=(
                global_warming_potential
            ),
            concentration_ppm=concentration,
            temperature_change_c=temperature_change,
        )

    if published is None:
        raise HTTPException(
            status_code=404,
            detail="Черновик парникового газа не найден",
        )

    greenhouse_gas = serialize_greenhouse_gas(
        published
    )

    return templates.TemplateResponse(
        request=request,
        name="greenhouse_gas.html",
        context={
            "request": request,
            "greenhouse_gas": greenhouse_gas,
        },
    )


# =========================================================
# GET: КАТАЛОГ
# =========================================================

@router.get(
    "/greenhouse-gases/catalog",
    response_class=HTMLResponse,
)
async def get_greenhouse_gas_catalog(
    request: Request,
    concentration: float | None = Query(
        default=None
    ),
):
    async with async_session_maker() as session:
        all_published = await get_published_greenhouse_gases(
            session=session,
        )

        published = await get_published_greenhouse_gases(
            session=session,
            concentration=concentration,
        )

        likes_counts = await get_likes_counts(
            session=session,
            greenhouse_gas_ids=[
                greenhouse_gas.id
                for greenhouse_gas in published
            ],
        )

    prepared = [
        serialize_greenhouse_gas(
            greenhouse_gas,
            likes_counts.get(
                greenhouse_gas.id,
                0,
            ),
        )
        for greenhouse_gas in published
    ]

    first_greenhouse_gas_id = (
        all_published[0].id
        if all_published
        else None
    )

    return templates.TemplateResponse(
        request=request,
        name="greenhouse_gas_catalog.html",
        context={
            "request": request,
            "greenhouse_gases": prepared,
            "concentration_filter": concentration,
            "filter_applied": (
                concentration is not None
            ),
            "first_greenhouse_gas_id": (
                first_greenhouse_gas_id
            ),
        },
    )


# =========================================================
# GET: ЛЕНТА / КОНКРЕТНЫЙ ГАЗ
# =========================================================

@router.get(
    "/greenhouse-gases/{greenhouse_gas_id}",
    response_class=HTMLResponse,
)
async def get_greenhouse_gas(
    request: Request,
    greenhouse_gas_id: int,
    go_next: bool = Query(
        default=False,
        alias="next",
    ),
):
    async with async_session_maker() as session:
        published = await get_published_greenhouse_gases(
            session=session,
        )

        likes_counts = await get_likes_counts(
            session=session,
            greenhouse_gas_ids=[
                greenhouse_gas.id
                for greenhouse_gas in published
            ],
        )

    current_index = next(
        (
            index
            for index, greenhouse_gas in enumerate(
                published
            )
            if greenhouse_gas.id == greenhouse_gas_id
        ),
        None,
    )

    if current_index is None:
        raise HTTPException(
            status_code=404,
            detail="Парниковый газ не найден",
        )

    if go_next:
        next_index = current_index + 1

        if next_index >= len(published):
            next_index = 0

        greenhouse_gas = published[next_index]
    else:
        greenhouse_gas = published[current_index]

    prepared = serialize_greenhouse_gas(
        greenhouse_gas,
        likes_counts.get(
            greenhouse_gas.id,
            0,
        ),
    )

    return templates.TemplateResponse(
        request=request,
        name="greenhouse_gas.html",
        context={
            "request": request,
            "greenhouse_gas": prepared,
        },
    )