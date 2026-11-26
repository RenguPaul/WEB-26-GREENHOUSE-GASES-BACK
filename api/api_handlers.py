import math

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
)

from api.dependencies import (
    get_current_user_id,
    get_optional_current_user_id,
)
from core.minio import (
    get_file_url,
    upload_file,
    validate_image,
    validate_video,
)
from db.session import async_session_maker
from repositories.greenhouse_gas import (
    create_api_draft_greenhouse_gas,
    delete_api_greenhouse_gas,
    get_draft_greenhouse_gas,
    get_greenhouse_gas_by_id,
    get_likes_counts,
    get_next_published_greenhouse_gas,
    get_published_greenhouse_gases,
    get_user_liked_greenhouse_gas_ids,
    publish_api_greenhouse_gas,
    set_greenhouse_gas_like,
)
from schemas.greenhouse_gas import (
    GreenhouseGasCreateResponse,
    GreenhouseGasDraftResponse,
    GreenhouseGasFeedItem,
    GreenhouseGasListItem,
    GreenhouseGasPublishRequest,
    GreenhouseGasPublishResponse,
    LikeRequest,
)


router = APIRouter(
    prefix="/api",
    tags=["Greenhouse gases"],
)


DEFAULT_IMAGE_URL = "/static/media/default-greenhouse.jpg"
DEFAULT_VIDEO_URL = "/static/media/default-greenhouse.mp4"

REFERENCE_CO2_PPM = 280.0
CLIMATE_SENSITIVITY_C = 3.0


def get_media_url(
    value: str | None,
    default_url: str,
) -> str:
    if value and value.strip():
        return value

    return default_url


def serialize_list_item(
    greenhouse_gas,
    current_user_id: int | None,
    likes_count: int = 0,
) -> GreenhouseGasListItem:
    return GreenhouseGasListItem(
        id=greenhouse_gas.id,
        name=greenhouse_gas.name,
        formula=greenhouse_gas.formula,
        global_warming_potential_100y=(
            greenhouse_gas.global_warming_potential_100y
        ),
        short_description=greenhouse_gas.short_description,
        concentration_ppm=greenhouse_gas.concentration_ppm,
        temperature_change_c=greenhouse_gas.temperature_change_c,
        image_url=get_media_url(
            get_file_url(greenhouse_gas.image_url)
            if greenhouse_gas.image_url
            else None,
            DEFAULT_IMAGE_URL,
        ),
        video_url=get_media_url(
            get_file_url(greenhouse_gas.video_url)
            if greenhouse_gas.video_url
            else None,
            DEFAULT_VIDEO_URL,
        ),
        is_creator=(
            1
            if current_user_id is not None
            and greenhouse_gas.creator_id == current_user_id
            else 0
        ),
        likes_count=likes_count,
    )


def serialize_published_item(
    greenhouse_gas,
    likes_count: int,
    liked_greenhouse_gas_ids: set[int],
) -> GreenhouseGasFeedItem:
    return GreenhouseGasFeedItem(
        id=greenhouse_gas.id,
        name=greenhouse_gas.name,
        formula=greenhouse_gas.formula,
        global_warming_potential_100y=(
            greenhouse_gas.global_warming_potential_100y
        ),
        short_description=greenhouse_gas.short_description,
        concentration_ppm=greenhouse_gas.concentration_ppm,
        temperature_change_c=greenhouse_gas.temperature_change_c,
        image_url=get_media_url(
            get_file_url(greenhouse_gas.image_url)
            if greenhouse_gas.image_url
            else None,
            DEFAULT_IMAGE_URL,
        ),
        video_url=get_media_url(
            get_file_url(greenhouse_gas.video_url)
            if greenhouse_gas.video_url
            else None,
            DEFAULT_VIDEO_URL,
        ),
        is_liked=(
            1
            if greenhouse_gas.id in liked_greenhouse_gas_ids
            else 0
        ),
        likes_count=likes_count,
    )


@router.get(
    "/greenhouse-gases",
    response_model=list[GreenhouseGasListItem],
    summary="Получить опубликованные парниковые газы",
    description=(
        "Публичный метод чтения. Авторизация не требуется. "
        "Поддерживает серверную фильтрацию по концентрации."
    ),
    responses={
        400: {"description": "Некорректная концентрация"}
    },
)
async def get_greenhouse_gases(
    concentration: float | None = Query(default=None),
    current_user_id: int | None = Depends(
        get_optional_current_user_id
    ),
):
    if concentration is not None and concentration <= 0:
        raise HTTPException(
            status_code=400,
            detail="Концентрация должна быть больше нуля",
        )

    async with async_session_maker() as session:
        greenhouse_gases = await get_published_greenhouse_gases(
            session=session,
            concentration=concentration,
        )

        greenhouse_gas_ids = [
            item.id for item in greenhouse_gases
        ]

        likes_counts = await get_likes_counts(
            session=session,
            greenhouse_gas_ids=greenhouse_gas_ids,
        )

    return [
        serialize_list_item(
            greenhouse_gas=item,
            current_user_id=current_user_id,
            likes_count=likes_counts.get(item.id, 0),
        )
        for item in greenhouse_gases
    ]


@router.get(
    "/greenhouse-gases/published-gases",
    response_model=list[GreenhouseGasFeedItem],
    summary="Получить ленту опубликованных парниковых газов",
    description=(
        "Публичный метод чтения. Для следующей записи передайте "
        "greenhouse_gas_id и next=true."
    ),
    responses={
        400: {"description": "Некорректные query-параметры"},
        404: {"description": "Следующая запись не найдена"},
    },
)
async def get_published_greenhouse_gases_api(
    greenhouse_gas_id: int | None = Query(default=None),
    next: bool = Query(default=False),
    current_user_id: int | None = Depends(
        get_optional_current_user_id
    ),
):
    if next and greenhouse_gas_id is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "Для параметра next=true необходимо "
                "указать greenhouse_gas_id"
            ),
        )

    if not next and greenhouse_gas_id is not None:
        raise HTTPException(
            status_code=400,
            detail=(
                "Параметр greenhouse_gas_id используется "
                "только вместе с next=true"
            ),
        )

    async with async_session_maker() as session:
        if next:
            greenhouse_gas = (
                await get_next_published_greenhouse_gas(
                    session=session,
                    greenhouse_gas_id=greenhouse_gas_id,
                )
            )

            if greenhouse_gas is None:
                raise HTTPException(
                    status_code=404,
                    detail=(
                        "Следующий опубликованный "
                        "парниковый газ не найден"
                    ),
                )

            greenhouse_gases = [greenhouse_gas]
        else:
            greenhouse_gases = (
                await get_published_greenhouse_gases(
                    session=session,
                )
            )

        greenhouse_gas_ids = [
            item.id for item in greenhouse_gases
        ]

        likes_counts = await get_likes_counts(
            session=session,
            greenhouse_gas_ids=greenhouse_gas_ids,
        )

        liked_greenhouse_gas_ids = set()

        if current_user_id is not None:
            liked_greenhouse_gas_ids = (
                await get_user_liked_greenhouse_gas_ids(
                    session=session,
                    user_id=current_user_id,
                    greenhouse_gas_ids=greenhouse_gas_ids,
                )
            )

    return [
        serialize_published_item(
            greenhouse_gas=item,
            likes_count=likes_counts.get(item.id, 0),
            liked_greenhouse_gas_ids=liked_greenhouse_gas_ids,
        )
        for item in greenhouse_gases
    ]


@router.get(
    "/greenhouse-gases/my-gas",
    response_model=GreenhouseGasDraftResponse,
    summary="Получить свой черновик",
    description=(
        "Требуется действующая cookie сессии "
        "greenhouse_session."
    ),
    responses={
        401: {"description": "Не выполнен вход"},
        404: {"description": "Черновик не найден"},
    },
)
async def get_my_greenhouse_gas(
    current_user_id: int = Depends(get_current_user_id),
):
    async with async_session_maker() as session:
        greenhouse_gas = await get_draft_greenhouse_gas(
            session=session,
            creator_id=current_user_id,
        )

    if greenhouse_gas is None:
        raise HTTPException(
            status_code=404,
            detail="Черновик текущего пользователя не найден",
        )

    return GreenhouseGasDraftResponse(
        id=greenhouse_gas.id,
        name=greenhouse_gas.name,
        formula=greenhouse_gas.formula,
        global_warming_potential_100y=(
            greenhouse_gas.global_warming_potential_100y
        ),
        short_description=greenhouse_gas.short_description,
        concentration_ppm=greenhouse_gas.concentration_ppm,
        temperature_change_c=greenhouse_gas.temperature_change_c,
        image_url=get_media_url(
            get_file_url(greenhouse_gas.image_url)
            if greenhouse_gas.image_url
            else None,
            DEFAULT_IMAGE_URL,
        ),
        video_url=get_media_url(
            get_file_url(greenhouse_gas.video_url)
            if greenhouse_gas.video_url
            else None,
            DEFAULT_VIDEO_URL,
        ),
    )


@router.post(
    "/greenhouse-gases",
    response_model=GreenhouseGasCreateResponse,
    status_code=201,
    summary="Создать черновик парникового газа",
    description=(
        "Требуется авторизация. Создатель определяется по cookie; "
        "изображение и видео передаются файлами."
    ),
    responses={
        401: {"description": "Не выполнен вход"},
        409: {"description": "Черновик уже существует"},
    },
)
async def create_greenhouse_gas(
    name: str = Form(...),
    formula: str | None = Form(default=None),
    global_warming_potential_100y: float | None = Form(
        default=None
    ),
    short_description: str | None = Form(default=None),
    concentration_ppm: float | None = Form(default=None),
    image: UploadFile = File(...),
    video: UploadFile = File(...),
    current_user_id: int = Depends(get_current_user_id),
):
    if not name.strip():
        raise HTTPException(
            status_code=400,
            detail="Название парникового газа не может быть пустым",
        )

    if concentration_ppm is not None and concentration_ppm <= 0:
        raise HTTPException(
            status_code=400,
            detail="Концентрация должна быть больше нуля",
        )

    validate_image(image)
    validate_video(video)

    async with async_session_maker() as session:
        existing_draft = await get_draft_greenhouse_gas(
            session=session,
            creator_id=current_user_id,
        )

        if existing_draft is not None:
            raise HTTPException(
                status_code=409,
                detail="У пользователя уже существует черновик",
            )

    try:
        image_filename = await upload_file(
            file=image,
            prefix="image",
        )

        video_filename = await upload_file(
            file=video,
            prefix="video",
        )

        temperature_change_c = None

        if concentration_ppm is not None:
            temperature_change_c = round(
                CLIMATE_SENSITIVITY_C
                * math.log2(
                    concentration_ppm / REFERENCE_CO2_PPM
                ),
                1,
            )

        async with async_session_maker() as session:
            greenhouse_gas = (
                await create_api_draft_greenhouse_gas(
                    session=session,
                    name=name.strip(),
                    formula=formula,
                    short_description=short_description,
                    global_warming_potential_100y=(
                        global_warming_potential_100y
                    ),
                    concentration_ppm=concentration_ppm,
                    temperature_change_c=temperature_change_c,
                    image_filename=image_filename,
                    video_filename=video_filename,
                    creator_id=current_user_id,
                )
            )

    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Не удалось создать парниковый газ",
        ) from exc

    return GreenhouseGasCreateResponse(
        id=greenhouse_gas.id,
        name=greenhouse_gas.name,
        status=greenhouse_gas.status,
        image_url=get_media_url(
            get_file_url(greenhouse_gas.image_url),
            DEFAULT_IMAGE_URL,
        ),
        video_url=get_media_url(
            get_file_url(greenhouse_gas.video_url),
            DEFAULT_VIDEO_URL,
        ),
    )


@router.put(
    "/greenhouse-gases/{greenhouse_gas_id}/publish",
    response_model=GreenhouseGasPublishResponse,
    summary="Опубликовать свой черновик",
    description=(
        "Сохраняет характеристики и публикует только собственный "
        "черновик текущего пользователя."
    ),
    responses={
        401: {"description": "Не выполнен вход"},
        404: {"description": "Черновик не найден"},
    },
)
async def publish_greenhouse_gas_api(
    greenhouse_gas_id: int,
    data: GreenhouseGasPublishRequest,
    current_user_id: int = Depends(get_current_user_id),
):
    temperature_change_c = round(
        CLIMATE_SENSITIVITY_C
        * math.log2(
            data.concentration_ppm / REFERENCE_CO2_PPM
        ),
        1,
    )

    async with async_session_maker() as session:
        greenhouse_gas = await publish_api_greenhouse_gas(
            session=session,
            greenhouse_gas_id=greenhouse_gas_id,
            creator_id=current_user_id,
            short_description=data.short_description,
            concentration_ppm=data.concentration_ppm,
            global_warming_potential_100y=(
                data.global_warming_potential_100y
            ),
            temperature_change_c=temperature_change_c,
        )

    if greenhouse_gas is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Черновик не найден или не принадлежит "
                "текущему пользователю"
            ),
        )

    return GreenhouseGasPublishResponse(
        id=greenhouse_gas.id,
        name=greenhouse_gas.name,
        status=greenhouse_gas.status,
        image_url=get_media_url(
            get_file_url(greenhouse_gas.image_url),
            DEFAULT_IMAGE_URL,
        ),
        video_url=get_media_url(
            get_file_url(greenhouse_gas.video_url),
            DEFAULT_VIDEO_URL,
        ),
        published_at=greenhouse_gas.published_at.isoformat(),
    )


@router.post(
    "/greenhouse-gases/{greenhouse_gas_id}/like",
    summary="Поставить или убрать лайк",
    description=(
        "Требуется авторизация. like=1 — поставить лайк, "
        "like=0 — убрать лайк."
    ),
    responses={
        401: {"description": "Не выполнен вход"},
        404: {"description": "Опубликованная запись не найдена"},
    },
)
async def like_greenhouse_gas(
    greenhouse_gas_id: int,
    like_request: LikeRequest,
    current_user_id: int = Depends(get_current_user_id),
):
    async with async_session_maker() as session:
        greenhouse_gas = await get_greenhouse_gas_by_id(
            session=session,
            greenhouse_gas_id=greenhouse_gas_id,
        )

        if greenhouse_gas is None:
            raise HTTPException(
                status_code=404,
                detail="Парниковый газ не найден",
            )

        await set_greenhouse_gas_like(
            session=session,
            user_id=current_user_id,
            greenhouse_gas_id=greenhouse_gas_id,
            like=like_request.like,
        )

        likes_counts = await get_likes_counts(
            session=session,
            greenhouse_gas_ids=[greenhouse_gas_id],
        )

    return {
        "greenhouse_gas_id": greenhouse_gas_id,
        "like": like_request.like,
        "likes_count": likes_counts.get(
            greenhouse_gas_id,
            0,
        ),
    }


@router.delete(
    "/greenhouse-gases/{greenhouse_gas_id}",
    summary="Логически удалить собственную запись",
    description=(
        "Требуется авторизация. Запись не удаляется физически; "
        "её статус меняется на удалённый."
    ),
    responses={
        401: {"description": "Не выполнен вход"},
        404: {"description": "Запись не найдена"},
    },
)
async def delete_greenhouse_gas_api(
    greenhouse_gas_id: int,
    current_user_id: int = Depends(get_current_user_id),
):
    async with async_session_maker() as session:
        greenhouse_gas = await delete_api_greenhouse_gas(
            session=session,
            greenhouse_gas_id=greenhouse_gas_id,
            creator_id=current_user_id,
        )

    if greenhouse_gas is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Парниковый газ не найден или не принадлежит "
                "текущему пользователю"
            ),
        )

    return {
        "id": greenhouse_gas.id,
        "status": greenhouse_gas.status,
    }