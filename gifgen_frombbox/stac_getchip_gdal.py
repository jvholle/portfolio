import os
import sys
import json
from datetime import datetime, timezone, timedelta
from osgeo import gdal, ogr, osr
import numpy as np
from pystac.extensions.eo import Band, EOExtension
from pystac_client import Client, conformance
import rasterio
from rasterio.io import MemoryFile
from rasterio.transform import from_bounds
# from rasterio.windows import window
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.enums import Resampling
from rasterio.shutil import copy
from pystac_client import Client
from shapely.geometry import box, mapping, shape, Polygon, Point
import requests
# import plot_geojimgs as plotgeo
# sys.path.append("C:/tmp")
# from utilities import UtilInit

# Get the current date and time in UTC
now_utc = datetime.now(timezone.utc)
# Format the date and time as a string
form_date = now_utc.strftime("%Y%m%d")


class QrySTAC:
    def __init__(self, injson, bbox, n_pnts):
        self.injson = injson
        self.bbox = bbox
        self.n_pnts = n_pnts

    @classmethod
    def qry_stac(cls, bbox, daterange=None, collname=None):
        try:
            if not daterange:
                daterange = ['2022-09-15T00:00:00Z', '2023-07-10T00:00:00Z']
            # Remote API call catalog = Client.open("https://earth-search.aws.element84.com/v1")
            api = Client.open('https://earth-search.aws.element84.com/v1')
            # api.add_conforms_to("ITEM_SEARCH")  # ['2017-01-01T00:00:00Z', '2020-01-02T00:00:00Z'],
            # col = [c.id for c in api.get_collections()] # print(col)
            results = api.search(
                max_items=5,
                # intersects=geom,  # provide just the 'geometry' from geojson
                bbox=bbox,
                datetime=daterange,
                collections=['sentinel-2-l2a', 'modis-16A3GF-061']  # , 'goes-glm']  #col  'sentinel-1-rtc'
            )
            print('How many items returned: ', len(results.item_collection()))
            item_dicts = [d for d in results.items_as_dicts()]  # items()
            # make into list of geojson features to plot...
            lst_objs = [{'id': d['id'], 'href': d['links'][0]['href'],  # [str(li['href']) for li in d['links']],
                         'geometry': d['geometry']} for d in item_dicts]
            # print(item_dicts[0])

            return item_dicts

        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            print(e, exc_type, exc_tb.tb_lineno)

    @staticmethod
    def get_imgbytes_stac(bbox, indate=None, use_daterge=True):  # Some application want get date range, other not.
        # Remote API call catalog = Client.open("https://earth-search.aws.element84.com/v1")
        client = Client.open('https://earth-search.aws.element84.com/v1')

        def generate_date_range(input_date_str, days=60):
            # Parse the input date string into a datetime object
            input_date = datetime.strptime(input_date_str, "%Y-%m-%d")

            # Calculate the date 60 days before and after the input date
            start_date = input_date - timedelta(days=days)
            end_date = input_date + timedelta(days=days)

            # Format the dates in UTC with 'T' and 'Z'
            start_date_utc = start_date.strftime("%Y-%m-%dT%H:%M:%SZ")
            end_date_utc = end_date.strftime("%Y-%m-%dT%H:%M:%SZ")

            return start_date_utc, end_date_utc

        # Conditions for date ranges and what to do if qry one date.
        if not indate:
            daterange = ['2024-03-15T00:00:00Z', '2024-04-15T00:00:00Z']
        elif use_daterge is False:
            input_date = datetime.strptime(indate, "%Y-%m-%d")  # gen datetime obj
            indate_utc = input_date.strftime("%Y-%m-%dT%H:%M:%SZ")
            daterange = indate_utc
            print('date range for single:: ', daterange)
        else:
            daterange = generate_date_range(indate, days=1)

        # Define the bounding box (xmin, ymin, xmax, ymax)
        bbox_geom = box(*bbox)
        print('bbox: ', bbox_geom)  # >> generates a polygon geom; May need to convert geom to src img crs!
        # plotgeo.plot_bounding_boxes(mapping(bbox_geom))

        # Search for items that intersect with the bounding box # intersects=bbox_geom,
        search = client.search(bbox=list(bbox),  datetime=daterange, collections=['sentinel-2-l2a'], limit=4)
        # search = client.search(intersects=bbox_geom, datetime=daterange, collections=['sentinel-2-l2a'], limit=4)

        # Get the first item (for simplicity, you might want to handle multiple items)
        items, item = list(search.items_as_dicts()), None  # Or items()
        if not items:
            raise ValueError("No items found for the given bounding box.")

        # Determine if item by index overlaps with the bbox of the geojson bbox trying to extract image.
        def det_polyoverlap(subjpoly: Polygon, imgpoly: Polygon):
            """ Determine if overlap between two polygons for finding a STAC image that overlaps subject polygon """
            # poly2 = Polygon([(bbox2[0], bbox2[1]), (bbox2[2], bbox2[1]), (bbox2[2], bbox2[3]), (bbox2[0], bbox2[3])])
            return subjpoly.intersects(imgpoly)

        for it in items:  # Loop all images returned
            # img_int = False
            # while img_int is False:
            img_poly = box(*it['bbox'])  # img poly is source crs, not 4326...
            if det_polyoverlap(bbox_geom, img_poly):
                item = it
                print('subject bbox intersects image bbox:', item['id'])
                break  # img_int = True  # break  # Get the first intersect img and break

        # item = items[0]  # take the first item return, may want to loop first 5 for best quality image...
        asset = item['assets']['visual']  # Assuming 'visual' is the key for the imagery asset
        print('asset: ', asset['href'], item['bbox'])  # ['crs']  srccrs = item['geometry']

        # read the href from stac with GDAL in mem
        dataset = gdal.Open("/vsicurl/" + asset["href"])
        return dataset

    @staticmethod
    def geo_to_pixel(geotransform, lon, lat):
        # Accessing geotransform elements
        x_origin = geotransform[0]
        y_origin = geotransform[3]
        pixel_width = geotransform[1]
        pixel_height = geotransform[5]

        # Calculate pixel coordinates
        col = (lon - x_origin) / pixel_width
        row = (y_origin - lat) / pixel_height
        return (col, row)

    @classmethod
    def crop_cog_with_bbox2(cls, bbox, indate=None):  # FUNC
        """
        Crop COG image w/bbox & include all bands. Ex input crds: min_lon, min_lat = -80.0, 25.0; max_lon, max_lat = -79.5, 25.5
        :param bbox: Bounding box as (min_lon, min_lat, max_lon, max_lat).
        :param indate: observation date to name image (UTC format).
        :return: Cropped image as a NumPy array with all bands.
        """
        # Open the COG \# dataset = gdal.Open(cog_path) # if not dataset:
        # raise FileNotFoundError(f"Could not open {cog_path}")

        # get dataset from STAC with GDAL vsicurl
        src_ds = QrySTAC.get_imgbytes_stac(bbox, indate, use_daterge=True)
        print('Did we get the dataset: ', type(src_ds))  # gdal.Info(src_ds))

        # get the min/max lat/lon from bbox
        min_lon, min_lat, max_lon, max_lat = bbox  # [-80.7209008, 32.20421586, -80.6647217198, 32.2394785]

        # Get the source projection
        src_proj = osr.SpatialReference(wkt=src_ds.GetProjection())

        # Define the target projection (WGS84)
        tgt_proj = osr.SpatialReference()
        tgt_proj.ImportFromEPSG(4326)  # EPSG:4326 = WGS84; assuming input bbox is 4326

        # Create a coordinate transformation
        transform = osr.CoordinateTransformation(tgt_proj, src_proj)

        # Transform the bounding box coordinates to the source projection // Swap the min/max lat lon for transf pnt.
        # min_x, min_y, _ = transform.TransformPoint(min_lon, min_lat)
        # max_x, max_y, _ = transform.TransformPoint(max_lon, max_lat)
        min_x, min_y, _ = transform.TransformPoint(min_lat, min_lon)
        max_x, max_y, _ = transform.TransformPoint(max_lat, max_lon)

        # Calculate the pixel offsets
        gt = src_ds.GetGeoTransform()
        inv_gt = gdal.InvGeoTransform(gt)

        min_px, min_py = map(int, gdal.ApplyGeoTransform(inv_gt, min_x, min_y))
        max_px, max_py = map(int, gdal.ApplyGeoTransform(inv_gt, max_x, max_y))
        print('pixel vals before bounds conv: ', min_px, min_py, max_px, max_py)

        # Ensure the pixel indices are within the image bounds
        min_px = max(min_px, 0)
        min_py = max(min_py, 0)
        max_px = min(max_px, src_ds.RasterXSize)
        # print('check if Raster size is alway min: ', (max_px, src_ds.RasterXSize))
        max_py = min(max_py, src_ds.RasterYSize)
        print('min_px/min_py: ', min_px, min_py)

        # Calculate the width and height of the crop // ISSUE with pos/neg values for min max pixels values; conv func?
        width = abs(max_px) - min_px  # > abs of max pix due subtracting two negatives returns much larger value
        height = abs(abs(max_py) - min_py)
        print('W and H: ', width, height)

        # test the formula by use of pixel extract from geo crds method for read array below
        # t_px, t_py = QrySTAC.geo_to_pixel(inv_gt, min_px, min_py)
        # print('Return Tester pix from crds: ', t_px, t_py)

        # Read the data from the source dataset
        data = src_ds.ReadAsArray(min_px, min_py, width, height)
        # data = src_ds.ReadAsArray(t_px, t_py, width, height)

        # Create a new dataset for the output
        driver = gdal.GetDriverByName('GTiff')
        # // Needs to be modified for func in docker... // Below add option to download from server.
        out_ds = driver.Create(f'./temp/clip_{indate}_rgb.tif', width, height, src_ds.RasterCount, gdal.GDT_Float32)

        # Set the geotransform and projection on the output dataset
        new_gt = list(gt)
        new_gt[0] = gt[0] + min_px * gt[1] + min_py * gt[2]
        new_gt[3] = gt[3] + min_px * gt[4] + min_py * gt[5]
        out_ds.SetGeoTransform(new_gt)
        out_ds.SetProjection(src_ds.GetProjection())

        # Write the data to the output dataset
        for i in range(1, src_ds.RasterCount + 1):
            out_band = out_ds.GetRasterBand(i)
            out_band.WriteArray(data[i - 1])

        # Flush and close datasets; return the name/outdir of extracted/cropped image
        out_ds.FlushCache()
        out_ds = None
        src_ds = None

        return f'./temp/clip_{indate}_rgb.tif'

    @classmethod
    def extr_geotiff(cls):
        # get dataset from STAC with GDAL vsicurl
        dataset = QrySTAC.get_imgbytes_stac(bbox)
        print('Did we get the dataset: ', type(dataset))

        # Extract the ENTIRE geotiff to disk
        driver = gdal.GetDriverByName('GTiff')  # 'COG' Driver?
        rows, cols = dataset.RasterYSize, dataset.RasterXSize
        print('shape main ds: ', rows, cols)
        dataset = driver.Create(f'mainimg_{form_date}.tif', cols, rows, 3, gdal.GDT_Float32)

        # Get the geotransform and projection
        geotransform = dataset.GetGeoTransform()
        projection = dataset.GetProjection()
        print('projection: ', projection)

        # Set the projection and geotransform
        dataset.SetProjection(projection)
        dataset.SetGeoTransform(geotransform)

        # Write the data to the dataset
        for band_num in range(1, 3 + 1):
            band = dataset.GetRasterBand(band_num)
            barray = band.ReadAsArray()
            band.WriteArray(barray)

        # Close the dataset to write to disk // STILL USING DS FOR CROP //
        dataset = None


if __name__ == '__main__':
    # Run faster with GDAL methods; flask app to get the bbox and get the image back...
    tbox = [-80.72100081394343, 32.20221586362286, -80.66272562117198, 32.23967859759147]
    # tbox = [125.83233619648411, 39.00902819552872, 125.84189082165578, 39.01643482171545]
    # As an option, input a Polygon geometry and convert it to a bbox below.
    poly = {"geometry": {"type": "MultiPolygon", "coordinates": [[[[
        125.83768353829957, 39.01303063087204], [125.83768353829957, 39.013130979338534],
        [125.83768353829957, 39.01333167669178], [125.83778717997768, 39.01333167669178],
        [125.83778717997768, 39.0134320255785], [125.83778717997768, 39.01353237460533],
        [125.83695804655278, 39.014034121840695], [125.83675076319658, 39.014034121840695],
        [125.83664712151844, 39.014034121840695], [125.83664712151844, 39.013933772113454],
        [125.83757989662148, 39.01252889064072], [125.83757989662148, 39.01232819552872],
        [125.83768353829957, 39.01232819552872], [125.83768353829957, 39.01252889064072],
        [125.83768353829957, 39.01262923840684], [125.83768353829957, 39.01272958631303],
        [125.83768353829957, 39.012829934359274], [125.83768353829957, 39.01293028254563],
        [125.83768353829957, 39.01303063087204]]]]}}
    polyshp = shape(poly['geometry'])
    print('IN POLY: ', polyshp.bounds)
    bbox = polyshp.bounds  # dec degr. 500 M = 0.045
    QrySTAC.crop_cog_with_bbox2(tbox, '2022-05-09')
    # QrySTAC.crop_img_bbox(tbox)  # bbox max to mins...
    # QrySTAC.download_and_crop_cog(polyshp.bounds)
    # QrySTAC.extr_geotiff()
