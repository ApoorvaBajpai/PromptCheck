"""Initial schema baseline

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-14 19:00:00.000000

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Phase 0 baseline schema placeholder
    pass


def downgrade() -> None:
    pass
