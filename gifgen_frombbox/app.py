# python
import os
from flask import Flask, render_template, request, send_from_directory
import json
import random
from gifgenerate_fromstac import LoadUtil
from stac_getchip_gdal import QrySTAC

# pip install Flask Flask-SocketIO eventlet
app = Flask(__name__)

# Directory where files are stored
LOCAL_DIRECTORY = "./temp"
FILENAME = "example_file.gif"  # Replace with your file name

""" Flask web interface tool to orchestrate generate a GIF from user defined bounding box including an image at time 
of event and a time afterward. """


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
    if not os.path.isfile('./temp'):
        os.makedirs('./temp')
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


if __name__ == '__main__':
    app.run(debug=True, port=80)
