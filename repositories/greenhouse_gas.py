from datetime import datetime

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from models.greenhouse_gas import GreenhouseGas
from models.like import Like


# ============================================================
# ПОЛУЧЕНИЕ ОПУБЛИКОВАННЫХ ПАРНИКОВЫХ ГАЗОВ
# ============================================================

async def get_published_greenhouse_gases(
    session: AsyncSession,
    concentration: float | None = None,
):
    """
    Получение опубликованных парниковых газов
    через SQLAlchemy ORM.

    Если передана concentration,
    выполняется серверная фильтрация.
    """

    stmt = select(GreenhouseGas).where(
        GreenhouseGas.status == "опубликован"
    )

    if concentration is not None:
        stmt = stmt.where(
            GreenhouseGas.concentration_ppm
            <= concentration
        )

    stmt = stmt.order_by(
        GreenhouseGas.id
    )

    result = await session.execute(stmt)

    return result.scalars().all()


# ============================================================
# ПОЛУЧЕНИЕ ОДНОГО ОПУБЛИКОВАННОГО ГАЗА
# ============================================================

async def get_greenhouse_gas_by_id(
    session: AsyncSession,
    greenhouse_gas_id: int,
):
    """
    Получение одного опубликованного
    парникового газа по ID через ORM.
    """

    stmt = select(GreenhouseGas).where(
        GreenhouseGas.id == greenhouse_gas_id,
        GreenhouseGas.status == "опубликован",
    )

    result = await session.execute(stmt)

    return result.scalar_one_or_none()


# ============================================================
# ПОЛУЧЕНИЕ ЧЕРНОВИКА ПОЛЬЗОВАТЕЛЯ
# ============================================================

async def get_draft_greenhouse_gas(
    session: AsyncSession,
    creator_id: int,
):
    """
    Получение черновика конкретного пользователя.

    По требованиям Lab 2 у одного пользователя
    может быть не более одного черновика.
    """

    stmt = select(GreenhouseGas).where(
        GreenhouseGas.creator_id == creator_id,
        GreenhouseGas.status == "черновик",
    )

    result = await session.execute(stmt)

    return result.scalar_one_or_none()


# ============================================================
# СОЗДАНИЕ ЧЕРНОВИКА
# ============================================================

async def create_draft_greenhouse_gas(
    session: AsyncSession,
    name: str,
    creator_id: int,
):
    """
    Создание черновика через SQLAlchemy ORM.
    """

    greenhouse_gas = GreenhouseGas(
        name=name,
        status="черновик",
        creator_id=creator_id,
    )

    session.add(greenhouse_gas)

    await session.commit()

    await session.refresh(
        greenhouse_gas
    )

    return greenhouse_gas


# ============================================================
# ПУБЛИКАЦИЯ
# ============================================================

async def publish_greenhouse_gas(
    session: AsyncSession,
    greenhouse_gas_id: int,
    short_description: str,
    global_warming_potential_100y: float,
    concentration_ppm: float,
    temperature_change_c: float,
):
    """
    Заполняет черновик и переводит его
    в статус "опубликован".

    Все изменения выполняются через ORM.
    """

    stmt = select(GreenhouseGas).where(
        GreenhouseGas.id == greenhouse_gas_id,
        GreenhouseGas.status == "черновик",
    )

    result = await session.execute(stmt)

    greenhouse_gas = (
        result.scalar_one_or_none()
    )

    if greenhouse_gas is None:
        return None

    greenhouse_gas.short_description = (
        short_description
    )

    greenhouse_gas.global_warming_potential_100y = (
        global_warming_potential_100y
    )

    greenhouse_gas.concentration_ppm = (
        concentration_ppm
    )

    greenhouse_gas.temperature_change_c = (
        temperature_change_c
    )

    greenhouse_gas.status = "опубликован"

    greenhouse_gas.published_at = (
        datetime.utcnow()
    )

    await session.commit()

    await session.refresh(
        greenhouse_gas
    )

    return greenhouse_gas


# ============================================================
# ЛОГИЧЕСКОЕ УДАЛЕНИЕ
# ============================================================

async def delete_greenhouse_gas(
    session: AsyncSession,
    greenhouse_gas_id: int,
):
    """
    Логическое удаление.

    ВАЖНО:
    здесь специально используется raw SQL,
    потому что это требование лабораторной.

    Физического DELETE нет.
    """

    await session.execute(
        text(
            """
            UPDATE greenhouse_gases
            SET status = 'удален'
            WHERE id = :greenhouse_gas_id
            """
        ),
        {
            "greenhouse_gas_id":
                greenhouse_gas_id
        },
    )

    await session.commit()


# ============================================================
# КОЛИЧЕСТВО ЛАЙКОВ
# ============================================================

async def get_likes_counts(
    session: AsyncSession,
    greenhouse_gas_ids: list[int],
):
    """
    Получает количество лайков для списка
    парниковых газов.

    Лайки не изменяются.
    Только читается их количество.
    """

    if not greenhouse_gas_ids:
        return {}

    stmt = (
        select(
            Like.greenhouse_gas_id,
            func.count(Like.user_id),
        )
        .where(
            Like.greenhouse_gas_id.in_(
                greenhouse_gas_ids
            )
        )
        .group_by(
            Like.greenhouse_gas_id
        )
    )

    result = await session.execute(stmt)

    return {
        row[0]: row[1]
        for row in result.all()
    }

