import asyncio

from repositories.greenhouse_gas import get_published_greenhouse_gases
from db.session import async_session_maker


async def test_orm():
    async with async_session_maker() as session:
        greenhouse_gases = await get_published_greenhouse_gases(session)

        print("Published greenhouse gases:")
        for gas in greenhouse_gases:
            print(
                gas.id,
                gas.name,
                gas.status,
                gas.concentration_ppm,
                gas.temperature_change_c,
            )


if __name__ == "__main__":
    asyncio.run(test_orm())