#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""

This script will read a folder and extract rinex files, or read directly
a file containing a list of files. For each of those files, it will lauch rinexmod
function, that will fill the file's header with informations gathered from the
corresponding sitelog, read in the 'sitelogsfolder' folder.
Sitelogs can be updated during the process using --update option.
The corrected files will be written to 'outputfolder' folder, and subfolders
will be reconstructed. The part of the path that is common to all files
must be indictaed in 'reconstruct' and this part of the path will be
replaced with output folder.
All those 3 variables ('sitelogsfolder', 'outputfolder' and 'reconstruct') are
stored in the batch_rinexmod.cfg ini file.

USAGE :

RINEXLIST : Rinex list file or folder containing rinex files. If folder provided,
it will filter files with a regex to get only rinex files.

OPTIONS :

-u : --update :       This option iwll update sitelogs in the reference folder
                      using a M3G webservice. This will launch the get_m3g_sitelogs
                      function, with 'delete' option set to True, so that old
                      version will be deleted.

EXAMPLES:

./batch_rinexmod.py  RINEXLIST (-u)
./rinexmod.py  RINEXFOLDER (-u)

REQUIREMENTS :

You have to have RNX2CRZ, CRZ2RNX, RNX2CRX and CRX2RNX installed and declared in
your path. The program must be present on the machine, if not, available there :
http://terras.gsi.go.jp/ja/crx2rnx.html

You have to have teqc installed and declared in your path.
The program must be present on the machine, if not, available there :
https://www.unavco.org/software/data-processing/teqc/teqc.html#executables

2021-10-25 Félix Léger - felixleger@gmail.com
"""


import os, re
from datetime import datetime
import configparser
# Rinexmod libraries
from rinexmod import rinexmod
from get_m3g_sitelogs import get_m3g_sitelogs


def listfiles(directory, extension):
    # returns list of paths
    liste = []
    extension = extension.lower()
    for dirpath, dirnames, files in os.walk(directory):
        for name in files:
            if name.lower().endswith(extension):
                report = os.path.join(dirpath, name)
                liste.append(report)
    return liste



def batch_rinexmod(rinexlist, update):
    """
    This function will read a folder and extract rinex files, or read directly
    a file containing a list of files. For each of those files, it will lauch rinexmod
    function, that will fill the file's header with informations gathered from the
    corresponding sitelog, read in the 'sitelogsfolder' folder.
    Sitelogs can be updated during the process using --update option.
    The corrected files will be written to 'outputfolder' folder, and subfolders
    will be reconstructed. The part of the path that is common to all files
    must be indictaed in 'reconstruct' and this part of the path will be
    replaced with output folder.
    """

    conf = '/home/leger/Documents/11_Metadonnées_GPS/rinexmod/batch_rinexmod.cfg'

    if not os.path.isfile(conf):
        print('# ERROR : Could not find config file ' + conf)
        # Set exit code to Error
        return 2

    # Reading input file
    config = configparser.RawConfigParser()
    config.read(conf)

    # Reading conf file
    try:
        sitelogsfolder = config.get('batch_rinexmod', 'sitelogsfolder')
        outputfolder = config.get('batch_rinexmod', 'outputfolder')
        reconstruct  = config.get('batch_rinexmod', 'reconstruct')
    except:
        print('# ERROR : missing elements in config file. Please check ' + conf)
        # Set exit code to Error
        return 2

    ########### Creating file list ###########

    # Rinex file extention to filter - empty string for no filer
    rinexfile_extension = '.Z'
    # Rinex naming convention filter
    rinex_pattern = re.compile('\w{3,4}(\d{3}).\.(\d{2})(d|o)')
    # Sitelog file extension
    sitelog_extension = '.log'
    # Sitelog naming convetion filter
    sitelog_pattern = re.compile('\w{3,9}_\d{8}.log')

    # Checking that input exists
    if not os.path.isfile(rinexlist) and not os.path.isdir(rinexlist):
        print('# ERROR : The input file or folder doesn\'t exist : ' + rinexlist)
        return

    # If is a file, test parsing as a list
    if os.path.isfile(rinexlist):

        try:
            rinexlist = [line.strip() for line in open(rinexlist).readlines()]
        except:
            print('# ERROR : The input file is not a list : ' + rinexlist)
            return

    elif os.path.isdir(rinexlist):

        rinexlist = listfiles(rinexlist, rinexfile_extension)

        if len(rinexlist) == 0:
            print('# ERROR : The input folder does not contain any \'{}\' files.'.format(rinexfileextension))
            return

    # Updating sitelogs. True is for deleting old sitelogs version in sitelogsfolder
    if update:
        get_m3g_sitelogs(sitelogsfolder, delete = True)

    # Removing non rinex files
    rinexlist = [file for file in rinexlist if rinex_pattern.match(os.path.basename(file))]

    # Making list of files' stations
    stationlist = [os.path.basename(file)[0:4] for file in rinexlist]
    stationlist = sorted(list(set(stationlist)))

    # Dict to store per station files lists
    files_per_sta = {sta : [] for sta in stationlist}

    # Assign file to station
    for file in rinexlist:
        filestation = os.path.basename(file)[0:4]
        files_per_sta[filestation].append(file)

    # Make list of XXXX_99999999.log sitelog files in local storage folder
    sitelogfiles = listfiles(sitelogsfolder, sitelog_extension)
    sitelogfiles = [file for file in sitelogfiles if sitelog_pattern.match(os.path.basename(file))]

    # Get sitelog for every files_per_sta key
    for sta in files_per_sta.keys():

        # Get all sitelogs corresponding to sta in the sitelogfiles list
        sta_sitelogs = [sitelog for sitelog in sitelogfiles if os.path.basename(sitelog)[0:4] == sta]

        # Check availability of sitelog
        if len(sta_sitelogs) == 0:
            print('# ERROR : No available sitelog for  \'{}\' files.'.format(sta.upper()))
            continue

        # Get last version of sitelog if multiple available
        sitelogs_dates = [os.path.splitext(os.path.basename(sitelog))[0][-8:] for sitelog in sta_sitelogs]
        sitelogs_dates = [datetime.strptime(sitelogs_date, '%Y%m%d' ) for sitelogs_date in sitelogs_dates]
        # We get the max date and put it back to string format.
        maxdate = max(sitelogs_dates).strftime('%Y%m%d')
        # We filter the list with the max date string, and get a one entry list, then transform it to string
        sta_sitelog = [sitelog for sitelog in sta_sitelogs if maxdate in os.path.splitext(os.path.basename(sitelog))[0][-8:]][0]

        rinexmod(rinexlist = files_per_sta[sta],
                 outputfolder = outputfolder,
                 teqcargs = None, name = None, single = False,
                 sitelog = sta_sitelog,
                 force = False,
                 reconstruct = reconstruct,
                 ignore = False, verbose = 0)

    return


if __name__ == '__main__':

    import argparse

    # Parsing Args
    parser = argparse.ArgumentParser(description='Read a Sitelog file and create a CSV file output')
    parser.add_argument('rinexlist', type=str, help='Rinex list file or path to folder containing files to process')
    parser.add_argument('-u', '--update', help='Update sitelogs from M3G repository', action='store_true')


    args = parser.parse_args()
    rinexlist = args.rinexlist
    update = args.update

    batch_rinexmod(rinexlist, update)
