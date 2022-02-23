#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extract metadata from crz file with crz2rnx and teqc.

EXAMPLE:
./crzmeta.py  RINEXFILE

REQUIREMENTS :

You have to have teqc installed and declared in your path.
The program must be present on the machine, if not, available there :
https://www.unavco.org/software/data-processing/teqc/teqc.html#executables

2019-12-13 Félix Léger - leger@ipgp.fr
"""

import subprocess
import tempfile as tmpf
import os, sys, re
from   datetime import datetime
from   shutil import copy, move
import hatanaka


def teqcisrinex(file):
    """
    Calling UNAVCO 'teqc' program via subprocess and returns the probable format
    of file. Parsing the response to find RINEX in it.
    https://www.unavco.org/software/data-processing/teqc/teqc.html#executables
    """
    # teqc +mdf : returns the format of file
    p = subprocess.Popen(['teqc', '+mdf', file], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()

    if 'INEX' in out.decode("utf-8"):
        return True
    else:
        return False


def teqcmeta(file):
    """
    Calling UNAVCO 'teqc' program via subprocess and returns the file's metadata
    The program must be present on the machine, if not, available there :
    https://www.unavco.org/software/data-processing/teqc/teqc.html#executables
    """
    # teqc +meta : get the metadata
    p = subprocess.Popen(['teqc', '+meta', file], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()

    return out.decode("utf-8")


def crzmeta(rinexfile):

    # If inputfile doesn't exists, return
    if not os.path.isfile(rinexfile):
        print('# ERROR : : The input file doesn\'t exist : ' + rinexfile)
        return

    temp_folder = tmpf.mkdtemp()

    success = copy(rinexfile, temp_folder)

    if not success:
        print('# ERROR - Copy of file to temp directory impossible - ' + rinexfile)
        return

    tempfile = os.path.join(temp_folder, os.path.basename(rinexfile))

    ##### Lauchning decompress_on_disk to extract Rinex file from archive #####
    convertedfile = hatanaka.decompress_on_disk(tempfile)

    if not teqcisrinex(convertedfile):
        print('# ERROR - Invalid Compressed Rinex file - ' + rinexfile)
        return
    else:
        metadata = teqcmeta(convertedfile)
        print('\n' + metadata)

    # Removing the rinex file
    os.remove(convertedfile)
    if os.path.isfile(tempfile):
        os.remove(tempfile)
    os.rmdir(temp_folder)

    return


if __name__ == '__main__':

    import argparse

    # Parsing Args
    parser = argparse.ArgumentParser(description='Read a Sitelog file and create a CSV file output')
    parser.add_argument('rinexfile', type=str, help='Input rinex list file to process')
    args = parser.parse_args()

    rinexfile = args.rinexfile

    crzmeta(rinexfile)
