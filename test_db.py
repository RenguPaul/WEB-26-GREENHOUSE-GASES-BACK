import asyncio

from sqlalchemy import text

from db.session import engine


async def test_connection():
    async with engine.connect() as connection:
        result = await connection.execute(text("SELECT 1"))
        print("PostgreSQL connection:", result.scalar())


if __name__ == "__main__":
    asyncio.run(test_connection())