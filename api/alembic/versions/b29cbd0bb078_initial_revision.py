"""Initial revision

Revision ID: b29cbd0bb078
Revises: 
Create Date: 2020-07-27 11:28:42.510750

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import geoalchemy2

# revision identifiers, used by Alembic.
revision = 'b29cbd0bb078'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic ###
    op.create_table('prediction_models',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('name', sa.String(), nullable=False),
                    sa.Column('abbreviation', sa.String(), nullable=False),
                    sa.Column('projection', sa.String(), nullable=False),
                    sa.PrimaryKeyConstraint('id'),
                    sa.UniqueConstraint('abbreviation', 'projection'),
                    comment='Identifies the Weather Prediction model'
                    )
    op.create_index(op.f('ix_prediction_models_id'),
                    'prediction_models', ['id'], unique=False)
    op.create_table('processed_model_run_files',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('url', sa.String(), nullable=False),
                    sa.Column('create_date', sa.TIMESTAMP(
                        timezone=True), nullable=False),
                    sa.Column('update_date', sa.TIMESTAMP(
                        timezone=True), nullable=False),
                    sa.PrimaryKeyConstraint('id'),
                    sa.UniqueConstraint('url'),
                    comment='Record to indicate that a particular model run file has been processed.'
                    )
    op.create_index(op.f('ix_processed_model_run_files_id'),
                    'processed_model_run_files', ['id'], unique=False)
    op.create_table('prediction_model_grid_subsets',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('prediction_model_id',
                              sa.Integer(), nullable=False),
                    sa.Column('geom', geoalchemy2.types.Geometry(geometry_type='POLYGON',
                                                                 from_text='ST_GeomFromEWKT', name='geometry'), nullable=False),
                    sa.ForeignKeyConstraint(['prediction_model_id'], [
                        'prediction_models.id'], ),
                    sa.PrimaryKeyConstraint('id'),
                    sa.UniqueConstraint('prediction_model_id', 'geom'),
                    comment='Identify the vertices surrounding the area of interest'
                    )
    op.create_index(op.f('ix_prediction_model_grid_subsets_id'),
                    'prediction_model_grid_subsets', ['id'], unique=False)
    op.create_table('prediction_model_runs',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('prediction_model_id',
                              sa.Integer(), nullable=False),
                    sa.Column('prediction_run_timestamp', sa.TIMESTAMP(
                        timezone=True), nullable=False),
                    sa.ForeignKeyConstraint(['prediction_model_id'], [
                        'prediction_models.id'], ),
                    sa.PrimaryKeyConstraint('id'),
                    sa.UniqueConstraint(
                        'prediction_model_id', 'prediction_run_timestamp'),
                    comment='Identify which prediction model run (e.g.  2020 07 07 12:00).'
                    )
    op.create_index(op.f('ix_prediction_model_runs_id'),
                    'prediction_model_runs', ['id'], unique=False)
    op.create_table('model_run_grid_subset_predictions',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('prediction_model_run_id',
                              sa.Integer(), nullable=False),
                    sa.Column('prediction_model_grid_subset_id',
                              sa.Integer(), nullable=False),
                    sa.Column('prediction_timestamp', sa.TIMESTAMP(
                        timezone=True), nullable=False),
                    sa.Column('tmp_tgl_2', postgresql.ARRAY(
                        sa.Float()), nullable=True),
                    sa.Column('rh_tgl_2', postgresql.ARRAY(
                        sa.Float()), nullable=True),
                    sa.ForeignKeyConstraint(['prediction_model_grid_subset_id'], [
                        'prediction_model_grid_subsets.id'], ),
                    sa.ForeignKeyConstraint(['prediction_model_run_id'], [
                        'prediction_model_runs.id'], ),
                    sa.PrimaryKeyConstraint('id'),
                    sa.UniqueConstraint('prediction_model_run_id',
                                        'prediction_model_grid_subset_id', 'prediction_timestamp'),
                    comment='The prediction for a grid subset of a particular model run.'
                    )
    op.create_index(op.f('ix_model_run_grid_subset_predictions_id'),
                    'model_run_grid_subset_predictions', ['id'], unique=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic ###
    op.drop_index(op.f('ix_model_run_grid_subset_predictions_id'),
                  table_name='model_run_grid_subset_predictions')
    op.drop_table('model_run_grid_subset_predictions')
    op.drop_index(op.f('ix_prediction_model_runs_id'),
                  table_name='prediction_model_runs')
    op.drop_table('prediction_model_runs')
    op.drop_index(op.f('ix_prediction_model_grid_subsets_id'),
                  table_name='prediction_model_grid_subsets')
    op.drop_table('prediction_model_grid_subsets')
    op.drop_index(op.f('ix_processed_model_run_files_id'),
                  table_name='processed_model_run_files')
    op.drop_table('processed_model_run_files')
    op.drop_index(op.f('ix_prediction_models_id'),
                  table_name='prediction_models')
    op.drop_table('prediction_models')
    # ### end Alembic commands ###
