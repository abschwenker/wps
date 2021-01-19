""" Routes for c-haines
"""
from datetime import datetime
import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.weather_models.fetch import c_haines

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/c-haines",
)


@router.get('/')
async def get_c_haines(model_run_timestamp: datetime, prediction_timestamp: datetime):
    """ Return geojson polygons for c-haines """
    # response.headers["Cache-Control"] = "max-age=43200"  # let browsers to cache the data for 12 hours
    logger.info('/c-haines/?model_run_timestamp=%s&prediction_timestamp=%s',
                model_run_timestamp, prediction_timestamp)
    headers = {"Cache-Control": "max-age=43200"}
    return JSONResponse(
        content=await c_haines.fetch(model_run_timestamp, prediction_timestamp),
        headers=headers)
    # return await c_haines.fetch(None, None)


@router.get('/model-runs')
async def get_model_runs():
    """ Return a list of recent model runs """
    logger.info('/c-haines/model-runs')
    return await c_haines.fetch_model_runs()


# @router.get('/predictions')
# async def get_predictions(model_run_timestamp: datetime):
#     """ Return list of predictions for a model run """
#     return await c_haines.fetch_model_run_predictions(model_run_timestamp)
