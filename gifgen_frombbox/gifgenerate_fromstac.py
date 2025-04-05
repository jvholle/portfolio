import io
import os
import sys
import json
import csv
import time
import cv2
from dateutil.relativedelta import relativedelta
from datetime import datetime, timezone, timedelta
import requests
from datetime import datetime
from shapely import box
from shapely.geometry import mapping, shape
from pystac_client import Client
import rasterio
import rasterio.mask
from rasterio.io import MemoryFile
from io import BytesIO
import random
from urllib.parse import parse_qs, urlparse
import urllib.parse
import imageio
from stac_getchip_gdal import QrySTAC

tdate = datetime.now()
strday = tdate.strftime("%Y-%m-%d")


class LoadUtil:
    def __init__(self, bbox, indate):
        self.bbox = bbox
        self.indate = indate

    @staticmethod
    def create_imggif2(region_id, img_list):
        print('Check regionid val: ', region_id)
        # Read the images into a list, img_list is list itself with local image dir, constr. phase, and obs. date
        images = [imageio.v3.imread(path[0]) for path in img_list]  # Not work w/large images, could be 1gb gif file
        
        # Save the images as a GIF
        imageio.mimsave(f"./temp/{region_id}.gif", images, duration=2)  # This fails with full sized images*
        time.sleep(1)

        # Open the gif and modify each frame with text # Read the GIF
        gif = imageio.mimread(f"./temp/{region_id}.gif")

        # Create a list to store the modified frames
        modified_frames = []

        # Add text to each frame // try work later in frame mod with the main gif gen. loop
        for i, frame in enumerate(gif):
            # img metadata
            img = img_list[i]
            imgpath, cons_phs, obsdate = img
            text = f"{obsdate} {cons_phs}"  # >> Obs. Date - Const. Phase
            # Convert the frame to BGR (OpenCV format)  # wh:(255, 255, 255)
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

            # Add text to the frame; putText key: cv2.putText(image, text, (10, 50), font, font_scale, color, thickness)
            phs_color = {"Site Preparation": (247, 218, 132), "Active Construction": (255, 0, 0),
                         "Post Construction": (123, 171, 215), "Unknown": (138, 93, 172), "No Activity": (178, 178, 178)}
            cv2.putText(frame, text, (5, 10), cv2.FONT_HERSHEY_SIMPLEX, 0.30, random.choice(list(phs_color.values())), 1)

            # Convert the frame back to RGB
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Append the modified frame to the list
            modified_frames.append(frame)

        # Save the modified frames as a new GIF
        imageio.mimsave(f"./temp/{region_id}_meta.gif", modified_frames, duration=2.5)  # / drop _meta /

        # cleanup first gif
        if os.path.exists(f"./temp/{region_id}.gif"):
            os.remove(f"./temp/{region_id}.gif")
            print(f'file removed: {f"./temp/{region_id}.gif"}')

    @classmethod
    def main(cls, bbox, indate=None):  # // Work in the Get date from user method
        """ From user bbox input, generate a GIF of images for a recent and past date to compair imagery from STAC
        1. User select bbox and return it to flask w/leaflet app
        2. query STAC for specified date and a date n years preceeding
        3. generate the gif from the return STAC images, display, save to disk or option to download """

        # Handle date object, get date utc n years preceeding indate.
        def get_predate(idate):
            ind_obj = datetime.strptime(idate, "%Y-%m-%d")
            date_minus4yrs = ind_obj - relativedelta(years=4)
            return date_minus4yrs

        # ind_obj = datetime.strptime(indate, "%Y-%m-%d")  # indata['qry_date']
        gif_imgs, defdate = [], '2023-02-12'  # , date_minus4yrs = [], ind_obj - relativedelta(years=4)

        # 1. Get the bbox and date from gui; testdic; / Add Flask GUI app here /
        if indate is None:
            prevdate = datetime.strftime(get_predate(defdate), '%Y-%m-%d')
            indate = defdate
        else:
            prevdate = datetime.strftime(get_predate(indate), '%Y-%m-%d')  # {'bbox': [], 'qry_date': '2023-02-12', 'prev_date': '2019-02-12'}  # date min4  prevdate

        data = {'bbox': bbox, 'qry_date': indate, 'prev_date': prevdate}
        print(data)

        # 2. Spatial Temporal Query STAC for images; add buffer around bbox for large img viewing area
        bufbbox = box(*bbox).buffer(0.008)  # conv. bbox to Shape, Poly, buffer and conv. back to bbox
        bbox = bufbbox.bounds  # dec degr. 500 M = 0.045
        print('buffered box: ', bbox)

        # Get imgs for varying dates for gif
        datekeys = [k for k in list(data.keys()) if 'date' in k]
        print('what are the date keys: ', datekeys)

        # 2. Get the images from AWS STAC
        for k in datekeys:
            init_img = QrySTAC.crop_cog_with_bbox2(bbox, indate=data.get(k))  # for test add one img or sec. blank img

            if init_img:  # os.getcwd()
                print('Did it return bbox? ', bbox, os.path.isfile(init_img))  # Add path
                # for gif generation, add tuple of img info: (imgpath, label, imgdate)
                imgdata = (init_img, k, data.get(k))
                gif_imgs.append(imgdata)

            elif init_img is None:
                continue

        print('gif imgs:::', gif_imgs)  # Display temp image, if any, phase of construction.
        if not gif_imgs:  # continue, if no images collected.
            print('No anno to image matches found!')
            pass

        # Coll what was not collected Observ. Anno and Large image where no match image by date //
        with open(f'gif_imgs_{strday}.json', 'w+') as m:
            # mjson = dict(dict(obs_date=f['properties']['observation_date'], mch_img=None, phase=None))
            json.dump(gif_imgs, m)

        # 3. generate GIF from the clipped images.  // Dev method to download the gif upon request //
        init_date = data['qry_date']
        LoadUtil.create_imggif2(f'test_{init_date}', gif_imgs)

        # Cleanup all clipped tifs
        del_files = [f for f in os.listdir('./temp') if f.endswith(('.tif', '.tiff'))]
        print('List files Delete: ', del_files)
        for fi in del_files:
            if os.path.exists(fi):
                os.remove('./temp/' + fi)


if __name__ == '__main__':
    # Create an ArgumentParser object
    parser = argparse.ArgumentParser(
        description='Script will provide a GIF of images from a STAC server and user input for the bounding box and '
                    'initial search date. The second image in the GIF will be 5 years proceeding the initial date.')

    # Add arguments; Ex. use: python script_name.py -i ... -a s3://bucketname/annos/site_models/
    parser.add_argument('-b', '--bbox', type=list, required=True, help='bounding box',
                        default=[-80.72100081394343, 32.20221586362286, -80.66272562117198, 32.23967859759147])
    parser.add_argument('-d', '--indate', type=str, required=True, help='initial date for STAC query',
                        default='2023-08-12')

    # Parse the arguments; access args with args.image_uri
    args = parser.parse_args()
    # img_uri = parse_s3_uri(args.image_uri)[1]
    bbox, indate, bucketType = args.bbox, args.indate, 'general'

    if not bbox or indate:  # default values for testing
        data = {'bbox': [-80.72100081394343, 32.20221586362286, -80.66272562117198, 32.23967859759147],
                'qry_date': '2023-08-12', 'prev_date': '2019-08-12'}  # Add output dir? current hardcoded
        bbox, indate = data['bbox'], data['qry_date']

    LoadUtil.main(bbox, indate)
