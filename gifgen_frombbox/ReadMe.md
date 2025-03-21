
# GIF Generator from Bounding Box Application

## Purpose

The GIF generator application uses Flask and Leaflet to query STAC imagery servers with the user defined bounding box from the interface.  Imagery returned from STAC is cropped by the bounding box; the GIF is composed of imagery from the date of the query and two years before the query.  The user has the option to download both the images and GIF.  

![image](https://github.com/user-attachments/assets/059710ee-a04e-42ac-854c-6cee6b791fcb)
