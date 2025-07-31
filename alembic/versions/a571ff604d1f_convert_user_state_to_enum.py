"""Convert user.state to enum

Revision ID: a571ff604d1f
Revises: f3f6b1a86d5e
Create Date: 2025-07-31 01:29:00.644545

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a571ff604d1f'
down_revision: Union[str, Sequence[str], None] = 'f3f6b1a86d5e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
