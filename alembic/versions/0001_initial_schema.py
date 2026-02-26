"""initial_schema

Revision ID: 0001
Revises:
Create Date: 2026-02-26

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # accounts table
    op.create_table(
        'accounts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('access_token', sa.String(), nullable=False),
        sa.Column('ad_account_id', sa.String(), nullable=False),
        sa.Column('app_id', sa.String(), nullable=False),
        sa.Column('app_secret', sa.String(), nullable=False),
        sa.Column('page_id', sa.String(), nullable=False),
        sa.Column('max_daily_budget_usd', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
    )

    # run_logs table
    op.create_table(
        'run_logs',
        sa.Column('run_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('account_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('ingested_data_json', sa.Text(), nullable=True),
        sa.Column('model', sa.String(), nullable=True),
        sa.Column('raw_claude_response', sa.Text(), nullable=True),
        sa.Column('campaign_config_json', sa.Text(), nullable=True),
        sa.Column('campaign_name', sa.String(), nullable=True),
        sa.Column('objective', sa.String(), nullable=True),
        sa.Column('budget_daily_usd', sa.Float(), nullable=True),
        sa.Column('reasoning', sa.Text(), nullable=True),
        sa.Column('strategy_error', sa.Text(), nullable=True),
        sa.Column('approved', sa.Boolean(), nullable=True),
        sa.Column('approval_timestamp', sa.DateTime(), nullable=True),
        sa.Column('dry_run', sa.Boolean(), nullable=True),
        sa.Column('created_campaign_id', sa.String(), nullable=True),
        sa.Column('created_ad_set_ids', sa.Text(), nullable=True),
        sa.Column('created_ad_ids', sa.Text(), nullable=True),
        sa.Column('execution_error', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('run_logs')
    op.drop_table('accounts')
