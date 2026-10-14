"""Add Phase 4 baseline and regression fields

Revision ID: 0004_phase4_regression
Revises: 0003_phase2_run_engine
Create Date: 2026-10-14 21:58:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_phase4_regression"
down_revision: str | None = "0003_phase2_run_engine"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add baseline_run_id to runs
    op.add_column("runs", sa.Column("baseline_run_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_runs_baseline_run_id",
        "runs",
        "runs",
        ["baseline_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_runs_baseline_run_id"), "runs", ["baseline_run_id"], unique=False)

    # 2. Add summary to runs
    op.add_column("runs", sa.Column("summary", sa.JSON(), nullable=True))

    # 3. Add baseline_run_id to projects
    op.add_column("projects", sa.Column("baseline_run_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_projects_baseline_run_id",
        "projects",
        "runs",
        ["baseline_run_id"],
        ["id"],
        ondelete="SET NULL",
        use_alter=True,
    )
    op.create_index(op.f("ix_projects_baseline_run_id"), "projects", ["baseline_run_id"], unique=False)

    # 4. Add classification, score, and comparison_details to run_results
    op.add_column("run_results", sa.Column("score", sa.Float(), server_default="0.0", nullable=True))
    op.add_column(
        "run_results",
        sa.Column("classification", sa.String(length=32), nullable=True),
    )
    op.create_index(
        op.f("ix_run_results_classification"), "run_results", ["classification"], unique=False
    )
    op.add_column("run_results", sa.Column("comparison_details", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("run_results", "comparison_details")
    op.drop_index(op.f("ix_run_results_classification"), table_name="run_results")
    op.drop_column("run_results", "classification")
    op.drop_column("run_results", "score")

    op.drop_constraint("fk_projects_baseline_run_id", "projects", type_="foreignkey")
    op.drop_index(op.f("ix_projects_baseline_run_id"), table_name="projects")
    op.drop_column("projects", "baseline_run_id")

    op.drop_column("runs", "summary")
    op.drop_constraint("fk_runs_baseline_run_id", "runs", type_="foreignkey")
    op.drop_index(op.f("ix_runs_baseline_run_id"), table_name="runs")
    op.drop_column("runs", "baseline_run_id")
