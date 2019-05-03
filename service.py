import requests
import json
import numpy
import gpx_parser as parser
import multiprocessing as mp
import time
import pickle
import os.path
import math

from PIL import Image
from io import BytesIO

from lxml import etree

prev = ''

class ImageData:
    def __init__(self, json_data):
        self.panoId = json_data['Location']['panoId']
        self.pano_yaw_deg = json_data['Projection']['pano_yaw_deg']
        self.lat = float(json_data['Location']['lat'])
        self.lon = float(json_data['Location']['lng'])

    
    def addExtraInfo(self, point_id, file_name):
        self.point_id = point_id
        self.file_name = file_name
    
    def __str__(self):
        res = 'Pano Id:' + self.panoId + '\n'
        
        if self.point_id != None:
            res += 'Id:' + str(self.point_id) + '\n'
        
        if self.file_name != None:
            res += 'File name:' + self.file_name + '\n'
        return res
    
    def getTuple(self):
        return self.panoId, self.pano_yaw_deg, self.lat, self.lon, self.point_id, self.file_name

def get(link):
    html = False
    while 1:
        try:
            html = requests.get(link)
            break
        except requests.exceptions.ConnectionError:
            print('Sleeping...')
            time.sleep(5)
    return html

def getPanoId(lat, lon):
    html = get('https://cbk0.google.com/cbk?output=json&ll=' + str(lat) + ',' + str(lon)).json()

    if 'Location' in html:
        return ImageData(html)
    else:
        return False


def getImage(panoId, pano_yaw_deg, point_id, lat, lon, file_name, direction):
    tile_size = 512

    width = tile_size * 13
    height = tile_size * 7
    result_image = Image.new('RGB', (width, height))

    for y in range(7):
        for x in range(13):
            response = get('https://geo0.ggpht.com/cbk?cb_client=maps_sv.tactile&authuser=0&hl=ru&gl=ru&panoid=' + panoId + '&output=tile&x='\
                    + str(x) + '&y=' + str(y) + '&zoom=4&nbt&fover=2')
            img = Image.open(BytesIO(response.content))
            result_image.paste(im=img, box=(x * tile_size, y * tile_size))
            print('Downloaded: x = {}, y = {}'.format(x, y))

    
    shiftImage(result_image, direction - float(pano_yaw_deg))
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

def shiftImage(image, angle):
    if angle < 0:
        angle = 360 - abs(angle)

    separator = round(image.size[0] * angle / 360)

    firstImage = image.crop((0, 0, separator, image.size[1]))
    secondImage = image.crop((separator, 0, image.size[0], image.size[1]))

    image.paste(secondImage, box=(0, 0))
    image.paste(firstImage, box=(secondImage.size[0], 0))

def calculate_initial_compass_bearing(pointA, pointB):
    """
    Calculates the bearing between two points.
    The formulae used is the following:
        θ = atan2(sin(Δlong).cos(lat2),
                  cos(lat1).sin(lat2) − sin(lat1).cos(lat2).cos(Δlong))
    :Parameters:
      - `pointA: The tuple representing the latitude/longitude for the
        first point. Latitude and longitude must be in decimal degrees
      - `pointB: The tuple representing the latitude/longitude for the
        second point. Latitude and longitude must be in decimal degrees
    :Returns:
      The bearing in degrees
    :Returns Type:
      float
    """
    if (type(pointA) != tuple) or (type(pointB) != tuple):
        raise TypeError("Only tuples are supported as arguments")

    lat1 = math.radians(pointA[0])
    lat2 = math.radians(pointB[0])

    diffLong = math.radians(pointB[1] - pointA[1])

    x = math.sin(diffLong) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - (math.sin(lat1)
            * math.cos(lat2) * math.cos(diffLong))

    initial_bearing = math.atan2(x, y)

    # Now we have the initial bearing but math.atan2 return values
    # from -180° to + 180° which is not what we want for a compass bearing
    # The solution is to normalize the initial bearing as shown below
    initial_bearing = math.degrees(initial_bearing)
    compass_bearing = (initial_bearing + 360) % 360

    return compass_bearing


if __name__ == '__main__':
    coords = extendCoords(getCoords('150Km.gpx'), 5)
    imageData = []
    
    
    pointsDataFileName = 'points.dat'
    directions = []
    
    if not os.path.isfile(pointsDataFileName):
        print('File will be created')
        imagesCounter = 0

        threads = 7
        pool = mp.Pool(threads)

        prevPanoId = ''

        for i in range(0, 400, threads):
            panoDataMap = pool.starmap(getPanoId, [(coords[j][0], coords[j][1]) for j in range(i, min(i + threads, len(coords)))])
            
            for j in range(len(panoDataMap)):
                if panoDataMap[j] != False:
                    if not imagesCounter or prevPanoId != panoDataMap[j].panoId:
                        prevPanoId = panoDataMap[j].panoId
                        img = panoDataMap[j]
                        img.addExtraInfo(i + j, str(imagesCounter) + '.jpg')
                        imageData.append(img.getTuple())

                        print(imageData[-1])
                        imagesCounter += 1

        with open(pointsDataFileName, 'wb') as f:
            pickle.dump(imageData, f)
    else:
        print('File openned')
        with open(pointsDataFileName, 'rb') as f:
            imageData = pickle.load(f)
    
    for i in range(len(imageData)-1):
        panoId1, pano_yaw_deg1, lat1, lon1, point_id1, file_name1 = imageData[i]
        panoId2, pano_yaw_deg2, lat2, lon2, point_id2, file_name2 = imageData[i + 1]

        directions.append(calculate_initial_compass_bearing((lat1, lon1), (lat2, lon2)))
    directions.append(directions[-1])


    count = 0

    pool = mp.Pool(threads)

    for i in range(0, len(imageData), threads):
        results = pool.starmap(getImage, [(imageData[j] + (directions[j],)) for j in range(i, min(i + threads, len(imageData)))])
        print(results)

        for j in results:
            j[0].save(j[1])
            print('Saved:', j[1])
    pool.close()