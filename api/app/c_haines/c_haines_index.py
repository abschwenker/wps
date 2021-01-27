""" Logic pertaining to the generation of c_haines index from GDAL datasets.
"""
import logging
import struct
from typing import List, Final
from pyproj import CRS
import gdal
from app.weather_models.process_grib import (
    calculate_geographic_coordinate, get_dataset_geometry, get_transformer, GEO_CRS)
from app.c_haines import GDALData


logger = logging.getLogger(__name__)


def calculate_c_haines_index(t700: float, t850: float, td850: float):
    """ Given temperature and dew points values, calculate c-haines.  """
    # pylint: disable=invalid-name

    # Temperature depression term (this indicates atmospheric instability).
    # Temperature at 850mb - Temperature at 700mb.
    ca = (t850-t700)/2-2
    # Dew point depression term (this indicates how dry the air is).
    cb = td850/3-1

    # This part limits the extent to which dry air is able to affect the overall index.
    # If there is very dry air (big difference between dew point temperature and temperature),
    # we want to limit to overall effect on the index, since if there's no atmospheric
    # instability, that dry air isn't going anywhere.
    if cb > 9:
        cb = 9
    elif cb > 5:
        cb = 5 + (cb-5)/2
    ch = ca + cb

    return ch


def read_scanline(band, yoff):
    """ Read a band scanline, returning an array of values. """
    scanline = band.ReadRaster(xoff=0, yoff=yoff,
                               xsize=band.XSize, ysize=1,
                               buf_xsize=band.XSize, buf_ysize=1,
                               buf_type=gdal.GDT_Float32)
    return struct.unpack('f' * band.XSize, scanline)


def get_geographic_bounding_box() -> List:
    """ Get the geographical area (the bounding box) that we want to generate data for.
    Currently hard coded to be an area around B.C. """
    # S->N 46->70
    # E->W -110->-140
    top_left_geo = (-140, 70)
    bottom_right_geo = (-110, 46)
    return (top_left_geo, bottom_right_geo)


class BoundingBoxChecker():
    """ Class used to check if a given raster coordinate lies within a specified
    geographic bounding box. """

    def __init__(self, padf_transform, raster_to_geo_transformer):
        self.geo_bounding_box = get_geographic_bounding_box()
        self.padf_transform = padf_transform
        self.raster_to_geo_transformer = raster_to_geo_transformer
        self.good_x = dict()
        self.check_cache = False

    def _is_inside_using_cache(self, raster_x, raster_y):
        good_y = self.good_x.get(raster_x)
        return good_y and raster_y in good_y

    def is_inside(self, raster_x, raster_y):
        """ Check if raster coordinate is inside the geographic bounding box """
        # Try to use the cached results. Transforming the raster coordinates is very slow. We can save
        # a considerable amount of time, by caching this response - and then using the cache for the
        # entire model run.
        # NOTE: This assumes that all the grib files in the model run will be using the same projection.
        if self.check_cache:
            return self._is_inside_using_cache(raster_x, raster_y)
        # Calculate lat/long and check bounds.
        lon, lat = calculate_geographic_coordinate(
            (raster_x, raster_y),
            self.padf_transform,
            self.raster_to_geo_transformer)
        lon0 = self.geo_bounding_box[0][0]
        lat0 = self.geo_bounding_box[0][1]
        lon1 = self.geo_bounding_box[1][0]
        lat1 = self.geo_bounding_box[1][1]
        if lon > lon0:
            if lon < lon1:
                if lat < lat0:
                    if lat > lat1:
                        good_y = self.good_x.get(raster_x)
                        if not good_y:
                            good_y = set()
                            self.good_x[raster_x] = good_y
                        good_y.add(raster_y)
                        return True
        return False


class CHainesGenerator():
    """ Class for generating c_haines data """

    def __init__(self):
        self.bound_checker: BoundingBoxChecker = None

    def _prepare_bound_checker(self, grib_tmp_700: gdal.Dataset):
        """ Prepare the boundary checker. """
        if not self.bound_checker:
            logger.info('Creating bound checker.')
            padf_transform = get_dataset_geometry(grib_tmp_700)
            crs = CRS.from_string(grib_tmp_700.GetProjection())
            # Create a transformer to go from whatever the raster is, to geographic coordinates.
            raster_to_geo_transformer = get_transformer(crs, GEO_CRS)
            self.bound_checker = BoundingBoxChecker(padf_transform, raster_to_geo_transformer)
        else:
            logger.info('Re-using bound checker.')
            self.bound_checker.check_cache = True

    def calculate_row_data(self,
                           tmp_700_raster_band: gdal.Band,
                           tmp_850_raster_band: gdal.Band,
                           dew_850_raster_band: gdal.Band,
                           y_row_index: int):
        """ Calculate a row of c-haines raster data """
        c_haines_row: Final = []
        # Read the scanlines.
        row_tmp_700: Final = read_scanline(tmp_700_raster_band, y_row_index)
        row_tmp_850: Final = read_scanline(tmp_850_raster_band, y_row_index)
        row_dew_850: Final = read_scanline(dew_850_raster_band, y_row_index)

        # Iterate through values in row.
        for x_column_index, (t700, t850, td850) in enumerate(zip(row_tmp_700, row_tmp_850, row_dew_850)):

            if self.bound_checker.is_inside(x_column_index, y_row_index):
                c_haines_row.append(calculate_c_haines_index(t700, t850, td850))
            else:
                c_haines_row.append(0)
        return c_haines_row

    def generate_c_haines(self, source_data: GDALData):
        """ Given grib data sources, generate c_haines data. """

        # Prepare the boundary checker.
        # Boundary checking is very slow. We have to repeatedly convert a raster coordinate to a geographic
        # coordinate, so we can save a lot of time by creating a boundary checker that caches results.
        self._prepare_bound_checker(source_data.grib_tmp_700)

        # Load the raster data.
        tmp_850_raster_band = source_data.grib_tmp_850.GetRasterBand(1)
        tmp_700_raster_band = source_data.grib_tmp_700.GetRasterBand(1)
        dew_850_raster_band = source_data.grib_dew_850.GetRasterBand(1)

        # Prepare the resultant data arrays.
        c_haines_data: Final = []

        # Iterate through rows (assuming all the raster bands have the same amount of rows)
        logger.info('Generating c-haines index data.')
        for y_row_index in range(tmp_850_raster_band.YSize):

            c_haines_row = self.calculate_row_data(
                tmp_700_raster_band, tmp_850_raster_band, dew_850_raster_band, y_row_index)

            c_haines_data.append(c_haines_row)

        return c_haines_data