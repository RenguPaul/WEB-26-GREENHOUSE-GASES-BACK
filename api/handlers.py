import math

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
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
from data.collections import greenhouse_gases


router = APIRouter()
templates = Jinja2Templates(directory="templates")

MINIO_URL = "http://localhost:9000/climate-media"

REFERENCE_CO2_PPM = 280.0
CLIMATE_SENSITIVITY_C = 3.0


def get_published_greenhouse_gases_from_memory():
    return [
        greenhouse_gas
        for greenhouse_gas in greenhouse_gases
        if greenhouse_gas["status"] == "published"
    ]


def calculate_temperature_change(concentration_ppm: float):
    """
    Упрощённый расчёт изменения средней температуры
    относительно доиндустриальной концентрации CO2 = 280 ppm.

    ΔT = S * log2(C / C0)

    S  = 3 °C — чувствительность климата
    C0 = 280 ppm — базовая концентрация CO2
    """

    if concentration_ppm <= 0:
        return 0.0

    return round(
        CLIMATE_SENSITIVITY_C
        * math.log2(concentration_ppm / REFERENCE_CO2_PPM),
        1,
    )


def prepare_greenhouse_gas(greenhouse_gas):
    """
    Подготавливает данные парникового газа для шаблонов.

    Температура здесь НЕ рассчитывается.
    """

    prepared = greenhouse_gas.copy()

    prepared["likes_count"] = len(greenhouse_gas["likes"])

    prepared["image_url"] = (
        f"{MINIO_URL}/{greenhouse_gas['image_key']}"
    )

    prepared["video_url"] = (
        f"{MINIO_URL}/{greenhouse_gas['video_key']}"
    )

    return prepared


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

    return {
        "message": "Парниковый газ удалён",
        "id": greenhouse_gas_id,
    }

@router.get(
    "/greenhouse-gases/request",
    response_class=HTMLResponse,
)
@router.get(
    "/greenhouse-gases/request",
    response_class=HTMLResponse,
)
async def get_greenhouse_gas_request(
    request: Request,
    concentration: float | None = Query(default=None),
    short_description: str | None = Query(default=None),
):
    async with async_session_maker() as session:
        draft = await get_draft_greenhouse_gas(session)

    if draft is None:
        raise HTTPException(
            status_code=404,
            detail="Черновик парникового газа не найден",
        )

    if concentration is None:
        concentration_value = draft.concentration_ppm
    else:
        concentration_value = concentration

    if short_description is None:
        description_value = draft.short_description
    else:
        description_value = short_description

    temperature_change = None

    if concentration_value is not None:
        temperature_change = calculate_temperature_change(
            concentration_value
        )

    greenhouse_gas = {
        "id": draft.id,
        "name": draft.name,
        "short_description": description_value,
        "status": draft.status,
        "image_url": draft.image_url,
        "video_url": draft.video_url,
        "concentration_ppm": concentration_value,
        "temperature_change_c": temperature_change,
        "likes_count": 0,
    }

    return templates.TemplateResponse(
        request=request,
        name="greenhouse_gas_request.html",
        context={
            "request": request,
            "greenhouse_gas": greenhouse_gas,
            "concentration": concentration_value,
        },
    )

@router.post(
    "/greenhouse-gases/request",
    response_class=HTMLResponse,
)
async def create_greenhouse_gas_request(
    request: Request,
):
    """
    Создаёт черновик парникового газа через SQLAlchemy ORM.
    """

    async with async_session_maker() as session:
        existing_draft = await get_draft_greenhouse_gas(session)

        if existing_draft is not None:
            return templates.TemplateResponse(
                request=request,
                name="greenhouse_gas_request.html",
                context={
                    "request": request,
                    "greenhouse_gas": {
                        "id": existing_draft.id,
                        "name": existing_draft.name,
                        "short_description": existing_draft.short_description,
                        "status": existing_draft.status,
                        "image_url": existing_draft.image_url,
                        "video_url": existing_draft.video_url,
                        "concentration_ppm": (
                            existing_draft.concentration_ppm
                        ),
                        "temperature_change_c": (
                            existing_draft.temperature_change_c
                        ),
                        "likes_count": 0,
                    },
                    "concentration": (
                        existing_draft.concentration_ppm
                    ),
                },
            )

        draft = await create_draft_greenhouse_gas(
            session=session,
            name="Новый парниковый газ",
            image_url=None,
            video_url=None,
            creator_id=1,
        )

    return templates.TemplateResponse(
        request=request,
        name="greenhouse_gas_request.html",
        context={
            "request": request,
            "greenhouse_gas": {
                "id": draft.id,
                "name": draft.name,
                "short_description": draft.short_description,
                "status": draft.status,
                "image_url": draft.image_url,
                "video_url": draft.video_url,
                "concentration_ppm": None,
                "temperature_change_c": None,
                "likes_count": 0,
            },
            "concentration": None,
        },
    )

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

    concentration_raw = form.get("concentration")

    if concentration_raw is None:
        raise HTTPException(
            status_code=400,
            detail="Концентрация парникового газа не указана",
        )

    try:
        concentration = float(concentration_raw)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=400,
            detail="Некорректное значение концентрации",
        )

    temperature_change = calculate_temperature_change(
        concentration
    )

    async with async_session_maker() as session:
        draft = await get_draft_greenhouse_gas(session)

        if draft is None:
            raise HTTPException(
                status_code=404,
                detail="Черновик парникового газа не найден",
            )

        published = await publish_greenhouse_gas(
            session=session,
            greenhouse_gas_id=draft.id,
            short_description=short_description,
            concentration_ppm=concentration,
            temperature_change_c=temperature_change,
        )

    if published is None:
        raise HTTPException(
            status_code=404,
            detail="Черновик парникового газа не найден",
        )

    return templates.TemplateResponse(
        request=request,
        name="greenhouse_gas.html",
        context={
            "request": request,
            "greenhouse_gas": {
                "id": published.id,
                "name": published.name,
                "short_description": published.short_description,
                "status": published.status,
                "image_url": published.image_url,
                "video_url": published.video_url,
                "concentration_ppm": published.concentration_ppm,
                "temperature_change_c": (
                    published.temperature_change_c
                ),
                "likes_count": 0,
            },
        },
    )

@router.get(
    "/greenhouse-gases/catalog",
    response_class=HTMLResponse,
)
async def get_greenhouse_gas_catalog(
    request: Request,
    concentration: float | None = Query(default=None),
):
    """
    Каталог опубликованных парниковых газов.

    Данные получаются из PostgreSQL через SQLAlchemy ORM.
    Фильтр выполняется на сервере.
    """

    async with async_session_maker() as session:
        published = await get_published_greenhouse_gases(
            session,
            concentration=concentration,
        )

        likes_counts = await get_likes_counts(
            session,
            [greenhouse_gas.id for greenhouse_gas in published],
        )

    prepared = []

    for greenhouse_gas in published:
        prepared.append(
            {
                "id": greenhouse_gas.id,
                "name": greenhouse_gas.name,
                "short_description": greenhouse_gas.short_description,
                "status": greenhouse_gas.status,
                "image_url": greenhouse_gas.image_url,
                "video_url": greenhouse_gas.video_url,
                "concentration_ppm": greenhouse_gas.concentration_ppm,
                "temperature_change_c": greenhouse_gas.temperature_change_c,
                "likes_count": likes_counts.get(
                    greenhouse_gas.id,
                    0,
                ),
            }
        )

    print("CATALOG DATA:", prepared)

    return templates.TemplateResponse(
        request=request,
        name="greenhouse_gas_catalog.html",
        context={
            "request": request,
            "greenhouse_gases": prepared,
            "concentration_filter": (
                concentration
                if concentration is not None
                else 600
            ),
            "filter_applied": concentration is not None,
        },
    )


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
    """
    Страница конкретного опубликованного парникового газа.
    Данные получаются из PostgreSQL через SQLAlchemy ORM.
    """

    async with async_session_maker() as session:
        published = await get_published_greenhouse_gases(session)
        likes_counts = await get_likes_counts(
            session,
            [greenhouse_gas.id for greenhouse_gas in published],
        )
        print("LIKES COUNTS:", likes_counts)

    current_index = next(
        (
            index
            for index, greenhouse_gas in enumerate(published)
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

    prepared = {
        "id": greenhouse_gas.id,
        "name": greenhouse_gas.name,
        "short_description": greenhouse_gas.short_description,
        "status": greenhouse_gas.status,
        "image_url": greenhouse_gas.image_url,
        "video_url": greenhouse_gas.video_url,
        "concentration_ppm": greenhouse_gas.concentration_ppm,
        "temperature_change_c": greenhouse_gas.temperature_change_c,
        "likes_count": likes_counts.get(
            greenhouse_gas.id,
            0,
        ),
    }

    return templates.TemplateResponse(
        request=request,
        name="greenhouse_gas.html",
        context={
            "request": request,
            "greenhouse_gas": prepared,
        },
    )