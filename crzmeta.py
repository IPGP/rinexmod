#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extract metadata from crz file.

EXAMPLE:
./crzmeta.py  RINEXFILE

REQUIREMENTS :

You need Python Hatanaka library from Martin Valgur:

pip install hatanaka

2019-12-13 Félix Léger - leger@ipgp.fr
"""

from rinexfile import RinexFile


def crzmeta(rinexfile):

    # Declare the rinex file as an object
    rinexfileobj = RinexFile(rinexfile)

    if rinexfileobj.status == 1:
        print('{:45s} - {}'.format('01 - The specified file does not exists', rinexfile))
        return

    if rinexfileobj.status == 3:
        print('{:45s} - {}'.format('03 - Invalid or empty Zip file', rinexfile))
        return

    if rinexfileobj.status == 4:
        print('{:45s} - {}'.format('04 - Invalid Compressed Rinex file', rinexfile))
        return

    print(rinexfileobj.get_metadata())

    return


if __name__ == '__main__':

    import argparse

    # Parsing Args
    parser = argparse.ArgumentParser(description='Read a Sitelog file and create a CSV file output')
    parser.add_argument('rinexfile', type=str, help='Input rinex list file to process')
    args = parser.parse_args()

    rinexfile = args.rinexfile

    crzmeta(rinexfile)
