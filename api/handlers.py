import math

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from data.collections import greenhouse_gases


router = APIRouter()
templates = Jinja2Templates(directory="templates")

MINIO_URL = "http://localhost:9000/climate-media"

REFERENCE_CO2_PPM = 280.0
CLIMATE_SENSITIVITY_C = 3.0


def get_published_greenhouse_gases():
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


@router.get(
    "/greenhouse-gases/request",
    response_class=HTMLResponse,
)
def get_greenhouse_gas_request(
    request: Request,
    concentration: float | None = Query(default=None),
):
    """
    Страница создания заявки на расчёт.

    Концентрация передаётся через GET-параметр.
    Например:
    /greenhouse-gases/request?concentration=420
    """

    draft = next(
        (
            greenhouse_gas
            for greenhouse_gas in greenhouse_gases
            if greenhouse_gas["status"] == "draft"
        ),
        None,
    )

    if draft is None:
        raise HTTPException(
            status_code=404,
            detail="Черновик парникового газа не найден",
        )

    greenhouse_gas = prepare_greenhouse_gas(draft)

    # Если пользователь ещё ничего не вводил,
    # показываем исходную концентрацию из черновика.
    if concentration is None:
        concentration_value = draft["concentration_ppm"]
    else:
        concentration_value = concentration

    greenhouse_gas["concentration_ppm"] = concentration_value

    # Температура рассчитывается только для CO2.
    if draft["formula"] == "CO2":
        greenhouse_gas["temperature_change"] = (
            calculate_temperature_change(
                concentration_value
            )
        )
    else:
        greenhouse_gas["temperature_change"] = None

    return templates.TemplateResponse(
        request=request,
        name="greenhouse_gas_request.html",
        context={
            "request": request,
            "greenhouse_gas": greenhouse_gas,
            "concentration": concentration_value,
        },
    )


@router.get(
    "/greenhouse-gases/catalog",
    response_class=HTMLResponse,
)
def get_greenhouse_gas_catalog(
    request: Request,
    concentration: float | None = Query(default=None),
):
    """
    Каталог опубликованных парниковых газов.

    Фильтр выполняется на сервере по концентрации.
    """

    published = get_published_greenhouse_gases()

    if concentration is not None:
        published = [
            greenhouse_gas
            for greenhouse_gas in published
            if greenhouse_gas["concentration_ppm"] <= concentration
        ]

    prepared = [
        prepare_greenhouse_gas(greenhouse_gas)
        for greenhouse_gas in published
    ]

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
def get_greenhouse_gas(
    request: Request,
    greenhouse_gas_id: int,
    go_next: bool = Query(
        default=False,
        alias="next",
    ),
):
    """
    Страница конкретного опубликованного парникового газа.
    """

    published = get_published_greenhouse_gases()

    current_index = next(
        (
            index
            for index, greenhouse_gas in enumerate(published)
            if greenhouse_gas["id"] == greenhouse_gas_id
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

    prepared = prepare_greenhouse_gas(greenhouse_gas)

    return templates.TemplateResponse(
        request=request,
        name="greenhouse_gas.html",
        context={
            "request": request,
            "greenhouse_gas": prepared,
        },
    )