#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This script takes a list of RINEX files (.d.Z or .d.gz or .rnx.gz),
and rename them according to the short <> long name convention.
The script recognize automatically the input convention and convert
it to the other one

See rinexrename -h for option description

2022-04-11  - Pierre Sakic & Félix Léger - leger@ipgp.fr

"""

from rinexmod.rinexfile import RinexFile
import shutil, os

def rinexrename(rinexinput, output=None, delete=False, alone=False, country="00XXX"):
    if alone:
        rinexinput = [rinexinput]
    elif isinstance(rinexinput, list):
        pass
    else:
        try:
            rinexinput = [line.strip() for line in open(rinexinput).readlines()]
        except:
            print('# ERROR : The input file is not a list : ' + rinexinput)
            return

    Output_path_list = []

    for rinex in rinexinput:

        RINEX_OBJ = RinexFile(rinex)

        if not output:
            output_dir = os.path.dirname(RINEX_OBJ.path)
        else:
            output_dir = output

        if RINEX_OBJ.name_conv == 'SHORT':
            new_name = RINEX_OBJ.get_longname(monum_country=country)
        elif RINEX_OBJ.name_conv == 'LONG':
            new_name = RINEX_OBJ.get_shortname()

        output_path = os.path.join(output_dir, new_name)

        shutil.copy(RINEX_OBJ.path, output_path)

        if delete:
            os.remove(RINEX_OBJ.path)

        Output_path_list.append(output_path)

    if alone:
        Output_path_list = Output_path_list[0]

    return Output_path_list


def main():
    import argparse


    # Parsing Args
    parser = argparse.ArgumentParser(description='rename a rinex file according to the short <> long name convention')
    parser.add_argument('rinexinput', type=str, help='Input rinex list file to process')
    parser.add_argument('-o', '--output', help='Output directory if different from input one',default=None)
    parser.add_argument('-d', '--delete', help='Delete input rinex file', action='store_true')
    parser.add_argument('-c', '--country', help='The monument/country code needed for the long name convention, e.g. 00FRA. 00XXX if not provided',default="00XXX")
    parser.add_argument('-a', '--alone', help='Input is a alone Rinex file and not a file containing list of Rinex files paths', action='store_true')

    args = parser.parse_args()

    rinexinput = args.rinexinput
    output = args.output
    delete = args.delete
    alone  = args.alone
    country = args.country

    rinexrename(rinexinput, output, delete, alone, country)

if __name__ == '__main__':
    main()