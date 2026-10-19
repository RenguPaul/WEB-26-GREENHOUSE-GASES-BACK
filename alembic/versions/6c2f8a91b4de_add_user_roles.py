"""Add user roles for Lab 4.

Revision ID: 6c2f8a91b4de
Revises: 1f6baa44e145
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "6c2f8a91b4de"
down_revision: Union[str, Sequence[str], None] = "1f6baa44e145"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("role", sa.String(length=30), nullable=False, server_default="user"),
    )
    op.create_check_constraint(
        "ck_users_role_valid",
        "users",
        "role IN ('user', 'moderator')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_role_valid", "users", type_="check")
    op.drop_column("users", "role")
