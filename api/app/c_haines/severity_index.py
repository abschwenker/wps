""" Logic pertaining to the generation of c_haines severity index from GDAL datasets.
"""
import os
from datetime import datetime, timezone, timedelta
from typing import Final
from contextlib import contextmanager
import tempfile
import logging
import json
import gdal
import ogr
import numpy
from pyproj import Transformer, Proj
from shapely.ops import transform
from shapely.geometry import shape
from sqlalchemy.orm import Session
from app.time_utils import get_utc_now
import app.db.database
from app.db.models import CHainesPoly, CHainesPrediction, CHainesModelRun
from app.db.crud.weather_models import get_prediction_model
from app.db.crud.c_haines import (get_c_haines_prediction, get_or_create_c_haines_model_run)
from app.weather_models import ModelEnum, ProjectionEnum
from app.weather_models.process_grib import NAD83
from app.weather_models.env_canada import (get_model_run_hours,
                                           get_file_date_part, adjust_model_day, download,
                                           UnhandledPredictionModelType)
from app.c_haines.c_haines_index import CHainesGenerator
from app.c_haines import GDALData


logger = logging.getLogger(__name__)


def get_severity(c_haines_index):
    """ Return the "severity" of the continuous haines index.

    Fire behavrious analysts are typically only concerned if there's a high
    or extreme index - so the c-haines values are lumped together by severity.

    The severity used here is fairly arbitrary - there's no standard in place.
    """
    # 0 - 4 : low
    if c_haines_index < 4:
        return 0
    # 4 - 8 : moderate
    if c_haines_index < 8:
        return 1
    # 8 - 11 : high
    if c_haines_index < 11:
        return 2
    # 11 + Extreme
    return 3


@contextmanager
def open_gdal(filename_tmp_700: str, filename_tmp_850: str, filename_dew_850: str) -> GDALData:
    """ Open gdal, and yield handy object containing all the data """
    try:
        # Open the datasets.
        grib_tmp_700 = gdal.Open(filename_tmp_700, gdal.GA_ReadOnly)
        grib_tmp_850 = gdal.Open(filename_tmp_850, gdal.GA_ReadOnly)
        grib_dew_850 = gdal.Open(filename_dew_850, gdal.GA_ReadOnly)
        # Yield handy object.
        yield GDALData(grib_tmp_700, grib_tmp_850, grib_dew_850)
    finally:
        # Clean up memory.
        del grib_tmp_700, grib_tmp_850, grib_dew_850


def record_exists(
        session,
        model_run: CHainesModelRun,
        prediction_timestamp: datetime):
    """ Check if we have a c-haines record """
    result = get_c_haines_prediction(session, model_run, prediction_timestamp)
    return result.count() > 0


def get_prediction_date(model_run_timestamp, hour) -> datetime:
    """ Construct the part of the filename that contains the model run date
    """
    return model_run_timestamp + timedelta(hours=hour)


def model_prediction_hour_iterator(model: ModelEnum):
    """ Return a prediction hour iterator.
    Each model has a slightly different set of prediction hours. """
    if model == ModelEnum.GDPS:
        # GDPS goes out real far, but in 3 hour intervals.
        for hour in range(0, 241, 3):
            yield hour
    elif model == ModelEnum.RDPS:
        # RDPS goes out 3 1/2 days.
        for hour in range(0, 85):
            yield hour
    elif model == ModelEnum.HRDPS:
        # HRDPS goes out 2 days.
        for hour in range(0, 49):
            yield hour
    else:
        raise UnhandledPredictionModelType()


def make_model_run_base_url(model: ModelEnum, model_run_start: str, forecast_hour: str):
    """ Return the base url for the grib file.
    The location of the files differs slightly for each model. """
    if model == ModelEnum.GDPS:
        return 'https://dd.weather.gc.ca/model_gem_global/15km/grib2/lat_lon/{HH}/{hhh}/'.format(
            HH=model_run_start, hhh=forecast_hour)
    if model == ModelEnum.RDPS:
        return 'https://dd.weather.gc.ca/model_gem_regional/10km/grib2/{HH}/{hhh}/'.format(
            HH=model_run_start, hhh=forecast_hour
        )
    if model == ModelEnum.HRDPS:
        return 'https://dd.weather.gc.ca/model_hrdps/continental/grib2/{HH}/{hhh}/'.format(
            HH=model_run_start, hhh=forecast_hour)
    raise UnhandledPredictionModelType()


def make_model_run_filename(
        model: ModelEnum, level: str, date: str, model_run_start: str, forecast_hour: str):
    """ Return the filename of the grib file.
    The filename for each model differs slightly. """
    if model == ModelEnum.GDPS:
        return 'CMC_glb_{}_latlon.15x.15_{}{HH}_P{hhh}.grib2'.format(
            level, date, HH=model_run_start, hhh=forecast_hour)
    if model == ModelEnum.RDPS:
        return 'CMC_reg_{}_ps10km_{}{HH}_P{hhh}.grib2'.format(
            level, date, HH=model_run_start, hhh=forecast_hour)
    if model == ModelEnum.HRDPS:
        return 'CMC_hrdps_continental_{level}_ps2.5km_{date}{HH}_P{hhh}-00.grib2'.format(
            level=level, date=date, HH=model_run_start, hhh=forecast_hour)
    raise UnhandledPredictionModelType()


def make_model_levels(model: ModelEnum):
    """ Return list of layers. (The layers are named slightly differently for HRDPS) """
    if model == ModelEnum.HRDPS:
        return ['TMP_ISBL_0700', 'TMP_ISBL_0850', 'DEPR_ISBL_0850']
    return ['TMP_ISBL_700', 'TMP_ISBL_850', 'DEPR_ISBL_850']


def make_model_run_download_urls(model: ModelEnum,
                                 now: datetime,
                                 model_run_hour: int,
                                 prediction_hour: int):
    """ Return urls to download model runs """

    # hh: model run start, in UTC [00, 12]
    # hhh: prediction hour [000, 003, 006, ..., 240]
    levels: Final = make_model_levels(model)
    # pylint: disable=invalid-name
    hh = '{:02d}'.format(model_run_hour)
    # For the global model, we have prediction at 3 hour intervals up to 240 hours.
    hhh = format(prediction_hour, '03d')

    base_url = make_model_run_base_url(model, hh, hhh)
    date = get_file_date_part(now, model_run_hour)

    adjusted_model_time = adjust_model_day(now, model_run_hour)
    model_run_timestamp = datetime(year=adjusted_model_time.year,
                                   month=adjusted_model_time.month,
                                   day=adjusted_model_time.day,
                                   hour=model_run_hour,
                                   tzinfo=timezone.utc)

    prediction_timestamp = get_prediction_date(model_run_timestamp, prediction_hour)
    urls = {}
    for level in levels:
        filename = make_model_run_filename(model, level, date, hh, hhh)
        urls[level] = base_url + filename

    return urls, model_run_timestamp, prediction_timestamp


class SourceInfo():
    """ Handy class to store source information in. """

    def __init__(self, projection, geotransform, rows: int, cols: int):
        self.projection = projection
        self.geotransform = geotransform
        self.rows: int = rows
        self.cols: int = cols


def create_in_memory_band(data: numpy.ndarray, source_info: SourceInfo):
    """ Create an in memory data band """
    mem_driver = gdal.GetDriverByName('MEM')

    dataset = mem_driver.Create('memory', source_info.cols, source_info.rows, 1, gdal.GDT_Byte)
    dataset.SetProjection(source_info.projection)
    dataset.SetGeoTransform(source_info.geotransform)
    band = dataset.GetRasterBand(1)
    band.WriteArray(data)

    return dataset, band


def save_data_as_geojson(
        ch_data: numpy.ndarray,
        mask_data: numpy.ndarray,
        source_info: SourceInfo,
        target_filename: str):
    """ Save data as geojson polygon """
    logger.info('Saving output as geojson %s...', target_filename)

    # Create data band.
    data_ds, data_band = create_in_memory_band(
        ch_data, source_info)

    # Create mask band.
    mask_ds, mask_band = create_in_memory_band(
        mask_data, source_info)

    # Create a GeoJSON layer.
    geojson_driver = ogr.GetDriverByName('GeoJSON')
    dst_ds = geojson_driver.CreateDataSource(target_filename)
    dst_layer = dst_ds.CreateLayer('C-Haines')
    field_name = ogr.FieldDefn("severity", ogr.OFTInteger)
    field_name.SetWidth(24)
    dst_layer.CreateField(field_name)

    # Turn the rasters into polygons.
    gdal.Polygonize(data_band, mask_band, dst_layer, 0, [], callback=None)

    # Ensure that all data in the target dataset is written to disk.
    dst_ds.FlushCache()
    # Explicitly clean up (is this needed?)
    del dst_ds, data_ds, mask_ds


def save_geojson_to_database(session: Session,
                             source_projection, filename: str,
                             prediction_timestamp: datetime,
                             model_run: CHainesModelRun):
    """ Open geojson file, iterate through features, saving them into the
    databse.
    """
    logger.info('Saving geojson for prediction %s to database...', prediction_timestamp)
    # Open the geojson file.
    with open(filename) as file:
        data = json.load(file)

    # Source coordinate system, must match source data.
    proj_from = Proj(projparams=source_projection)
    # Destination coordinate systems (NAD83, geographic coordinates)
    proj_to = Proj(NAD83)
    project = Transformer.from_proj(proj_from, proj_to, always_xy=True)

    # Create a prediction record to hang everything off of:
    prediction = CHainesPrediction(model_run=model_run,
                                   prediction_timestamp=prediction_timestamp)
    session.add(prediction)
    # Convert each feature into a shapely geometry and save to database.
    for feature in data['features']:
        # Create polygon:
        source_geometry = shape(feature['geometry'])
        # Transform polygon from source to NAD83
        geometry = transform(project.transform, source_geometry)
        # Create data model object.
        polygon = CHainesPoly(
            geom=geometry.wkt,
            severity=feature['properties']['severity'],
            c_haines_prediction=prediction)
        # Add to current session.
        session.add(polygon)
    # Only commit once we have everything.
    session.commit()


def generate_severity_data(c_haines_data):
    """ Generate severity index data, iterating over c-haines data.
    NOTE: Iterating to generate c-haines, and then iterating again to generate severity is a bit slower,
    but results in much cleaner code.
    """
    logger.info('Generating c-haines severity index data.')
    severity_data = []
    mask_data = []
    for row in c_haines_data:
        severity_row = []
        mask_row = []
        for cell in row:
            severity = get_severity(cell)
            severity_row.append(severity)
            # We ignore severity 0.
            if severity == 0:
                mask_row.append(0)
            else:
                mask_row.append(1)
        severity_data.append(severity_row)
        mask_data.append(mask_row)
    return numpy.array(severity_data), numpy.array(mask_data)


class EnvCanadaPayload():
    """ Handy class to store payload information in. """

    def __init__(self):
        self.filename_tmp_700: str = None
        self.filename_tmp_850: str = None
        self.filename_dew_850: str = None
        self.prediction_timestamp: datetime = None
        self.model_run: CHainesModelRun = None


class CHainesSeverityGenerator():
    """ Class responsible for orchestrating the generation of Continous Haines severity
    index polygons.

    Steps for generation of severity level as follows:
    1) Download grib files.
    2) Iterate through raster rows, generating an in memory raster containing c-haines severity indices.
    3) Turn raster data into polygons, storing in intermediary GeoJSON file.
    4) Write polygons to database.
    """

    def __init__(self, model: ModelEnum, projection: ProjectionEnum):
        self.model = model
        self.projection = projection
        self.c_haines_generator = CHainesGenerator()
        self.session = app.db.database.get_write_session()

    def _yield_payload(self):
        """ Iterator that yields the next to process. """
        prediction_model = get_prediction_model(self.session, self.model, self.projection)
        utc_now = get_utc_now()
        for model_hour in get_model_run_hours(self.model):
            model_run = None
            for prediction_hour in model_prediction_hour_iterator(self.model):
                urls, model_run_timestamp, prediction_timestamp = make_model_run_download_urls(
                    self.model, utc_now, model_hour, prediction_hour)
                if not model_run:
                    model_run = get_or_create_c_haines_model_run(
                        self.session, model_run_timestamp, prediction_model)
                if record_exists(self.session, model_run, prediction_timestamp):
                    logger.info('%s: already processed %s-%s',
                                self.model,
                                model_run_timestamp, prediction_timestamp)
                    continue

                with tempfile.TemporaryDirectory() as tmp_path:
                    if self.model == ModelEnum.HRDPS:
                        filename_tmp_700 = download(urls['TMP_ISBL_0700'], tmp_path)
                        filename_tmp_850 = download(urls['TMP_ISBL_0850'], tmp_path)
                        filename_dew_850 = download(urls['DEPR_ISBL_0850'], tmp_path)
                    else:
                        filename_tmp_700 = download(urls['TMP_ISBL_700'], tmp_path)
                        filename_tmp_850 = download(urls['TMP_ISBL_850'], tmp_path)
                        filename_dew_850 = download(urls['DEPR_ISBL_850'], tmp_path)

                    if filename_tmp_700 and filename_tmp_850 and filename_dew_850:
                        payload = EnvCanadaPayload()
                        payload.filename_tmp_700 = filename_tmp_700
                        payload.filename_tmp_850 = filename_tmp_850
                        payload.filename_dew_850 = filename_dew_850
                        payload.prediction_timestamp = prediction_timestamp
                        payload.model_run = model_run
                        yield payload
                    else:
                        logger.warning('failed to download all files')

    def _generate_c_haines_data(
            self,
            payload: EnvCanadaPayload):

        # Open the grib files.
        with open_gdal(payload.filename_tmp_700,
                       payload.filename_tmp_850,
                       payload.filename_dew_850) as source_data:
            # Generate c_haines data
            c_haines_data = self.c_haines_generator.generate_c_haines(source_data)
            # Store the projection and geotransform for later.
            projection = source_data.grib_tmp_700.GetProjection()
            geotransform = source_data.grib_tmp_700.GetGeoTransform()
            # Store the dimensions for later.
            band = source_data.grib_tmp_700.GetRasterBand(1)
            rows = band.YSize
            cols = band.XSize
            # Package source info nicely.
            source_info = SourceInfo(projection=projection,
                                     geotransform=geotransform, rows=rows, cols=cols)

        return c_haines_data, source_info

    def _save_severity_data_to_database(self,
                                        payload,
                                        c_haines_severity_data,
                                        c_haines_mask_data,
                                        source_info: SourceInfo):
        with tempfile.TemporaryDirectory() as tmp_path:
            json_filename = os.path.join(os.getcwd(), tmp_path, 'c-haines.geojson')
            save_data_as_geojson(
                c_haines_severity_data,
                c_haines_mask_data,
                source_info,
                json_filename)

            save_geojson_to_database(self.session,
                                     source_info.projection,
                                     json_filename,
                                     payload.prediction_timestamp,
                                     payload.model_run)

    def generate(self):
        """ Entry point for generating and storing c-haines severity index. """
        # Iterate through payloads that need processing.
        for payload in self._yield_payload():
            # Generate the c_haines data.
            c_haines_data, source_info = self._generate_c_haines_data(payload)
            # Generate the severity index and mask data.
            c_haines_severity_data, c_haines_mask_data = generate_severity_data(c_haines_data)
            # We're done with the c_haines data, so we can clean up some memory.
            del c_haines_data
            # Save to database.
            self._save_severity_data_to_database(payload,
                                                 c_haines_severity_data,
                                                 c_haines_mask_data,
                                                 source_info)
