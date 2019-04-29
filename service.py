# Tiles (25x10): https://geo0.ggpht.com/cbk?cb_client=maps_sv.tactile&authuser=0&hl=ru&gl=ru&panoid=bZlPaVbI3qakBT2aBKmWFw&output=tile&x=25&y=12&zoom=5&nbt&fover=2

import requests
import urllib.request as req
import json
import numpy
import gpx_parser as parser
import multiprocessing as mp
import time
import pickle
import os.path

from PIL import Image
from io import BytesIO

from lxml import etree

prev = ''

class ImagePoint:
    def __init__(self, point_id, file_name, pano_id):
        self.point_id = point_id
        self.file_name = file_name
        self.pano_id = pano_id

def getPanoId(lat, lon):
    response = req.urlopen('https://cbk0.google.com/cbk?output=json&ll=' + str(lat) + ',' + str(lon))
    html = response.read()

    data = json.loads(html)
    if 'Location' in data:
        return data['Location']['panoId']
    else:
        return False


def getImage(pano_id, file_name):
    tile_size = 512

    width = tile_size * 13
    height = tile_size * 7
    result_image = Image.new('RGB', (width, height))

    for y in range(7):
        for x in range(13):
            while 1:
                try:
                    response = requests.get('https://geo0.ggpht.com/cbk?cb_client=maps_sv.tactile&authuser=0&hl=ru&gl=ru&panoid=' + pano_id + '&output=tile&x='\
                    + str(x) + '&y=' + str(y) + '&zoom=4&nbt&fover=2')
                    img = Image.open(BytesIO(response.content))
                    result_image.paste(im=img, box=(x * tile_size, y * tile_size))
                    print('Downloaded: x = {}, y = {}'.format(x, y))
                    break
                except requests.exceptions.ConnectionError:
                    #r.status_code = "Connection refused"
                    print('Sleeping...')
                    time.sleep(10)
    
            
    return result_image, file_name

def getCoords(gpx_filename):
    coord_list = []

    with open(gpx_filename, 'r') as gpx_file:
        gpx = parser.parse(gpx_file)
        print("{} tracks loaded".format(len(gpx)))

        for track in gpx:
            print('Track with {} segments and {} points'.format(len(track), track.get_points_no()))
            for segment in track:
                print('Segment with %s points % len(segment)')
                for point in segment:
                    coord_list.append(point)

    return coord_list

def extendCoords(coords, distanseBetweenPoints):
    print(len(coords))
    
    newCoords = []

    for i in range(len(coords) - 1):
        dst = coords[i].distance_2d(coords[i + 1])
        new_cnt = int(dst // distanseBetweenPoints)

        lat = coords[i].latitude 
        lon = coords[i].longitude

        if new_cnt > 0:
            for j in range(new_cnt):
                lat += (coords[i + 1].latitude - coords[i].latitude) / new_cnt
                lon += (coords[i + 1].longitude - coords[i].longitude) / new_cnt
                newCoords.append((lat, lon))    
        else:
            newCoords.append((lat, lon))
    
    return newCoords

if __name__ == '__main__':
    coords = extendCoords(getCoords('route.gpx'), 100)
    imagePoints = []
    
    
    pointsDataFileName = 'points.dat'

    if not os.path.isfile(pointsDataFileName):
        print('File will be created')
        imagesCounter = 0

        
        threads = 16
        pool = mp.Pool(threads)

        for i in range(0, len(coords), threads):
            panoIdMap = pool.starmap(getPanoId, [(coords[j][0], coords[j][1]) for j in range(i, min(i + threads, len(coords)))])
            
            for j in range(len(panoIdMap)):
                if panoIdMap[j] != False:
                    if not imagesCounter or imagePoints[len(imagePoints)-1].pano_id != panoIdMap[j]:
                        img = ImagePoint(i + j, str(imagesCounter) + '.jpg', panoIdMap[j])
                        imagePoints.append(img)
                        print(img.point_id, img.file_name, img.pano_id)
                        imagesCounter += 1

        with open(pointsDataFileName, 'wb') as f:
            pickle.dump(imagePoints, f)
    else:
        print('File openned')
        with open(pointsDataFileName, 'rb') as f:
            imagePoints = pickle.load(f)

    count = 0

    threads = 7
    pool = mp.Pool(threads)

    print(imagePoints[0])

    for i in range(0, len(imagePoints), threads):
        results = pool.starmap(getImage, [(imagePoints[j].pano_id, imagePoints[j].file_name) for j in range(i, min(i + threads, len(imagePoints)))])
        print(results)

        for j in results:
            j[0].save(j[1])
            print('Saved:', j[1])
    pool.close()