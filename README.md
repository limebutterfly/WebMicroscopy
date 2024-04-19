# Online Microscopy Viewer
This program consists of a python server script serving microscopy tiles from Olympus ETS files 
(recorded for example with a VS200 slide scanner). It also consists of a [Leaflet](https://leafletjs.com) based 
microscopy viewer including a tool do perform a full differential on bone marrow and peripheral blood.

## Purpose

Olympus Slide Scanners can scan slides at high magnification. Images are stored as ".vsi" files and adjacent a container
containing the actual scanned images (tiles) in an ".ets" file.

This program has been tested with very specific settings and might have to be adjusted to your needs. The python script
contains classes to extract tiles from ".ets" files for other purposes.

As a sidenote, ".vsi" files are basically "enhanced" tiffs and can be read by a standard tiff reader. They do contain
a preview of the entire slide as well as the scanned ares.

Although the foundation for this has been prepared in the extraction classes, this program does currently not work with
Z-stacks and expects a planar image.

## Dependencies
* [Python](https://www.python.org) tested with v3.11
* [Pillow](https://pypi.org/project/pillow/) tested with v10.3.0
* [JQuery](https://jquery.com/download/) tested with v3.7.1 -> loaded directly in HTML
* [Leaflet](https://leafletjs.com) tested with v.1.9.4 -> loaded directly in HTML
* [Bootstrap](https://getbootstrap.com) tested with v5.3.3 -> loaded directly in HTML
* VSI Files, unfortunately I can not provide them for you.

## Installation
- Download source code from github
- install python3.11 ([Python Homepage](https://www.python.org)), the script will probably also work with newer and slightly older versions, although I did not test this.
- install Pillow `pip install pillow`
- You need your own VSI files. Unfortunately I can not provide any test files. These files have to be with a folder structure as depicted here:
```
[IMAGES FOLDER]
    [SUBFOLDER]
        [EXAMPLE_IMAGE1.vsi]
       _[EXAMPLE_IMAGE1]_
            stack1
                      frame_t.ets 
           stack10000
               frame_t.ets
               .. other irrelevant files and folders
           stack10002
               frame_t.ets
               ...other irrelevant files and folders
```

This script will only consider frame_t.ets in stack10002. This file contains the interesting stacks for my purpose. You might have to adapt this to your purposes.

- Adapt server.py
```
DEVELOPMENT_MODE = True #change this to fales in production!
PORT = 8080 # PORT TO SERVE ON
FILES_PATH = "/Users/jeremy/Desktop/vsi" # Set Path to Olympus Files
URL_TRAILING = "/microscopy/" # trailing URL, set to "/" to omit.
MAX_OPEN_FILES = 10 #max files that are open simultaneously
MAX_OPEN_TIME = 3600 # one hour
```
- Adapt viewer.html
```
const url='/microscopy' //without trailing /, url to image server
const image_folder='SET_IMAGE_FOLDER_HERE' // folder with image
const image = 'SET_FILE_NAME_HERE' //stem of VSI file
const stack = '10002' // stack id, Usually 10002 as per Olympus standard.
const marker_url = '/viewer/markers' //url to files of marker images, without trailing /
```

## Missing Features
* Olympus uses some proprietary binary format to store additional information in the .vsi file. I think it is really unfortunate, that this is not documented. I would be particularly interested in extracting the position of the stacks on the whole-slide overview as well as knowing the relative position of the individual stacks to eachother. This would allow to load the entire slide preview into Leaflet and showing every stack there, allowing to zoom into all scanned areas (and not just stack10002 as it is now).
* Extend differentiation to classify cells as "abnormal" (e.g. dysplasia) and "normal"

## Copyright and License
(C) 2024 by Jeremy Deuel <jeremy.deuel@usz.ch>
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.