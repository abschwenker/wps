""" Fetch c-haines geojson
"""
from datetime import datetime
import logging
import app.db.database


logger = logging.getLogger(__name__)


async def fetch(model_run_timestamp: datetime, prediction_timestamp: datetime):
    """ Fetch polygon geojson
    """
    logger.info('model: %s; prediction: %s', model_run_timestamp, prediction_timestamp)
    # TODO: Add filters for model and timestamp (returning only the most recent model run)
    session = app.db.database.get_read_session()
    # Ordering by severity, ascending is important to ensure that
    # higher severity is placed over lower severity. (On the front end,
    # it makes it easier to have the high severity border sit on top and
    # pop nicely.)
    # TODO: This isn't safe - sql injection could happen! Fix.
    query = """select json_build_object(
        'type', 'FeatureCollection',
        'features', json_agg(ST_AsGeoJSON(t.*)::json)
    )
        from (
        select geom, severity from prediction_model_c_haines_polygons
        where 
            prediction_timestamp = '{prediction_timestamp}' and
            model_run_timestamp = '{model_run_timestamp}'
        order by severity asc
    ) as t(geom, severity)""".format(
        prediction_timestamp=prediction_timestamp.isoformat(),
        model_run_timestamp=model_run_timestamp.isoformat())
    # something is wrong here.
    logger.info('fetching geojson from db...')
    # pylint: disable=no-member
    response = session.execute(query)
    row = next(response)
    logger.info('returning response...')
    return row[0]


async def fetch_model_runs():
    pass
