"""Add execution configuration, repeat counts, idempotency, and cache expiry

Revision ID: 0005_hardening_and_flakiness
Revises: 0004_phase4_regression
Create Date: 2026-10-15 15:50:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005_hardening_and_flakiness"
down_revision: str | None = "0004_phase4_regression"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add model and generation configuration to prompt_versions
    op.add_column(
        "prompt_versions",
        sa.Column("model", sa.String(length=64), server_default="gemini-2.5-flash", nullable=False),
    )
    op.add_column("prompt_versions", sa.Column("system_instruction", sa.Text(), nullable=True))
    op.add_column(
        "prompt_versions",
        sa.Column("temperature", sa.Float(), server_default="1.0", nullable=False),
    )
    op.add_column("prompt_versions", sa.Column("top_p", sa.Float(), nullable=True))
    op.add_column("prompt_versions", sa.Column("max_output_tokens", sa.Integer(), nullable=True))
    op.add_column("prompt_versions", sa.Column("response_mime_type", sa.String(length=64), nullable=True))

    # 2. Add repeat_count and idempotency_key to runs
    op.add_column("runs", sa.Column("repeat_count", sa.Integer(), server_default="1", nullable=False))
    op.add_column("runs", sa.Column("idempotency_key", sa.String(length=128), nullable=True))
    op.create_index(op.f("ix_runs_idempotency_key"), "runs", ["idempotency_key"], unique=False)

    # 3. Add repeat_index to run_results and update unique constraint
    op.add_column(
        "run_results",
        sa.Column("repeat_index", sa.Integer(), server_default="0", nullable=False),
    )
    try:
        op.drop_constraint("uq_run_test_case", "run_results", type_="unique")
    except Exception:
        pass
    op.create_unique_constraint(
        "uq_run_test_case_repeat",
        "run_results",
        ["run_id", "test_case_id", "repeat_index"],
    )

    # 4. Add expires_at to output_cache
    op.add_column("output_cache", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f("ix_output_cache_expires_at"), "output_cache", ["expires_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_output_cache_expires_at"), table_name="output_cache")
    op.drop_column("output_cache", "expires_at")

    op.drop_constraint("uq_run_test_case_repeat", "run_results", type_="unique")
    op.create_unique_constraint("uq_run_test_case", "run_results", ["run_id", "test_case_id"])
    op.drop_column("run_results", "repeat_index")

    op.drop_index(op.f("ix_runs_idempotency_key"), table_name="runs")
    op.drop_column("runs", "idempotency_key")
    op.drop_column("runs", "repeat_count")

    op.drop_column("prompt_versions", "response_mime_type")
    op.drop_column("prompt_versions", "max_output_tokens")
    op.drop_column("prompt_versions", "top_p")
    op.drop_column("prompt_versions", "temperature")
    op.drop_column("prompt_versions", "system_instruction")
    op.drop_column("prompt_versions", "model")
