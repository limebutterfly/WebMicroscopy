# Script to read Olympus ETS files for virtual Microscopy
# Copyright (C) 2024, Jeremy Deuel <jeremy.deuel@usz.ch>
#     This program is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.
#
#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.
#
#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <https://www.gnu.org/licenses/>.

from http import server
import re
import os
from datetime import datetime
import json
from mimetypes import MimeTypes
import math
import io
from PIL import Image

# SETTINGS

DEVELOPMENT_MODE = True #change this to fales in production!
PORT = 8080 # PORT TO SERVE ON
FILES_PATH = "/Users/jeremy/Desktop/vsi" # Set Path to Olympus Files
URL_TRAILING = "/microscopy/" # trailing URL, set to "/" to omit.
MAX_OPEN_FILES = 10 #max files that are open simultaneously
MAX_OPEN_TIME = 3600 # one hour

class OlympusETSFile:
    endian = 'little'

    def __init__(self, path: os.path):
        self.fh = open(path, 'rb')
        self.content = {}
        self.type = self.fh.read(3).decode('ascii')
        int.from_bytes(self.fh.read(1), byteorder=self.endian, signed=False) #read stop byte
        assert self.type=="SIS", f"Wrong file format"
        self.extractSISHead()
        self.extractTiles()

    def __del__(self):
        self.fh.close()
    def extractSISHead(self):
        self.content['c_bitsize'] = int.from_bytes(self.fh.read(4), byteorder=self.endian, signed=False)
        assert self.content['c_bitsize']==64, f"Unknown bitsize value: {self.content['c_bitsize']}"
        self.content['c_version'] = int.from_bytes(self.fh.read(4), byteorder=self.endian, signed=False)
        assert self.content['c_version'] == 3, f"Unknown version value: {self.content['c_version']}"
        self.content['c_dimension'] = int.from_bytes(self.fh.read(4), byteorder=self.endian, signed=False)
        assert self.content['c_dimension'] == 4, f"Unknown dimension value: {self.content['c_dimension']}"
        self.content['c_etsoffset'] = int.from_bytes(self.fh.read(8), byteorder=self.endian, signed=False)
        assert self.content['c_etsoffset'] == 64, f"Unknown etsoffset value: {self.content['c_etsoffset']}"
        self.content['c_etsnbytes'] = int.from_bytes(self.fh.read(4), byteorder=self.endian, signed=False)
        assert self.content['c_etsnbytes'] == 228, f"Unknown etsnbytes value: {self.content['c_etsnbytes']}"
        self.content['c_zero0'] = int.from_bytes(self.fh.read(4), byteorder=self.endian, signed=False)
        assert self.content['c_zero0'] == 0, f"Unknown c_zero0 value: {self.content['c_zero0']}"
        self.content['offset'] = int.from_bytes(self.fh.read(8), byteorder=self.endian, signed=False)
        self.content['ntiles'] = int.from_bytes(self.fh.read(4), byteorder=self.endian, signed=False)
        self.content['c_zero1'] = int.from_bytes(self.fh.read(4), byteorder=self.endian, signed=False)
        assert self.content['c_zero1'] == 0, f"Unknown c_zero1 value: {self.content['c_zero1']}"

        self.content['offset2'] = int.from_bytes(self.fh.read(8), byteorder=self.endian, signed=False)
        self.content['c_zero2'] = int.from_bytes(self.fh.read(4), byteorder=self.endian, signed=False)
        assert self.content['c_zero2'] == 0, f"Unknown c_zero2 value: {self.content['c_zero2']}"
        self.content['c_zero3'] = int.from_bytes(self.fh.read(4), byteorder=self.endian, signed=False)

        assert self.content['c_zero3'] == 0, f"Unknown c_zero3 value: {self.content['c_zero3']}"

        self.content['constant0'] = int.from_bytes(self.fh.read(8), byteorder=self.endian, signed=False)
        assert self.content['constant0'] == 844450705396805, f"Unknown constant0 value: {self.content['constant0']}"

        self.content['constant1'] = int.from_bytes(self.fh.read(4), byteorder=self.endian, signed=False)
        assert self.content['constant1'] == 2, f"Unknown constant1 value: {self.content['constant1']}"

        self.content['var1'] = int.from_bytes(self.fh.read(4), byteorder=self.endian, signed=False)
        self.content['var2'] = int.from_bytes(self.fh.read(4), byteorder=self.endian, signed=False)
        self.content['zoomfactor'] = int.from_bytes(self.fh.read(4), byteorder=self.endian, signed=False)
        self.content['var4'] = int.from_bytes(self.fh.read(4), byteorder=self.endian, signed=False)
        self.content['length'] = int.from_bytes(self.fh.read(4), byteorder=self.endian, signed=False)
        self.content['width'] = int.from_bytes(self.fh.read(4), byteorder=self.endian, signed=False)
        self.content['height'] = int.from_bytes(self.fh.read(4), byteorder=self.endian, signed=False)
        self.content['c_zero4'] = int.from_bytes(self.fh.read(4), byteorder=self.endian, signed=False)
        assert self.content['c_zero4'] == 0, f"Unknown c_zero4 value: {self.content['c_zero4']}"
        for k in [k for k in self.content.keys()]:
            if k[0]=="c":
                self.content.pop(k)

    def extractTiles(self):
        offset = self.content['offset']
        self.tiles = {}
        self.dims = {}
        ntiles = 0 # counter
        while offset<self.content['offset2']:
            t = Tile(self.fh, offset)
            assert t.z == 0, f"Can not handle z>0, z is {t.z}"
            if t.level in self.tiles.keys():
                self.tiles[t.level].append(t)
                if t.y == 0:
                    self.dims[t.level][0] = t.x
                elif t.y > 0 and t.x == 0:
                    self.dims[t.level][1] = t.y
            else:
                self.tiles[t.level] = [t]
                self.dims[t.level] = [0,0]
            ntiles += 1
            offset += 36
        assert ntiles==self.content['ntiles'], f"extracted {ntiles} but expected {self.content['ntiles']}."
        for k in self.dims.keys():
            self.dims[k] = (self.dims[k][0]+1,self.dims[k][1]+1)

    def getTile(self, x: int, y:int , z:int, level:int):
        assert z==0, f"Can not extract z-levels different from 0"
        if not level in self.dims.keys(): return None #wrong level
        if y >= self.dims[level][1] or y<0: return None
        if x >= self.dims[level][0] or x<0: return None
        t = self.tiles[level][self.dims[level][0]*y + x]
        assert t.x == x and t.y == y and t.z == z and t.level == level, f"Extracted wrong tile. Expected {x} {y} {z} l{level} but got {t.x} {t.y} {t.z} l{t.level}"
        return t
    def tileSummary(self):
        return self.dims
    def dim(self, level:int = 0) -> (int, int, int):
        """
        returns dimensions of tiles at a specified level
        x, y, z
        """
        if not level in self.dims.keys():
            return 0, 0, 0
        return self.dims[level][0], self.dims[level][1], 0

    def __repr__(self):
        return f"File of type {self.type} with content {repr(self.content)}"

    def getImage(self, coordinates: tuple[int, int, int, int]):
        max_x, max_y, _ = self.dim(0)
        tile_size = self.content['length']
        min_x_tile = math.floor(coordinates[0]/tile_size)
        max_x_tile = math.floor((coordinates[0]+coordinates[2])/tile_size)
        min_y_tile = math.floor(coordinates[1] / tile_size)
        max_y_tile = math.floor((coordinates[1] + coordinates[3]) / tile_size)
        assert min_x_tile >= 0 and min_x_tile < max_x, f"min x coordinate {min_x_tile} out of bounds [0, {max_x}]"
        assert max_x_tile >= 0 and max_x_tile < max_x, f"max x coordinate {max_x_tile} out of bounds [0, {max_x}]"
        assert min_y_tile >= 0 and min_y_tile < max_y, f"min y coordinate {min_y_tile} out of bounds [0, {max_y}]"
        assert max_y_tile >= 0 and max_y_tile < max_y, f"min y coordinate {max_y_tile} out of bounds [0, {max_y}]"
        img = Image.new('RGB',((max_x_tile-min_x_tile+1)*tile_size,(max_y_tile-min_y_tile+1)*tile_size))
        for x in range(min_x_tile, max_x_tile+1):
            for y in range(min_y_tile, max_y_tile+1):
                print(f"tile {x} {y} to box {((x-min_x_tile)*tile_size,(y-min_y_tile)*tile_size)}")
                tile = Image.open(io.BytesIO(self.getTile(x,y,0,0).getBytes()), formats=("JPEG",))
                img.paste(tile, ((x-min_x_tile)*tile_size,(y-min_y_tile)*tile_size))

        img = img.crop((
            coordinates[0] - min_x_tile * tile_size,
            coordinates[1] - min_y_tile * tile_size,
            coordinates[0]+coordinates[2] - min_x_tile * tile_size,
            coordinates[1]+coordinates[3]-min_y_tile * tile_size
        ))

        returnBytes = io.BytesIO()
        img.save(returnBytes, format='PNG')
        return returnBytes.getvalue()

        assert False, "not implemented"
class Tile():
    endian = 'little'
    def __init__(self, fh, offset: int):
        self.content = {}
        self.fh = fh
        self.fh.seek(offset)
        self.extractHead()
    def extractHead(self):
        self.content['c1'] = int.from_bytes(self.fh.read(4), byteorder=self.endian, signed=False)
        assert self.content['c1']==4, f"start byte of tile does not start with 4, is {self.content['c1']}"
        self.content['px'] = int.from_bytes(self.fh.read(4), byteorder=self.endian, signed=False)
        self.content['py'] = int.from_bytes(self.fh.read(4), byteorder=self.endian, signed=False)
        self.content['pz'] = int.from_bytes(self.fh.read(4), byteorder=self.endian, signed=False)
        self.content['level'] = int.from_bytes(self.fh.read(4), byteorder=self.endian, signed=False)
        self.content['offset'] = int.from_bytes(self.fh.read(8), byteorder=self.endian, signed=False)
        self.content['nbytes'] = int.from_bytes(self.fh.read(4), byteorder=self.endian, signed=False)
        self.content['tile_i'] = int.from_bytes(self.fh.read(4), byteorder=self.endian, signed=False)
        for k in [k for k in self.content.keys()]:
            if k[0]=="c":
                self.content.pop(k)
    def __repr__(self):
        return f"Tile at lvl {self.content['level']} pos {self.content['px']} {self.content['py']} {self.content['pz']} size {self.content['nbytes']}"
    @property
    def level(self):
        return self.content['level']

    @property
    def x(self):
        return self.content['px']

    @property
    def y(self):
        return self.content['py']

    @property
    def z(self):
        return self.content['pz']
    def getBytes(self):
        self.fh.seek(self.content['offset'])
        return self.fh.read(self.content['nbytes'])

    def saveToFile(self, path):
        with open(path, 'wb') as f:
            f.write(self.getBytes())
        print(f"Wrote file {path}")


class etsFileHandler:
    """
    Class to manage multiple simultaneously open ETS files.
    """

    def __init__(self, max_files_open=10, max_file_open_time=3600):
        self.handles = {}
        self.lastSeen = {}
        self.max_files_open = max_files_open
        self.max_file_open_time = max_file_open_time

    def __del__(self):
        """
        Close open files
        """
        for ets in [ets for ets in self.handles.keys()]:
            self.closeFile(ets)

    def closeFile(self, ets: os.path):
        self.lastSeen.pop(ets)
        ets = self.handles.pop(ets)
        if DEVELOPMENT_MODE: print(f"Closed file {ets}")
        del ets

    def openFile(self, ets: os.path):
        if DEVELOPMENT_MODE: print(f"Opening file {ets}")
        self.handles[ets] = OlympusETSFile(ets)
        self.lastSeen[ets] = int(datetime.now().timestamp())
        while len(self.handles) > self.max_files_open:
            # close oldest file
            oldest = min(self.lastSeen)
            for k in self.lastSeen[k]:
                if self.lastSeen[k] == oldest:
                    self.closeFile(k)
        return self.handles[ets]

    def manageOpenFileHandles(self):
        for ets in self.handles.keys():
            if self.lastSeen[ets] < int(datetime.now().timestamp()) - self.max_file_open_time:
                self.closeFile(ets)

    def getETSFile(self, ets: os.path) -> OlympusETSFile:
        if ets in self.handles.keys():
            if DEVELOPMENT_MODE: print(f"Serving cached file handle for file {ets}")
            self.lastSeen[ets] = int(datetime.now().timestamp())
            self.manageOpenFileHandles()
            return self.handles[ets]
        self.manageOpenFileHandles()
        return self.openFile(ets)


class ImageHTTPRequestHandler(server.BaseHTTPRequestHandler):

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html;charset=UTF-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

    def send_debug(self, message, title="Debug Info"):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(f"<html><head><title>{title}</title></head><body><h1>{title}</h1><hr /><p>{message}</p></body></html>".encode("utf-8"))

    def figureOutPath(self):
        assert self.path[:len(URL_TRAILING)] == URL_TRAILING, f"path does not start with {URL_TRAILING} but is {self.path}."
        request_path = self.path[len(URL_TRAILING):]
        request_path = request_path.split("/")
        assert len(request_path)>2, "path has to contain at least a directory, a filename and a stack id"
        directory = request_path[0]
        filename = request_path[1]
        stack = int(request_path[2])
        assert len(filename)>0, "filename has to be specified."
        # WARNING THIS REGEX IS DESIGNED TO BE "SAFE", DISALLOWING ENTERING ANY MALICIOUS CONTENT. BE SURE TO KEEP IT OR IF CHANGING ENSURING THAT NO ARBITRARY PATHS ETC CAN BE ENTERED!
        assert re.match("^[A-Za-z0-9_]{3,15}$", filename), "filename has to be alphanumeric and between 3-15 chars long"
        assert re.match("^[A-Za-z0-9_]{3,15}$", directory), "directory has to be alphanumeric and between 3-15 chars long"
        vsi = os.path.join(FILES_PATH,directory, f"{filename}.vsi")
        ets = os.path.join(FILES_PATH,directory, f"_{filename}_", f"Stack{stack}", "frame_t.ets")
        assert os.path.exists(vsi), f"VSI file {vsi} not found"
        assert os.path.exists(ets), f"ETS file {ets} found"
        if len(request_path)==3:
            return vsi, ets, None

        if request_path[3] == 'cell':
            assert len(request_path) ==6 or len(request_path) == 8, "wrong number of arguments"
            #Speciality: Return individual cell image
            if len(request_path)==8:
                pass
                w = int(request_path[6])
                h = int(request_path[7])
            else:
                w = 128
                h = 128
            assert w > 9 and w < 1025, f"width has to be within bounds [10,1024]"
            assert h > 9 and h < 1025, f"height has to be within bounds [10,1024]"
            x = int(request_path[4])-w/2
            y = int(request_path[5])-h/2
            return vsi, ets, (x,y,w,h)
        assert len(request_path) == 6, "wrong number of arguments"
        level = int(request_path[3])
        x = int(request_path[4])
        y = int(request_path[5])
        return vsi, ets, (x, y, level)

    def DEVEL_serve_file(self):
        """
        DANGEROUS, USE ONLY FOR DEVELOPMENT. DOES NOT CHECK PATH!!!
        :return:
        """
        p = os.path.join(FILES_PATH, *self.path.split("/"))
        if os.path.isfile(p):
            if DEVELOPMENT_MODE: print(f"Serving static file at path {p}")
            mime_type = MimeTypes().guess_type(self.path)
            self.send_response(200)
            self.send_header('Content-Type',f"{mime_type[0]};charset=UTF-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            with open(p, 'rb') as f:
                self.wfile.write(f.read())
            return True
        return False


    def do_GET(self):
        if DEVELOPMENT_MODE and self.DEVEL_serve_file(): return
        try:
            vsi, ets, coordinates = self.figureOutPath()
        except AssertionError as e:
            self.send_error(404, "file not found", str(e))
            return
        except ValueError as e:
            return self.send_error(400, "bad request", f"Got unexpected value: {e}")
            return
        ets_handle = etsHandler.getETSFile(ets)
        if coordinates is None:
            self.serve_json_overview(ets_handle)
            return
        if len(coordinates)==4: #get image
            try:
                img = ets_handle.getImage(coordinates)
                assert img is not None, f"Image at coordinates {coordinates} not found."
                self.send_response(200)
                self.send_header('Content-Type', 'image/png')
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(img)
                return
            except AssertionError as e:
                self.send_error(404, "coordinates not found", str(e))
                return
        else:
            try:
                tile = ets_handle.getTile(coordinates[0],coordinates[1],0, coordinates[2])
                assert tile is not None, f"tile for coordinates x={coordinates[0]}, y={coordinates[1]}, z=0, level={coordinates[2]} not found."
                self.send_response(200)
                self.send_header('Content-Type', 'image/jpeg')
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(tile.getBytes())
                return
            except AssertionError as e:
                self.send_error(404, "coordinates not found", str(e))
                return


    def serve_json_overview(self, ets: OlympusETSFile):
        self.send_response(200)
        self.send_header("Content-Type", "text/json;charset=UTF-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        lvl0_dim = ets.dim(0)
        json_dict = {
            'tile': ets.content['length'],
            'levels': max(ets.dims.keys()),
            'width': ets.content['length'] * lvl0_dim[0],
            'height': ets.content['length'] * lvl0_dim[1]
        }
        self.wfile.write(json.dumps(json_dict, ensure_ascii=False, indent=4, check_circular=False).encode("utf-8"))

if __name__=="__main__":
    etsHandler = etsFileHandler(MAX_OPEN_FILES, MAX_OPEN_TIME)
    with server.ThreadingHTTPServer(('localhost', PORT), ImageHTTPRequestHandler) as httpd:
        print("serving at port", PORT)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt as e:
            del etsHandler

