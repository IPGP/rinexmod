#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extract metadata from crz file.

With -p option, will plot the file's samples intervals

EXAMPLE:
./crzmeta.py  RINEXFILE (-p)

REQUIREMENTS :

You need Python Hatanaka library from Martin Valgur:

pip install hatanaka

2019-12-13 Félix Léger - leger@ipgp.fr
"""

from rinexmod.rinexfile import RinexFile


def crzmeta(rinexfile, plot):

    # Declare the rinex file as an object
    rinexfileobj = RinexFile(rinexfile)

    if rinexfileobj.status == 1:
        print('{:45s} - {}'.format('01 - The specified file does not exists', rinexfile))
        return

    if rinexfileobj.status == 2:
        print('{:45s} - {}'.format('02 - Not an observation Rinex file', rinexfile))
        return

    if rinexfileobj.status == 3:
        print('{:45s} - {}'.format('03 - Invalid or empty Zip file', rinexfile))
        return

    if rinexfileobj.status == 4:
        print('{:45s} - {}'.format('04 - Invalid Compressed Rinex file', rinexfile))
        return

    if rinexfileobj.status == 5:
        print('{:45s} - {}'.format('05 -Less than two epochs in the file', rinexfile))
        return

    print(rinexfileobj.get_header()[0])

    # We reload _get_sample_rate method with plot set to true
    if plot:
        rinexfileobj.get_sample_rate(plot = True)

    return


def main():
    import argparse

    # Parsing Args
    parser = argparse.ArgumentParser(description='Read a Sitelog file and create a CSV file output')
    parser.add_argument('rinexfile', type=str, help='Input rinex list file to process')
    parser.add_argument('-p', '--plot', help='Plot file\'s samples intervals', action='store_true', default=0)
    args = parser.parse_args()

    rinexfile = args.rinexfile
    plot = args.plot

    crzmeta(rinexfile, plot)

if __name__ == '__main__':
    main()
