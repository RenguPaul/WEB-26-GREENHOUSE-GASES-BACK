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


def calculate_temperature_change(
    concentration_ppm: float,
    global_warming_potential_100y: float,
) -> float:
    """
    Упрощённый расчёт изменения средней температуры
    с учётом концентрации парникового газа и его GWP100.

    Сначала рассчитывается эквивалентная концентрация CO₂:

        C_eff = concentration_ppm * GWP100

    Затем изменение температуры:

        ΔT = S * log2(C_eff / C0)

    где:

        S  = 3.0 °C — чувствительность климата;
        C0 = 280 ppm — базовая концентрация CO₂.
    """

    if concentration_ppm <= 0:
        return 0.0

    if global_warming_potential_100y <= 0:
        return 0.0

    effective_concentration = (
        concentration_ppm
        * global_warming_potential_100y
    )

    return round(
        CLIMATE_SENSITIVITY_C
        * math.log2(
            effective_concentration
            / REFERENCE_CO2_PPM
        ),
        1,
    )


def prepare_greenhouse_gas(
    greenhouse_gas,
):
    """
    Подготавливает данные парникового газа
    для передачи в шаблоны.
    """

    prepared = greenhouse_gas.copy()

    prepared["likes_count"] = len(
        greenhouse_gas["likes"]
    )

    prepared["image_url"] = (
        f"{MINIO_URL}/{greenhouse_gas['image_key']}"
    )

    prepared["video_url"] = (
        f"{MINIO_URL}/{greenhouse_gas['video_key']}"
    )

    return prepared


# ============================================================
# GET: СТРАНИЦА ЗАЯВКИ
# ============================================================

@router.get(
    "/greenhouse-gases/request",
    response_class=HTMLResponse,
)
def get_greenhouse_gas_request(
    request: Request,
    concentration: float | None = Query(
        default=None
    ),
    gwp: float | None = Query(
        default=None
    ),
):
    """
    Страница создания заявки.

    Расчёт выполняется по двум параметрам:

    - concentration — концентрация газа, ppm;
    - gwp — потенциал глобального потепления GWP100.
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

    if concentration is None:
        concentration_value = draft[
            "concentration_ppm"
        ]
    else:
        concentration_value = concentration

    if gwp is None:
        gwp_value = draft[
            "global_warming_potential_100y"
        ]
    else:
        gwp_value = gwp

    greenhouse_gas = prepare_greenhouse_gas(
        draft
    )

    greenhouse_gas["concentration_ppm"] = (
        concentration_value
    )

    greenhouse_gas[
        "global_warming_potential_100y"
    ] = gwp_value

    greenhouse_gas["temperature_change"] = (
        calculate_temperature_change(
            concentration_ppm=concentration_value,
            global_warming_potential_100y=gwp_value,
        )
    )

    return templates.TemplateResponse(
        request=request,
        name="greenhouse_gas_request.html",
        context={
            "request": request,
            "greenhouse_gas": greenhouse_gas,
            "concentration": concentration_value,
            "gwp": gwp_value,
        },
    )


# ============================================================
# GET: КАТАЛОГ
# ============================================================

@router.get(
    "/greenhouse-gases/catalog",
    response_class=HTMLResponse,
)
def get_greenhouse_gas_catalog(
    request: Request,
    concentration: float | None = Query(
        default=None
    ),
):
    """
    Каталог опубликованных парниковых газов.

    Фильтрация выполняется по концентрации.
    """

    published = get_published_greenhouse_gases()

    if concentration is not None:
        published = [
            greenhouse_gas
            for greenhouse_gas in published
            if greenhouse_gas["concentration_ppm"]
            <= concentration
        ]

    prepared = []

    for greenhouse_gas in published:
        item = prepare_greenhouse_gas(
            greenhouse_gas
        )

        # Температура рассчитывается из двух
        # предметных параметров.
        item["temperature_change"] = (
            calculate_temperature_change(
                concentration_ppm=(
                    greenhouse_gas[
                        "concentration_ppm"
                    ]
                ),
                global_warming_potential_100y=(
                    greenhouse_gas[
                        "global_warming_potential_100y"
                    ]
                ),
            )
        )

        prepared.append(item)

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
            "filter_applied": (
                concentration is not None
            ),
        },
    )


# ============================================================
# GET: ЛЕНТА / КОНКРЕТНЫЙ ПАРНИКОВЫЙ ГАЗ
# ============================================================

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
    Страница конкретного опубликованного
    парникового газа.

    Перед отображением рассчитывается изменение
    температуры на основе двух параметров:

    1. concentration_ppm
    2. global_warming_potential_100y
    """

    published = get_published_greenhouse_gases()

    current_index = next(
        (
            index
            for index, greenhouse_gas in enumerate(
                published
            )
            if greenhouse_gas["id"]
            == greenhouse_gas_id
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

        greenhouse_gas = published[
            next_index
        ]
    else:
        greenhouse_gas = published[
            current_index
        ]

    concentration_ppm = greenhouse_gas[
        "concentration_ppm"
    ]

    global_warming_potential_100y = (
        greenhouse_gas[
            "global_warming_potential_100y"
        ]
    )

    # Расчёт температуры по двум параметрам.
    temperature_change = (
        calculate_temperature_change(
            concentration_ppm=concentration_ppm,
            global_warming_potential_100y=(
                global_warming_potential_100y
            ),
        )
    )

    prepared = prepare_greenhouse_gas(
        greenhouse_gas
    )

    # Передаём рассчитанный результат
    # в шаблон ленты.
    prepared["temperature_change"] = (
        temperature_change
    )

    return templates.TemplateResponse(
        request=request,
        name="greenhouse_gas.html",
        context={
            "request": request,
            "greenhouse_gas": prepared,
        },
    )

