
import math

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from repositories.greenhouse_gas import (
    create_draft_greenhouse_gas,
    delete_greenhouse_gas,
    get_draft_greenhouse_gas,
    get_greenhouse_gas_by_id,
    get_likes_counts,
    get_published_greenhouse_gases,
    publish_greenhouse_gas,
)


router = APIRouter()
templates = Jinja2Templates(directory="templates")


# ============================================================
# НАСТРОЙКИ
# ============================================================

CURRENT_USER_ID = 1

DEFAULT_IMAGE_URL = (
    "/static/media/default-greenhouse.jpg"
)

DEFAULT_VIDEO_URL = (
    "/static/media/default-greenhouse.mp4"
)

REFERENCE_CO2_PPM = 280.0
CLIMATE_SENSITIVITY_C = 3.0


# ============================================================
# РАСЧЁТ ИЗМЕНЕНИЯ ТЕМПЕРАТУРЫ
# ============================================================

def calculate_temperature_change(
    concentration_ppm: float,
    global_warming_potential_100y: float,
) -> float:
    """
    Упрощённая учебная модель расчёта
    изменения температуры.

    Сначала рассчитывается эффективная
    концентрация:

        C_eff = concentration_ppm * GWP100

    Затем:

        ΔT = S * log2(C_eff / C0)

    где:

        S  = 3.0 °C
        C0 = 280 ppm
    """

    if concentration_ppm <= 0:
        return 0.0

    if global_warming_potential_100y <= 0:
        return 0.0

    effective_concentration = (
        concentration_ppm
        * global_warming_potential_100y
    )

    if effective_concentration <= 0:
        return 0.0

    return round(
        CLIMATE_SENSITIVITY_C
        * math.log2(
            effective_concentration
            / REFERENCE_CO2_PPM
        ),
        1,
    )


# ============================================================
# МЕДИА
# ============================================================

def get_media_url(
    value: str | None,
    default_url: str,
) -> str:
    """
    Если ссылка на медиа отсутствует,
    используется локальный файл по умолчанию.
    """

    if not value:
        return default_url

    return value


# ============================================================
# ПОДГОТОВКА ДАННЫХ ДЛЯ TEMPLATE
# ============================================================

def serialize_greenhouse_gas(
    greenhouse_gas,
    likes_count: int = 0,
) -> dict:
    """
    Преобразует SQLAlchemy-модель
    в словарь для Jinja2.
    """

    temperature_change = (
        greenhouse_gas.temperature_change_c
    )

    # Если значение ещё не записано в БД,
    # рассчитываем его из двух предметных параметров.
    if (
        temperature_change is None
        and greenhouse_gas.concentration_ppm
        is not None
        and greenhouse_gas.global_warming_potential_100y
        is not None
    ):
        temperature_change = (
            calculate_temperature_change(
                concentration_ppm=(
                    greenhouse_gas.concentration_ppm
                ),
                global_warming_potential_100y=(
                    greenhouse_gas
                    .global_warming_potential_100y
                ),
            )
        )

    return {
        "id": greenhouse_gas.id,
        "name": greenhouse_gas.name,
        "formula": greenhouse_gas.formula,

        "global_warming_potential_100y": (
            greenhouse_gas
            .global_warming_potential_100y
        ),

        "short_description": (
            greenhouse_gas.short_description
        ),

        "status": greenhouse_gas.status,

        "image_url": get_media_url(
            greenhouse_gas.image_url,
            DEFAULT_IMAGE_URL,
        ),

        "video_url": get_media_url(
            greenhouse_gas.video_url,
            DEFAULT_VIDEO_URL,
        ),

        "concentration_ppm": (
            greenhouse_gas.concentration_ppm
        ),

        "temperature_change_c": (
            greenhouse_gas.temperature_change_c
        ),

        # Это имя используется в шаблоне
        # для отображения значения температуры.
        "temperature_change": (
            temperature_change
        ),

        "created_at": greenhouse_gas.created_at,

        "creator_id": greenhouse_gas.creator_id,

        "published_at": greenhouse_gas.published_at,

        "likes_count": likes_count,
    }


# ============================================================
# 1. POST — ЛОГИЧЕСКОЕ УДАЛЕНИЕ
# ============================================================

@router.post(
    "/greenhouse-gases/{greenhouse_gas_id}/delete"
)
async def delete_greenhouse_gas_route(
    greenhouse_gas_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Логическое удаление.

    Запись физически не удаляется.
    Её статус меняется на "удален".
    """

    await delete_greenhouse_gas(
        db,
        greenhouse_gas_id,
    )

    return {
        "message": "Парниковый газ удалён"
    }


# ============================================================
# 2. GET — СТРАНИЦА ЗАЯВКИ
# ============================================================

@router.get(
    "/greenhouse-gases/request",
    response_class=HTMLResponse,
)
async def get_greenhouse_gas_request(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Открытие страницы создания заявки.
    """

    draft = await get_draft_greenhouse_gas(
        db,
        CURRENT_USER_ID,
    )

    if draft is None:
        draft = await create_draft_greenhouse_gas(
            db,
            "Новый парниковый газ",
            CURRENT_USER_ID,
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


# ============================================================
# 3. POST — СОЗДАНИЕ ЧЕРНОВИКА
# ============================================================

@router.post(
    "/greenhouse-gases/request"
)
async def create_greenhouse_gas_request(
    name: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Создание черновика через ORM.

    У пользователя может быть только
    один черновик.
    """

    existing_draft = (
        await get_draft_greenhouse_gas(
            db,
            CURRENT_USER_ID,
        )
    )

    if existing_draft is not None:
        return {
            "message": "Черновик уже существует",
            "greenhouse_gas_id": (
                existing_draft.id
            ),
        }

    greenhouse_gas = (
        await create_draft_greenhouse_gas(
            db,
            name,
            CURRENT_USER_ID,
        )
    )

    return {
        "message": "Черновик создан",
        "greenhouse_gas_id": (
            greenhouse_gas.id
        ),
    }


# ============================================================
# 4. POST — ПУБЛИКАЦИЯ
# ============================================================

@router.post(
    "/greenhouse-gases/publish"
)
async def publish_greenhouse_gas_route(
    greenhouse_gas_id: int = Query(...),
    short_description: str = Query(...),
    global_warming_potential_100y: float = Query(...),
    concentration_ppm: float = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Публикация черновика.

    Температура вводиться пользователем
    не должна.

    Она вычисляется автоматически из:

        concentration_ppm
        +
        global_warming_potential_100y
    """

    temperature_change_c = (
        calculate_temperature_change(
            concentration_ppm=concentration_ppm,
            global_warming_potential_100y=(
                global_warming_potential_100y
            ),
        )
    )

    greenhouse_gas = (
        await publish_greenhouse_gas(
            session=db,
            greenhouse_gas_id=(
                greenhouse_gas_id
            ),
            short_description=(
                short_description
            ),
            global_warming_potential_100y=(
                global_warming_potential_100y
            ),
            concentration_ppm=(
                concentration_ppm
            ),
            temperature_change_c=(
                temperature_change_c
            ),
        )
    )

    if greenhouse_gas is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Черновик парникового газа "
                "не найден"
            ),
        )

    return {
        "message": (
            "Парниковый газ опубликован"
        ),
        "greenhouse_gas_id": (
            greenhouse_gas.id
        ),
        "temperature_change_c": (
            temperature_change_c
        ),
    }


# ============================================================
# 5. GET — КАТАЛОГ
# ============================================================

@router.get(
    "/greenhouse-gases/catalog",
    response_class=HTMLResponse,
)
async def get_greenhouse_gas_catalog(
    request: Request,
    concentration: float | None = Query(
        default=None
    ),
    db: AsyncSession = Depends(get_db),
):
    """
    Каталог опубликованных
    парниковых газов.

    Фильтрация выполняется
    на стороне сервера.
    """

    # Получаем все опубликованные записи.
    all_published = (
        await get_published_greenhouse_gases(
            db
        )
    )

    # Первый опубликованный объект
    # используется для ссылки "Лента".
    first_greenhouse_gas_id = (
        all_published[0].id
        if all_published
        else None
    )

    # Получаем каталог с фильтром.
    greenhouse_gases = (
        await get_published_greenhouse_gases(
            db,
            concentration=concentration,
        )
    )

    greenhouse_gas_ids = [
        greenhouse_gas.id
        for greenhouse_gas
        in greenhouse_gases
    ]

    likes_counts = await get_likes_counts(
        db,
        greenhouse_gas_ids,
    )

    prepared_greenhouse_gases = []

    for greenhouse_gas in greenhouse_gases:
        item = serialize_greenhouse_gas(
            greenhouse_gas,
            likes_counts.get(
                greenhouse_gas.id,
                0,
            ),
        )

        prepared_greenhouse_gases.append(
            item
        )

    return templates.TemplateResponse(
        request=request,
        name="greenhouse_gas_catalog.html",
        context={
            "request": request,

            "greenhouse_gases": (
                prepared_greenhouse_gases
            ),

            "concentration_filter": (
                concentration
            ),

            "first_greenhouse_gas_id": (
                first_greenhouse_gas_id
            ),
        },
    )


# ============================================================
# 6. GET — ЛЕНТА / ОДИН ПАРНИКОВЫЙ ГАЗ
# ============================================================

@router.get(
    "/greenhouse-gases/{greenhouse_gas_id}",
    response_class=HTMLResponse,
)
async def get_greenhouse_gas(
    request: Request,
    greenhouse_gas_id: int,

    # В URL остаётся ?next=true,
    # но внутри Python параметр называется go_next,
    # чтобы не конфликтовать со встроенной функцией next().
    go_next: bool = Query(
        default=False,
        alias="next",
    ),

    db: AsyncSession = Depends(get_db),
):
    """
    Отображение одного опубликованного
    парникового газа.

    При ?next=true открывается
    следующий опубликованный объект.
    """

    # Сначала получаем конкретный объект
    # через ORM.
    greenhouse_gas = (
        await get_greenhouse_gas_by_id(
            db,
            greenhouse_gas_id,
        )
    )

    if greenhouse_gas is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Парниковый газ не найден"
            ),
        )

    # --------------------------------------------------------
    # КНОПКА "СЛЕДУЮЩИЙ"
    # --------------------------------------------------------

    if go_next:
        published = (
            await get_published_greenhouse_gases(
                db
            )
        )

        current_index = next(
            (
                index
                for index, item
                in enumerate(published)
                if item.id == greenhouse_gas_id
            ),
            None,
        )

        if current_index is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Парниковый газ не найден"
                ),
            )

        if not published:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Опубликованные "
                    "парниковые газы отсутствуют"
                ),
            )

        next_index = (
            current_index + 1
        ) % len(published)

        greenhouse_gas = published[
            next_index
        ]

    # --------------------------------------------------------
    # ЛАЙКИ
    # --------------------------------------------------------

    likes_counts = await get_likes_counts(
        db,
        [greenhouse_gas.id],
    )

    likes_count = likes_counts.get(
        greenhouse_gas.id,
        0,
    )

    # --------------------------------------------------------
    # ПОДГОТОВКА ДАННЫХ
    # --------------------------------------------------------

    prepared = serialize_greenhouse_gas(
        greenhouse_gas,
        likes_count,
    )

    return templates.TemplateResponse(
        request=request,
        name="greenhouse_gas.html",
        context={
            "request": request,
            "greenhouse_gas": prepared,
        },
    )

