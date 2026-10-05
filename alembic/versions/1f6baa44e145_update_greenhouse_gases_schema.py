"""update greenhouse gases schema

Revision ID: 1f6baa44e145
Revises: 9f4a7c2b1d30
Create Date: 2026-10-03 20:44:56.018900

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "1f6baa44e145"
down_revision: Union[str, Sequence[str], None] = "9f4a7c2b1d30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DEFAULT_IMAGE_URL = "/static/media/default-greenhouse.svg"
DEFAULT_VIDEO_URL = "/static/media/default-greenhouse.mp4"


def upgrade() -> None:
    """Upgrade schema."""

    # 1. Добавляем пароль пользователям временно как nullable,
    # чтобы можно было заполнить существующие записи.
    op.add_column(
        "users",
        sa.Column(
            "password",
            sa.String(length=255),
            nullable=True,
        ),
    )

    # 2. Заполняем пароль для уже существующих пользователей.
    op.execute(
        sa.text(
            """
            UPDATE users
            SET password = 'test_password'
            WHERE password IS NULL
            """
        )
    )

    # 3. После заполнения делаем поле обязательным.
    op.alter_column(
        "users",
        "password",
        existing_type=sa.String(length=255),
        nullable=False,
    )

    # 4. У существующих газов, у которых отсутствуют ссылки
    # на медиафайлы, устанавливаем стандартные файлы.
    op.execute(
        sa.text(
            """
            UPDATE greenhouse_gases
            SET image_url = :image_url
            WHERE image_url IS NULL
            """
        ).bindparams(image_url=DEFAULT_IMAGE_URL)
    )

    op.execute(
        sa.text(
            """
            UPDATE greenhouse_gases
            SET video_url = :video_url
            WHERE video_url IS NULL
            """
        ).bindparams(video_url=DEFAULT_VIDEO_URL)
    )

    # 5. URL изображения и видео становятся обязательными.
    op.alter_column(
        "greenhouse_gases",
        "image_url",
        existing_type=sa.String(length=500),
        nullable=False,
    )

    op.alter_column(
        "greenhouse_gases",
        "video_url",
        existing_type=sa.String(length=500),
        nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema."""

    # Возвращаем media URL обратно в nullable.
    op.alter_column(
        "greenhouse_gases",
        "video_url",
        existing_type=sa.String(length=500),
        nullable=True,
    )

    op.alter_column(
        "greenhouse_gases",
        "image_url",
        existing_type=sa.String(length=500),
        nullable=True,
    )

    # Удаляем пароль из users.
    op.drop_column("users", "password")