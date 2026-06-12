"""027_add_business_goals

Create the single-row Business Goals charter table and seed the singleton row
(INTENT.md §9). One row, fixed primary key, JSON columns for the structured
sub-models. Seeded with the §9 illustration defaults: gated autonomy, a $200
monthly budget, and at most 2 active products.

Revision ID: 027_add_business_goals
Revises: 026_token_usage_tables
Create Date: 2026-06-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "027_add_business_goals"
down_revision = "026_token_usage_tables"
branch_labels = None
depends_on = None

# Fixed singleton id — must match SINGLETON_ID in roboco/models/business_goals.py
SINGLETON_ID = "00000000-0000-0000-0000-000000000001"

# Operating-policy defaults from the INTENT §9 illustration (the leash).
_DEFAULT_OPERATING_POLICY = {
    "autonomy_level": "gated",
    "gate_list": ["spend", "go_public", "new_product_line", "cap_breach"],
    "monthly_budget_usd": 200,
    "max_active_products": 2,
    "strategy_cadence": "weekly",
    "provisioning": {
        "github_org": None,
        "default_repo_visibility": "private",
        "naming": None,
    },
}


def upgrade() -> None:
    op.create_table(
        "business_goals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("north_star", sa.Text, nullable=False, server_default=""),
        sa.Column("constraints", sa.JSON, nullable=False),
        sa.Column("objectives", sa.JSON, nullable=False),
        sa.Column("operating_policy", sa.JSON, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Seed the singleton row with the INTENT §9 defaults so the charter exists
    # the moment the app boots — no agent ever briefs against a missing artifact.
    business_goals = sa.table(
        "business_goals",
        sa.column("id", UUID(as_uuid=True)),
        sa.column("north_star", sa.Text),
        sa.column("constraints", sa.JSON),
        sa.column("objectives", sa.JSON),
        sa.column("operating_policy", sa.JSON),
    )
    op.bulk_insert(
        business_goals,
        [
            {
                "id": SINGLETON_ID,
                "north_star": "",
                "constraints": [],
                "objectives": [],
                "operating_policy": _DEFAULT_OPERATING_POLICY,
            }
        ],
    )


def downgrade() -> None:
    op.drop_table("business_goals")
