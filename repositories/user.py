from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User


async def get_user_by_username(
    session: AsyncSession,
    username: str,
) -> User | None:
    result = await session.execute(
        select(User)
        .where(User.username == username)
    )

    return result.scalar_one_or_none()


async def create_user(
    session: AsyncSession,
    username: str,
    password: str,
) -> User:
    user = User(
        username=username,
        password=password,
    )

    session.add(user)

    await session.commit()
    await session.refresh(user)

    return user