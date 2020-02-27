#!/usr/bin/env python3
import os
import sys
from subprocess import Popen, PIPE
import fcntl
import serial
import time

from pocs.mount import create_mount_from_config
from panoptes.utils.error import MountNotFound

from panoptes.utils.config.client import set_config

from peas.sensors import detect_board_on_port

BASEDIR = 'cd /sys/devices/pci0000:00'
DataStorageMatrix = []
TemporaryDataStorageList = []

# Finding dev path and relating it to bus number and dev number
StartLocationProbe = BASEDIR + ' ; find -maxdepth 2 -name "usb*"'
StartLocation = Popen(
    StartLocationProbe,
    shell=True,
    bufsize=64,
    stdin=PIPE,
    stdout=PIPE,
    close_fds=True).stdout.read().strip().decode('utf-8').split('\n')
NEWBASEDIR = BASEDIR + ' ; cd ' + StartLocation[0]
SearchLocationProbe = NEWBASEDIR + ' ; find . -name "*-*:*"'
SearchLocations = Popen(
    SearchLocationProbe,
    shell=True,
    bufsize=64,
    stdin=PIPE,
    stdout=PIPE,
    close_fds=True).stdout.read().strip().decode('utf-8').split('\n')
Num_Searches = len(SearchLocations)
i = Num_Searches
while i > 0:
    CurrentIndex = Num_Searches - i
    SearchLocation = NEWBASEDIR + ' ; cd ' + SearchLocations[CurrentIndex]
    DevPathProbe = SearchLocation + ' ; find -maxdepth 2 ! -name "tty"  -name "tty*"'
    DEVPATH = Popen(
        DevPathProbe,
        shell=True,
        bufsize=64,
        stdin=PIPE,
        stdout=PIPE,
        close_fds=True).stdout.read().strip().decode('utf-8')
    if (DEVPATH == ""):
        i -= 1
        continue
    if (DEVPATH.startswith("./tty/")):
        PARSEDDEVPATH = DEVPATH.split("./tty/")
        PARSEDDEVPATH.remove("")
    if (DEVPATH != ""):
        if (DEVPATH.startswith("./tty/")):
            PARSEDDEVPATH = DEVPATH.split("./tty/")
        elif (DEVPATH.startswith("./tty")):
            PARSEDDEVPATH = DEVPATH.split("./")
    PARSEDDEVPATH.remove("")
    BUSNUMDEVNUMPROBE = SearchLocation + ' ; cd .. ; echo -n "Bus: " ; cat busnum ; echo -n " Device: " ; cat devnum ; echo -n " ID " ; cat idVendor ; echo -n ":" ; cat idProduct ; echo -n " " ; cat manufacturer ; echo -n ", " ; cat product'
    BUSNUMDEVNUM = Popen(
        BUSNUMDEVNUMPROBE,
        shell=True,
        bufsize=64,
        stdin=PIPE,
        stdout=PIPE,
        close_fds=True).stdout.read().strip().decode('utf-8')
    TemporaryDataStorageList = BUSNUMDEVNUM.split("\n")
    TemporaryDataStorageList.insert(0, PARSEDDEVPATH[0])
    TemporaryDataStorageList.insert(1, " ")
    DataStorageMatrix.append(TemporaryDataStorageList)
    i -= 1
# Print out that parsed info!
for x in DataStorageMatrix:
    print("")
    for y in x:
        print(y, end='')
print("")

DevPaths = []
DataStorageMatrixLength = len(DataStorageMatrix)
k = DataStorageMatrixLength
while k > 0:
    DataSet = DataStorageMatrixLength - k
    if (DataStorageMatrix[DataSet][0].startswith("ttyUSB")):
        DevPaths.append(DataStorageMatrix[DataSet][0])
        k -= 1
        continue
    k -= 1

# Identify Mount
for port in DevPaths:
    usb_port = f'/dev/{port}'
    set_config('mount.serial.port', usb_port)
    mount_info = {
        'driver': 'ioptron',
        'serial': {
            'port': usb_port
        }
    }

    mount = create_mount_from_config(mount_info=mount_info)

    try:
        mount.initialize()
    except MountNotFound:
        continue

    print(f'\033[1;32;40mFound mount on {usb_port}, saving to config\033[1;37;40m')
    set_config('mount.serial.port', usb_port)
    break

# Identify Weather Sensor


# Identify Arduinos
# Isolate Arduino device paths
k = DataStorageMatrixLength
DevPaths.clear()
while k > 0:
    DataSet = DataStorageMatrixLength - k
    if (DataStorageMatrix[DataSet][0].startswith("ttyACM")):
        DevPaths.append(DataStorageMatrix[DataSet][0])
        k -= 1
        continue
    k -= 1

# Setup arduino-cli commands for this docker image
os.system("arduino-cli core update-index")
fqbn_raw = os.popen("arduino-cli board list | awk '{ print $7 }'").read()
fqbn = fqbn_raw.split('\n')[1]
fqbnCoreElements = fqbn.split(":")
fqbnCore = fqbnCoreElements[0] + ":" + fqbnCoreElements[1]
os.system(f'arduino-cli core install {fqbnCore}')
# Switch to the arduino_files directory to have the sketch upload properly
os.chdir('/var/panoptes/POCS/resources/arduino_files')
for port in DevPaths:
    # Upload sketch
    usb_port = f'/dev/{port}'
    print(f'Uploading identifier Arduino sketch to {usb_port}.')
    os.system(f'arduino-cli upload -p {usb_port} --fqbn {fqbn} identifier')
    print(f'Sketch uploaded to Arduino on {usb_port}')

    # Get and parse serial output
    with serial.Serial(usb_port, 9600, timeout=3) as ser:
        time.sleep(10)
        # 53 chars since one full temp data is 27, 53 ensures full capture of
        # at least one full temp report
        identifier_output = ser.read(53)
        identifier_output = identifier_output.decode("utf-8")
    serial_lines = identifier_output.split('\n')
    for line in serial_lines:
        if(len(line) > 26):
            full_reading = line
            break
    if (full_reading == '"temps":[-127.00,-127.00,-127.00]'):
        print(f'\033[1;32;40mFound camera_board Arduino on {usb_port}, saving to config.\033[1;37;40m')
        set_config('environment.camera_board.serial_port', usb_port)
        # Ask user if they want to upload the Arduino script, don't force
        # in case the build is different
        while True:
            response = input(
                "Automatically upload the Arduino sketch for the camera board Arduino (camera_board.ino) [y/n]?")
            if response.lower().startswith('y'):
                print("Uploading sketch...")
                os.chdir('/var/panoptes/POCS/resources/arduino_files')
                os.system(f'arduino-cli upload -p {usb_port} --fqbn {fqbn} camera_board')
                print('\033[1;32;40mSketch uploaded.\033[1;37;40m')
                break
            elif response.lower().startswith('n'):
                print("Exiting and printing collected information.")
                break
            else:
                print("A 'yes' or 'no' response is required")
    elif (full_reading != '"temps":[-127.00,-127.00,-127.00]'):
        print(f'\033[1;32;40mFound power_board Arduino on {usb_port}, saving to config.\033[1;37;40m')
        set_config('environment.control_board.serial_port', usb_port)
        while True:
            response = input(
                "Automatically upload the Arduino sketch for the control board Arduino (power_board.ino) [y/n]?")
            if response.lower().startswith('y'):
                print("Uploading sketch...")
                os.chdir('/var/panoptes/POCS/resources/arduino_files')
                os.system(f'arduino-cli upload -p {usb_port} --fqbn {fqbn} power_board')
                print('\033[1;32;40mSketch uploaded.\033[1;37;40m')
                break
            elif response.lower().startswith('n'):
                print("Exiting and printing collected information.")
                break
            else:
                print("A 'yes' or 'no' response is required")
    else:
        print(f'\033[91mProblem detecting board with Arduino on {usb_port}!\033[00m')
