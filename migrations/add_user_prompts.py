"""Add user_prompts table

Revision ID: add_user_prompts
Revises: (your_previous_revision)
Create Date: 2026-01-17

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'add_user_prompts'
down_revision = None  # Update this to your latest migration
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create user_prompts table
    op.create_table(
        'user_prompts',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('user_id', sa.String(length=100), nullable=False, comment='Chainlit user identifier'),
        sa.Column('prompt_type', sa.String(length=20), nullable=False, comment="Type of prompt: 'sql' or 'kb'"),
        sa.Column('prompt_text', sa.Text(), nullable=False, comment='The custom prompt text'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()'), comment='When prompt was created'),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()'), comment='Last update timestamp'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'prompt_type', name='uq_user_prompt_type'),
        sa.CheckConstraint("prompt_type IN ('sql', 'kb')", name='ck_prompt_type'),
        sa.CheckConstraint("LENGTH(prompt_text) >= 20 AND LENGTH(prompt_text) <= 5000", name='ck_prompt_length'),
    )

    # Create indexes
    op.create_index('idx_user_prompts_user_type', 'user_prompts', ['user_id', 'prompt_type'])
    op.create_index(op.f('ix_user_prompts_user_id'), 'user_prompts', ['user_id'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index(op.f('ix_user_prompts_user_id'), table_name='user_prompts')
    op.drop_index('idx_user_prompts_user_type', table_name='user_prompts')

    # Drop table
    op.drop_table('user_prompts')
