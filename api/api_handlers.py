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

from api.dependencies import get_current_user_id
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
from repositories.user import (
    create_user,
    get_user_by_username,
)
from schemas.greenhouse_gas import (
    GreenhouseGasCreateResponse,
    GreenhouseGasDraftResponse,
    GreenhouseGasFeedItem,
    GreenhouseGasListItem,
    GreenhouseGasPublishResponse,
    LikeRequest,
)
from schemas.user import (
    AuthStubResponse,
    UserRegisterRequest,
    UserRegisterResponse,
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
    current_user_id: int,
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
            greenhouse_gas.image_url,
            DEFAULT_IMAGE_URL,
        ),
        video_url=get_media_url(
            greenhouse_gas.video_url,
            DEFAULT_VIDEO_URL,
        ),
        is_creator=(
            1
            if greenhouse_gas.creator_id == current_user_id
            else 0
        ),
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
            greenhouse_gas.image_url,
            DEFAULT_IMAGE_URL,
        ),
        video_url=get_media_url(
            greenhouse_gas.video_url,
            DEFAULT_VIDEO_URL,
        ),
        is_liked=(
            1
            if greenhouse_gas.id in liked_greenhouse_gas_ids
            else 0
        ),
        likes_count=likes_count,
    )


# ============================================================
# ДОМЕН ПРИЛОЖЕНИЯ
# ============================================================


@router.get(
    "/greenhouse-gases",
    response_model=list[GreenhouseGasListItem],
)
async def get_greenhouse_gases(
    concentration: float | None = Query(default=None),
    current_user_id: int = Depends(get_current_user_id),
):
    """
    GET /api/greenhouse-gases

    Возвращает опубликованные парниковые газы.
    Поддерживает серверную фильтрацию по концентрации.
    """

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

    return [
        serialize_list_item(
            greenhouse_gas=greenhouse_gas,
            current_user_id=current_user_id,
        )
        for greenhouse_gas in greenhouse_gases
    ]


@router.get(
    "/greenhouse-gases/published-gases",
    response_model=list[GreenhouseGasFeedItem],
)
async def get_published_greenhouse_gases_api(
    greenhouse_gas_id: int | None = Query(default=None),
    next: bool = Query(default=False),
    current_user_id: int = Depends(get_current_user_id),
):
    """
    GET /api/greenhouse-gases/published-gases

    Обычный запрос:
        GET /api/greenhouse-gases/published-gases

    Получение следующего опубликованного газа:
        GET /api/greenhouse-gases/published-gases
            ?greenhouse_gas_id=15&next=true

    Это один и тот же GET-метод.
    Query-параметры не создают новый HTTP-метод.
    """

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

        # ----------------------------------------------------
        # Режим "следующий опубликованный парниковый газ"
        # ----------------------------------------------------
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

            greenhouse_gas_ids = [greenhouse_gas.id]

            likes_counts = await get_likes_counts(
                session=session,
                greenhouse_gas_ids=greenhouse_gas_ids,
            )

            liked_greenhouse_gas_ids = (
                await get_user_liked_greenhouse_gas_ids(
                    session=session,
                    user_id=current_user_id,
                    greenhouse_gas_ids=greenhouse_gas_ids,
                )
            )

            return [
                serialize_published_item(
                    greenhouse_gas=greenhouse_gas,
                    likes_count=likes_counts.get(
                        greenhouse_gas.id,
                        0,
                    ),
                    liked_greenhouse_gas_ids=(
                        liked_greenhouse_gas_ids
                    ),
                )
            ]

        # ----------------------------------------------------
        # Обычная лента опубликованных парниковых газов
        # ----------------------------------------------------
        greenhouse_gases = await get_published_greenhouse_gases(
            session=session,
        )

        greenhouse_gas_ids = [
            greenhouse_gas.id
            for greenhouse_gas in greenhouse_gases
        ]

        likes_counts = await get_likes_counts(
            session=session,
            greenhouse_gas_ids=greenhouse_gas_ids,
        )

        liked_greenhouse_gas_ids = (
            await get_user_liked_greenhouse_gas_ids(
                session=session,
                user_id=current_user_id,
                greenhouse_gas_ids=greenhouse_gas_ids,
            )
        )

    return [
        serialize_published_item(
            greenhouse_gas=greenhouse_gas,
            likes_count=likes_counts.get(
                greenhouse_gas.id,
                0,
            ),
            liked_greenhouse_gas_ids=liked_greenhouse_gas_ids,
        )
        for greenhouse_gas in greenhouse_gases
    ]


@router.get(
    "/greenhouse-gases/my-gas",
    response_model=GreenhouseGasDraftResponse,
)
async def get_my_greenhouse_gas(
    current_user_id: int = Depends(get_current_user_id),
):
    """
    GET /api/greenhouse-gases/my-gas

    Возвращает черновик текущего пользователя.
    """

    async with async_session_maker() as session:
        greenhouse_gas = await get_draft_greenhouse_gas(
            session=session,
            creator_id=current_user_id,
        )

    if greenhouse_gas is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Парниковый газ текущего пользователя "
                "не найден"
            ),
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
            greenhouse_gas.image_url,
            DEFAULT_IMAGE_URL,
        ),
        video_url=get_media_url(
            greenhouse_gas.video_url,
            DEFAULT_VIDEO_URL,
        ),
    )


@router.post(
    "/greenhouse-gases",
    response_model=GreenhouseGasCreateResponse,
    status_code=201,
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
    """
    POST /api/greenhouse-gases

    Создание черновика парникового газа.
    Изображение и видео передаются как файлы.
    """

    if not name.strip():
        raise HTTPException(
            status_code=400,
            detail=(
                "Название парникового газа "
                "не может быть пустым"
            ),
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
                detail=(
                    "У пользователя уже существует "
                    "черновик"
                ),
            )

    image_filename = None
    video_filename = None

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
        image_url=get_file_url(
            greenhouse_gas.image_url
        ),
        video_url=get_file_url(
            greenhouse_gas.video_url
        ),
    )


@router.put(
    "/greenhouse-gases/{greenhouse_gas_id}/publish",
    response_model=GreenhouseGasPublishResponse,
)
async def publish_greenhouse_gas_api(
    greenhouse_gas_id: int,
    current_user_id: int = Depends(get_current_user_id),
):
    """
    PUT /api/greenhouse-gases/{id}/publish

    Публикация черновика текущего пользователя.
    """

    async with async_session_maker() as session:
        greenhouse_gas = await publish_api_greenhouse_gas(
            session=session,
            greenhouse_gas_id=greenhouse_gas_id,
            creator_id=current_user_id,
        )

    if greenhouse_gas is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Черновик не найден или "
                "не принадлежит текущему пользователю"
            ),
        )

    return GreenhouseGasPublishResponse(
        id=greenhouse_gas.id,
        name=greenhouse_gas.name,
        status=greenhouse_gas.status,
        image_url=get_file_url(
            greenhouse_gas.image_url
        ),
        video_url=get_file_url(
            greenhouse_gas.video_url
        ),
        published_at=greenhouse_gas.published_at.isoformat(),
    )


@router.post(
    "/greenhouse-gases/{greenhouse_gas_id}/like",
)
async def like_greenhouse_gas(
    greenhouse_gas_id: int,
    like_request: LikeRequest,
    current_user_id: int = Depends(get_current_user_id),
):
    """
    POST /api/greenhouse-gases/{id}/like

    like=1 — поставить лайк.
    like=0 — убрать лайк.
    """

    async with async_session_maker() as session:
        greenhouse_gas = await get_greenhouse_gas_by_id(
            session=session,
            greenhouse_gas_id=greenhouse_gas_id,
        )

        if (
            greenhouse_gas is None
            or greenhouse_gas.status != "опубликован"
        ):
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
)
async def delete_greenhouse_gas_api(
    greenhouse_gas_id: int,
    current_user_id: int = Depends(get_current_user_id),
):
    """
    DELETE /api/greenhouse-gases/{id}

    Логическое удаление.
    Удалять можно только собственный парниковый газ.
    """

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
                "Парниковый газ не найден "
                "или не принадлежит текущему пользователю"
            ),
        )

    return {
        "id": greenhouse_gas.id,
        "status": greenhouse_gas.status,
    }


# ============================================================
# ДОМЕН ПОЛЬЗОВАТЕЛЯ
# ============================================================


@router.post(
    "/users/register",
    response_model=UserRegisterResponse,
    status_code=201,
)
async def register_user(
    request: UserRegisterRequest,
):
    """
    POST /api/users/register

    Регистрация нового пользователя.
    """

    username = request.username.strip()

    if not username:
        raise HTTPException(
            status_code=400,
            detail=(
                "Имя пользователя "
                "не может быть пустым"
            ),
        )

    async with async_session_maker() as session:
        existing_user = await get_user_by_username(
            session=session,
            username=username,
        )

        if existing_user is not None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Пользователь с таким именем "
                    "уже существует"
                ),
            )

        user = await create_user(
            session=session,
            username=username,
            password=request.password,
        )

    return UserRegisterResponse(
        id=user.id,
        username=user.username,
    )


@router.post(
    "/users/auth",
    response_model=AuthStubResponse,
)
async def authenticate_user():
    """
    POST /api/users/auth

    Заглушка авторизации для ЛР4.
    """

    return AuthStubResponse(
        message="Авторизация будет реализована в ЛР4",
    )


@router.post(
    "/users/deauth",
    response_model=AuthStubResponse,
)
async def deauthenticate_user():
    """
    POST /api/users/deauth

    Заглушка выхода из системы для ЛР4.
    """

    return AuthStubResponse(
        message="Выход из системы будет реализован в ЛР4",
    )