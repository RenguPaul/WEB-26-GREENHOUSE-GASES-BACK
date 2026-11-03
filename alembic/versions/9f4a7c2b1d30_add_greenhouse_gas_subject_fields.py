"""add subject fields to greenhouse gases

Revision ID: 9f4a7c2b1d30
Revises: 387e381fb912
Create Date: 2026-09-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9f4a7c2b1d30"
down_revision: Union[str, Sequence[str], None] = "387e381fb912"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "greenhouse_gases",
        sa.Column(
            "formula",
            sa.String(length=50),
            nullable=True,
        ),
    )

    op.add_column(
        "greenhouse_gases",
        sa.Column(
            "global_warming_potential_100y",
            sa.Float(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "greenhouse_gases",
        "global_warming_potential_100y",
    )

    op.drop_column(
        "greenhouse_gases",
        "formula",
    )