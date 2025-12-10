"""empty message

Revision ID: 7d225675e312
Revises: 3e588a47adb0
Create Date: 2025-10-15 15:37:24.491996

"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "7d225675e312"
down_revision: Union[str, Sequence[str], None] = "3e588a47adb0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
