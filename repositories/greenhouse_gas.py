from datetime import datetime

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from models.greenhouse_gas import GreenhouseGas
from models.like import Like


async def get_published_greenhouse_gases(
    session: AsyncSession,
    concentration: float | None = None,
) -> list[GreenhouseGas]:
    query = (
        select(GreenhouseGas)
        .where(GreenhouseGas.status == "опубликован")
        .order_by(GreenhouseGas.id)
    )

    if concentration is not None:
        query = query.where(
            GreenhouseGas.concentration_ppm <= concentration
        )

    result = await session.execute(query)

    return list(result.scalars().all())


async def get_greenhouse_gas_by_id(
    session: AsyncSession,
    greenhouse_gas_id: int,
) -> GreenhouseGas | None:
    result = await session.execute(
        select(GreenhouseGas)
        .where(
            GreenhouseGas.id == greenhouse_gas_id,
            GreenhouseGas.status == "опубликован",
        )
    )

    return result.scalar_one_or_none()


async def get_draft_greenhouse_gas(
    session: AsyncSession,
    creator_id: int,
) -> GreenhouseGas | None:
    result = await session.execute(
        select(GreenhouseGas)
        .where(
            GreenhouseGas.status == "черновик",
            GreenhouseGas.creator_id == creator_id,
        )
        .order_by(GreenhouseGas.id)
    )

    return result.scalars().first()


async def create_draft_greenhouse_gas(
    session: AsyncSession,
    name: str,
    image_url: str | None,
    video_url: str | None,
    creator_id: int,
) -> GreenhouseGas:
    draft = GreenhouseGas(
        name=name,
        status="черновик",
        image_url=image_url,
        video_url=video_url,
        creator_id=creator_id,
    )

    session.add(draft)

    await session.commit()
    await session.refresh(draft)

    return draft


async def publish_greenhouse_gas(
    session: AsyncSession,
    greenhouse_gas_id: int,
    short_description: str,
    formula: str,
    global_warming_potential_100y: float,
    concentration_ppm: float,
    temperature_change_c: float,
) -> GreenhouseGas | None:
    result = await session.execute(
        select(GreenhouseGas)
        .where(
            GreenhouseGas.id == greenhouse_gas_id,
            GreenhouseGas.status == "черновик",
        )
    )

    greenhouse_gas = result.scalar_one_or_none()

    if greenhouse_gas is None:
        return None

    greenhouse_gas.short_description = short_description
    greenhouse_gas.formula = formula
    greenhouse_gas.global_warming_potential_100y = (
        global_warming_potential_100y
    )
    greenhouse_gas.concentration_ppm = concentration_ppm
    greenhouse_gas.temperature_change_c = temperature_change_c
    greenhouse_gas.status = "опубликован"
    greenhouse_gas.published_at = datetime.utcnow()

    await session.commit()
    await session.refresh(greenhouse_gas)

    return greenhouse_gas


async def delete_greenhouse_gas(
    session: AsyncSession,
    greenhouse_gas_id: int,
) -> None:
    await session.execute(
        text(
            """
            UPDATE greenhouse_gases
            SET status = 'удален'
            WHERE id = :greenhouse_gas_id
            """
        ),
        {
            "greenhouse_gas_id": greenhouse_gas_id,
        },
    )

    await session.commit()


async def get_likes_counts(
    session: AsyncSession,
    greenhouse_gas_ids: list[int],
) -> dict[int, int]:
    if not greenhouse_gas_ids:
        return {}

    result = await session.execute(
        select(
            Like.greenhouse_gas_id,
            func.count(Like.user_id),
        )
        .where(
            Like.greenhouse_gas_id.in_(greenhouse_gas_ids)
        )
        .group_by(Like.greenhouse_gas_id)
    )

    return {
        greenhouse_gas_id: likes_count
        for greenhouse_gas_id, likes_count in result.all()
    }