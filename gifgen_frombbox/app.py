# python
import os
from flask import Flask, render_template, request, json as jsn, redirect, url_for, jsonify, send_file, send_from_directory
# from flask_socketio import SocketIO, emit
import json
import numpy as np
import io
import tempfile
from io import BytesIO, StringIO
import time
from osgeo import gdal
from osgeo import osr
import rasterio
from skimage.util.shape import view_as_blocks
import shapely
from shapely import Point, Polygon, LineString
from shapely.geometry import shape
from geojson import Feature, FeatureCollection
from PIL import Image
import rasterio
import rasterio.mask
from rasterio.windows import transform
from rasterio.features import geometry_window, geometry_mask
from shapely.geometry import box, mapping
# import geopandas as gpd
from fiona.crs import from_epsg
import matplotlib.pyplot as plt
import random
from gifgenerate_fromstac import LoadUtil
from stac_getchip_gdal import QrySTAC

# pip install Flask Flask-SocketIO eventlet
app = Flask(__name__)
# socketio = SocketIO(app)

# Directory where files are stored
LOCAL_DIRECTORY = "./temp"
FILENAME = "example_file.gif"  # Replace with your file name


def gen_randobbox_inbbox(inbox, width, height):
    # inbox is tuple bbox, width in degrees; ex= 0.5
    # us_bbox = (-125, 24.396308, -66.93457, 49.384358)

    min_lon, min_lat, max_lon, max_lat = inbox

    # Generate random coordinates within the continental U.S.
    random_min_lon = random.uniform(min_lon, max_lon - width)
    random_min_lat = random.uniform(min_lat, max_lat - height)

    # Create a bounding box using Shapely; first will return Polygon, second list of coords
    bbox = box(random_min_lon, random_min_lat, random_min_lon + width, random_min_lat + height)
    print(mapping(bbox))
    return mapping(bbox)  #['coordinates']


# def subsect_img():
#     # Define your bounding box coordinates
#     minx, miny = -90, 40
#     maxx, maxy = -80, 50
#     bbox = box(minx, miny, maxx, maxy)
#     # Create a GeoDataFrame from the bounding box
#     geo = gpd.GeoDataFrame({'geometry': bbox}, index=[0], crs="EPSG:4326")
#
#     # Define path to your large image
#     path_to_raster = "17030.tif"
#     # Open the large image file
#     with rasterio.open(path_to_raster) as src:  # open with rasterio w/Window method open segment, not ent img
#         # Convert the bounding box to the coordinate system of the image
#         img_bounds = tuple(src.bounds)
#         coords = gen_randobbox_inbbox(img_bounds, 0.0015, 0.0015)
#         # geo = geo.to_crs(crs=src.crs.data)
#         # # Get the geometry of the bounding box in the image's coordinate system
#         # coords = [json.loads(geo.to_json())['features'][0]['geometry']]
#         # Mask the image with the bounding box and get the transform
#         out_img, out_transform = rasterio.mask.mask(src, [coords], crop=True)
#     # Visualize the output image
#     plt.imshow(out_img[0], cmap='gray')
#     plt.show()


def GetExtent(ds):
    """ Return list of corner coordinates from a gdal Dataset """
    xmin, xpixel, _, ymax, _, ypixel = ds.GetGeoTransform()
    width, height = ds.RasterXSize, ds.RasterYSize
    xmax = xmin + width * xpixel
    ymin = ymax + height * ypixel

    return (xmin, ymax), (xmax, ymax), (xmax, ymin), (xmin, ymin)


@app.route('/')
def index():
    # Get the list of files in the directory
    files = os.listdir(LOCAL_DIRECTORY)
    return render_template("index.html", files=files)


@app.route('/get_bbox', methods=['GET', 'POST'])
def get_bbox():
    if request.method == 'POST':
        # Route will get bbox crds from user defined selection from leaflet map
        data = request.json['data']  # data = bbox crds from selection in app
        # print('Bbox returned to Flask: ', [int(d) for d in data[0].split(',')])
        print('bbox: ', data)
        bbox = data  # [int(d) for d in data[0].split(',')]

        # query stac & return list img items, which will be passed to the table constructor and populated
        stacrst = QrySTAC.qry_stac(bbox, collname=None)
        print(list(stacrst[0].keys()))

        # Also call the gen gif from bbox coords and date; Need method to add date as string //
        gengif = LoadUtil.main(bbox, indate=None)
        print('Was the Gif generated: ', gengif)
        # files = [f for f in os.listdir(directory_path) if os.path.isfile(os.path.join(directory_path, f))]

        # returns list of stac items as dicts; return both dicts and dataset of one img chip?
        return stacrst


@app.route("/download", methods=["POST"])
def download_file():
    # Get the selected file name from the form
    selected_file = request.form.get("file")
    if selected_file:
        # Serve the file from the local directory
        return send_from_directory(LOCAL_DIRECTORY, selected_file, as_attachment=True)
    return "No file selected", 400

# Fetch() method from JS app call get vehicles from mongo output to csv, convert bytes.io, pass to js. Prev Use/
# @app.route('/download-file', methods=['POST'])  # veh-tocsv
# def download_file():
#     # Path to your GIF file
#     path_to_gif = 'path/to/your/file.gif'
#     return send_file(path_to_gif, as_attachment=True)

    # old
    # data = request.json['data']  # path to gif in docker or ./temp
    # print('RESULT: ', data)  # type(data))
    # # Can we pass argument from js to python to filter csv?
    # bytecsv = vehicles_tocsv(sec_lvl=data)
    # # send_from_directory(app.config['Upload_Folder'], f'vehicles_{strday}')  # /app, Or send_file app.config['filename'])
    # print("bytes from python: ", bytecsv)
    # return bytecsv

# @app.route('/stac_qry', methods=['GET', 'POST'])  #
# def stac_query():
#     # DEFINE A METHOD TO GET THE STAC RESPONSE JSON AND PASS TO TABLE CONSTRUCTOR
#     if request.method == 'POST':
#         data = request.json['data']  # data = selected name from dd in app.
#         print('Bbox returned to Flask: ', [float(d) for d in data[0].split(',')])
#
#         return data[0].split(',')


if __name__ == '__main__':
    app.run(debug=True, port=80)
    # subsect_img()
