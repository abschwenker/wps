"""record if record has been interpolated

Revision ID: 402cff253825
Revises: ee2df2ebe8c0
Create Date: 2020-09-03 10:52:00.745576

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '402cff253825'
down_revision = 'ee2df2ebe8c0'
branch_labels = None
depends_on = None


def upgrade():
    # Add "interpolated" column.
    op.add_column('prediction_model_run_timestamps', sa.Column('interpolated', sa.Boolean(), nullable=True))
    # Mark all rows as NOT interpolated.
    op.execute('update prediction_model_run_timestamps set interpolated = False')
    # Set column to nullable=False.
    op.alter_column('prediction_model_run_timestamps', 'interpolated',
                    existing_type=sa.BOOLEAN(),
                    nullable=False)


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('prediction_model_run_timestamps', 'interpolated')
    # ### end Alembic commands ###
