#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This script takes a list of RINEX Hanakata compressed files (.d.Z or .d.gz or .rnx.gz),
loop the rinex files modifiy the file's header. It then write them back to Hanakata
compressed format in an output folder. It permits also to rename the files changing
the four first characters of the file name with another station code. It can write
those files with the long name naming convention.

Two ways of passing parameters to modifiy headers are possible:

* --modification_kw : you pass as argument the field(s) that you want to modifiy and its value.
                      Acceptable_keywords are : station, receiver_serial, receiver_type, receiver_fw,
                      antenna_serial, antenna_type, antenna_X_pos, antenna_Y_pos, antenna_Z_pos,
                      antenna_X_delta, antenna_Y_delta, antenna_Z_delta,
                      operator, agency, observables

* --sitelog  : you pass a sitelog file. The script will treat only files corresponding to
               the same station as the provided sitelog. You then have to pass a list
               of files comming from the right station. If not, they will be rejected.
               The script will take the start and end time of each proceeded file
               and use them to extract from the sitelog the station instrumentation
               of the corresponding period and fill file's header with following infos :
                       Four Character ID
                       X coordinate (m)
                       Y coordinate (m)
                       Z coordinate (m)
                       Receiver Type
                       Serial Number
                       Firmware Version
                       Satellite System (will translate this info to one-letter code, see RinexFile.set_observable_type())
                       Antenna Type
                       Serial Number
                       Marker->ARP Up Ecc. (m)
                       Marker->ARP East Ecc(m)
                       Marker->ARP North Ecc(m)
                       On-Site Agency Preferred Abbreviation
                       Responsible Agency Preferred Abbreviation

You can not provide both --modification_kw and --sitelog options.

USAGE :

RINEXLIST : Rinex list file
OUTPUTFOLDER : Folder where to write the modified files. This is a compulsory
argument, you can not modify files inplace.

OPTIONS :

-k : --modification_kw :    Header fields that you want to modify.
-s : --sitelog :            Sitelog file in witch rinexmod will find file's period's
                            instrumentation informations, or folder containing sitelogs.
                            The sitelogs must be valid as the script does not check it.
-f : --force :              Force appliance of sitelog based header arguments when
                            station name within file does not correspond to sitelog.
-i : --ignore :             Ignore firmware changes between instrumentation periods
                            when getting headers args info from sitelogs.
-m : --marker :             A four characater station code that will be used to rename
                            input files.
-n : --ninecharfile :       path a of a list file containing 9-char. site names from
                            the M3G database generated with get_m3g_stations.
                            Not mandatory, but nessessary to get the country code to rename
                            files to long name standard. If not provided the country code will be XXX.
-a : --alone :               Option to provide if you want to run this script on a alone
                            rinex file and not on a list of files.
-c : --compression :        Set file's compression (acceptables values : 'gz' (recommended
                            to fit IGS standards), 'Z'. Default value will retrieve
                            the actual compression of the input file.
-l : --longname             Rename file using long name rinex convention.
-r : --reconstruct :        Reconstruct files subdirectory. You have to indicate the
                            part of the path that is common to all files in the list and
                            that will be replaced with output folder.
-v : --verbose:             Will prompt file's metadata before and after modifications.

EXAMPLES:

./rinexmod.py  RINEXLIST OUTPUTFOLDER (-k antenna_type='ANT TYPE' antenna_X_pos=9999 agency=AGN) (-m AGAL) (-s) (-r /ROOTFOLDER/) (-v)
./rinexmod.py  RINEXLIST OUTPUTFOLDER (-l ./sitelogsfolder/stationsitelog.log) (-m AGAL) (-s) (-r /ROOTFOLDER/) (-f) (-i) (-v)

REQUIREMENTS :

You need Python Hatanaka library from Martin Valgur:

pip install hatanaka

2021-02-07 Félix Léger - leger@ipgp.fr
"""

import os, re
from   datetime import datetime
import logging
from sitelogs_IGS import SiteLog
from rinexfile import RinexFile
import hatanaka


def loggersVerbose(logfile):
    '''
    This function manage logging levels. It has two outpus, one to the prompt,
    the other to a logfile defined by 'logfile'.
    '''

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    # This handler will write to a log file
    filehandler = logging.FileHandler(logfile, mode='a', encoding='utf-8')
    # This one is for prompt
    prompthandler = logging.StreamHandler()

    promptformatter = logging.Formatter('%(asctime)s - %(levelname)-7s - %(message)s')
    fileformatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    prompthandler.setFormatter(promptformatter)
    filehandler.setFormatter(fileformatter)

    # Setting handler logging level.
    prompthandler.setLevel(logging.INFO)
    filehandler.setLevel(logging.WARNING)

    logger.addHandler(prompthandler)
    logger.addHandler(filehandler)

    return logger


def listfiles(directory, extension):
    # returns list of paths
    liste = []
    extension = extension.lower()
    for dirpath, dirnames, files in os.walk(directory):
        for name in files:
            if name.lower().endswith(extension):
                file = os.path.join(dirpath, name)
                liste.append(file)
    return liste


def rinexmod(rinexlist, outputfolder, marker, longname, alone, sitelog, force, reconstruct, ignore, ninecharfile, modification_kw, verbose, compression):
    """
    Main function for reading a Rinex list file. It process the list, and apply
    file name modification, teqc args based header modification, or sitelog-based
    header modification.
    """
    # If sitelog option, no modification arguments must be provided
    if sitelog and modification_kw:
        print('# ERROR : If you get metadata from sitelog, don\'t provide arguments for modification (-k, --modification_kw option) !')
        return

    # If no longname, modification_kw and sitelog, return
    if not sitelog and not modification_kw and not marker and not longname:
        print('# ERROR : No action asked, provide at least one of the following args : --sitelog, --modification_kw, --marker, --longname.')
        return

    # If force option provided, check if sitelog option too, if not, not relevant.
    if force and not sitelog:
        print('# ERROR : --force option is meaningful only when using also --sitelog option with one sitelog provided')
        return

    # If ignore option provided, check if sitelog option too, if not, not relevant.
    if ignore and not sitelog:
        print('# ERROR : --ignore option is meaningful only when using also --sitelog option')
        return

    # If inputfile doesn't exists, return
    if isinstance(rinexlist, list):
        pass
    elif not os.path.isfile(rinexlist):
        print('# ERROR : The input file doesn\'t exist : ' + rinexlist)
        return

    outputfolder = os.path.abspath(outputfolder)

    if not os.path.isdir(outputfolder):
        # mkdirs ???
        os.mkdir(outputfolder)

    ########### Logging levels ###########

    # Creating log file
    now = datetime.now()
    dt = datetime.strftime(now, '%Y%m%d%H%M%S')
    logfile = os.path.join(outputfolder, dt + '_' + 'rinexmod.log')

    logger = loggersVerbose(logfile)

    ####### Converting sitelog to list of sitelog objects ######

    if sitelog:
        # Case of one sitelog:
        if os.path.isfile(sitelog):

            # Creating sitelog object
            sitelogobj = SiteLog(sitelog)
            # If sitelog is not parsable
            if sitelogobj.status != 0:
                print('# ERROR : The sitelog is not parsable : ' + sitelog)
                return

            sitelogs = [sitelogobj]

        # Case of a folder
        elif os.path.isdir(sitelog):

            if force:
                    print('# ERROR : --force option is meaningful only when providing a sole sitelog and not a folder contaning various ones')
                    return

            sitelog_extension = '.log'
            all_sitelogs = listfiles(sitelog, sitelog_extension)

            sitelog_pattern = re.compile('\w{3,9}_\d{8}.log')
            all_sitelogs = [file for file in all_sitelogs if sitelog_pattern.match(os.path.basename(file))]

            ### Get last version of sitelogs if multiple available
            sitelogs = []
            # We list the available stations to group sitelogs
            sitelogsta = [os.path.basename(sitelog)[0:4] for sitelog in all_sitelogs]

            for sta in sitelogsta:
                # Grouping by station
                sta_sitelogs = [sitelog for sitelog in all_sitelogs if os.path.basename(sitelog)[0:4] == sta]
                # Getting dates from basename
                sitelogs_dates = [os.path.splitext(os.path.basename(sitelog))[0][-8:] for sitelog in sta_sitelogs]
                # Parsing 'em
                sitelogs_dates = [datetime.strptime(sitelogs_date, '%Y%m%d' ) for sitelogs_date in sitelogs_dates]
                # We get the max date and put it back to string format.
                maxdate = max(sitelogs_dates).strftime('%Y%m%d')
                # We filter the list with the max date string, and get a one entry list, then transform it to string
                sta_sitelog = [sitelog for sitelog in sta_sitelogs if maxdate in os.path.splitext(os.path.basename(sitelog))[0][-8:]][0]
                # Creating sitelog object
                sitelogobj = SiteLog(sta_sitelog)

                # If sitelog is not parsable
                if sitelogobj.status != 0:
                    print('# ERROR : The sitelog is not parsable : ' + sitelogobj.path)
                    return

                # Appending to list
                sitelogs.append(sitelogobj)

    ####### Checking input keyword modification arguments ######

    if modification_kw:

        acceptable_keywords = ['station',
                               'receiver_serial',
                               'receiver_type',
                               'receiver_fw',
                               'antenna_serial',
                               'antenna_type',
                               'antenna_X_pos',
                               'antenna_Y_pos',
                               'antenna_Z_pos',
                               'antenna_X_delta',
                               'antenna_Y_delta',
                               'antenna_Z_delta',
                               'operator',
                               'agency',
                               'observables']

        for kw in modification_kw:
            if kw not in acceptable_keywords:
                print('# ERROR : \'{}\' is not an acceptable keyword for header modification.'.format(kw))
                return

    ### Opening and reading lines of the file containing list of rinex to proceed
    if alone:
        rinexlist = [rinexlist]
    elif isinstance(rinexlist, list):
        pass
    else:
        try:
            rinexlist = [line.strip() for line in open(rinexlist).readlines()]
        except:
            print('# ERROR : The input file is not a list : ' + rinexlist)
            return

    ### Get the 4 char > 9 char dictionnary from the input list
    if ninecharfile:
        if not os.path.isfile(ninecharfile):
            print('# ERROR : The specified 9-chars. list file does not exists : ' + ninecharfile)
            return
        elif longname:
            with open(ninecharfile,"r+")  as F:
                nine_char_list = F.readlines()
                nine_char_dict = dict()

            for site_key in nine_char_list:
                nine_char_dict[site_key[:4].lower()] = site_key.strip()

    ### Check that the provided marker is a 4-char station name
    if marker and len(marker) != 4:
        print('# ERROR : The marker provided is not 4-char valid : ' + marker)
        return

    ### Looping in file list ###

    return_lists = {}

    for file in rinexlist:

        logger.info('# File : ' + file)

        if reconstruct:
            if not reconstruct in file:
                logger.error('{:60s} - {}'.format('31 - The subfolder can not be reconstructed for file', file))
                continue

            # We construct the output path with relative path between file name and parameter
            relpath = os.path.relpath(os.path.dirname(file), reconstruct)
            myoutputfolder = os.path.join(outputfolder, relpath)
            if not os.path.isdir(myoutputfolder):
                os.makedirs(myoutputfolder)
        else:
            myoutputfolder = outputfolder

        if os.path.abspath(os.path.dirname(file)) == myoutputfolder:
            logger.error('{:60s} - {}'.format('30 - Input and output folders are the same !', file))
            continue

        # Declare the rinex file as an object
        rinexfileobj = RinexFile(file)

        if rinexfileobj.status == 1:
            logger.error('{:60s} - {}'.format('01 - The specified file does not exists', file))
            continue

        if rinexfileobj.status == 2:
            logger.error('{:60s} - {}'.format('02 - Not an observation Rinex file', file))
            continue

        if rinexfileobj.status == 3:
            logger.error('{:60s} - {}'.format('03 - Invalid or empty Zip file', file))
            continue

        if rinexfileobj.status == 4:
            logger.error('{:60s} - {}'.format('04 - Invalid Compressed Rinex file', file))
            continue

        if marker:
            # We store the old marker name to add a comment in rinex file's header
            modification_source = rinexfileobj.filename[:4]
            # We set the station in the filename to the new marker
            if rinexfileobj.name_conv == 'SHORT':
                rinexfileobj.filename = marker.lower() + rinexfileobj.filename[4:]
            else:
                rinexfileobj.filename = marker.upper() + rinexfileobj.filename[4:]

        if longname:
            # We rename the file to the rinex long name convention
            # Get the site 9-char name
            if ninecharfile:
                if not rinexfileobj.filename[:4].lower() in nine_char_dict:
                    logger.warning('{:60s} - {}'.format('32 - Station\'s country not retrevied, will not be properly renamed', file))
                    site = rinexfileobj.filename[:4].upper() + "00XXX"
                else:
                    site = nine_char_dict[rinexfileobj.filename[:4].lower()].upper()
            # elif sitelog: # XXXXXXX probleme si multiples sitelogs
            #     site = os.path.basename(sitelog)[:9].upper()
            else:
                logger.warning('{:60s} - {}'.format('32 - Station\'s country not retrevied, will not be properly renamed', file))
                site = rinexfileobj.filename[:4].upper() + "00XXX"

            if rinexfileobj.file_period == '01D':
                timeformat = '%Y%j0000' # Start of the day
            else:
                timeformat = '%Y%j%H00' # Start of the hour

            rinexfileobj.filename = '_'.join((site.upper(),
                                              rinexfileobj.start_date.strftime(timeformat),
                                              rinexfileobj.file_period,
                                              rinexfileobj.sample_rate,
                                              rinexfileobj.observable_type + 'O.rnx')) # O for observation

            if not compression:
                # If not specified, we set compression to gz when file changed to longname
                compression = 'gz'

        if sitelog:

            # Station name from the rinex's header line
            station_meta = rinexfileobj.get_station().lower()

            # Finding the right sitelog. If is list, can not use force. If no sitelog found, do not process.
            if station_meta not in [sitelog.station for sitelog in sitelogs]:
                if len(sitelogs) == 1:
                    if not force:
                        logger.error('{:60s} - {}'.format('33 - File\'s station does not correspond to provided sitelog - use -f option to force', file))
                        continue
                    else:
                        logger.warning('{:60s} - {}'.format('34 - File\'s station does not correspond to provided sitelog, processing anyway', file))
                else:
                    logger.error('{:60s} - {}'.format('33 - No provided sitelog for this file\'s station', file))
                    continue
            else:
                sitelogobj = [sitelog for sitelog in sitelogs if sitelog.station == station_meta][0]

            modification_source = sitelogobj.filename

            # Station name from the sitelog
            sitelog_sta_code = sitelogobj.info['1.']['Four Character ID'].lower()

            if sitelog_sta_code != station_meta:
                if not force:
                    logger.error('{:60s} - {}'.format('33 - File\'s station does not correspond to provided sitelog - use -f option to force', file))
                    continue
                else:
                    logger.warning('{:60s} - {}'.format('34 - File\'s station does not correspond to provided sitelog, processing anyway', file))

            # Get rinex header values from sitelog infos and start and end time of the file
            # ignore option is to ignore firmware changes between instrumentation periods.
            metadata_vars, ignored  = sitelogobj.rinex_metadata_lines(rinexfileobj.start_date, rinexfileobj.end_date, ignore)

            if not metadata_vars:
                logger.error('{:60s} - {}'.format('35 - No instrumentation corresponding to the data period on the sitelog', file))
                continue

            if ignored:
                logger.warning('{:60s} - {}'.format('36 - Instrumentation cames from merged periods of sitelog with different firmwares, processing anyway', file))

            (fourchar_id, observable_type, agencies, receiver, antenna, antenna_pos, antenna_delta) = metadata_vars

            if verbose:
                logger.info('File Metadata :\n' + rinexfileobj.get_metadata())

            # # Apply the modifications to the RinexFile object
            rinexfileobj.set_marker(fourchar_id)
            rinexfileobj.set_receiver(**receiver)
            rinexfileobj.set_antenna(**antenna)
            rinexfileobj.set_antenna_pos(**antenna_pos)
            rinexfileobj.set_antenna_delta(**antenna_delta)
            rinexfileobj.set_agencies(**agencies)
            rinexfileobj.set_observable_type(observable_type)

        if modification_kw:

            if verbose:
                logger.info('File Metadata :\n' + rinexfileobj.get_metadata())

            modification_source = 'command line'

            rinexfileobj.set_marker(modification_kw.get('station'))

            rinexfileobj.set_receiver(modification_kw.get('receiver_serial'),
                                    modification_kw.get('receiver_type'),
                                    modification_kw.get('receiver_fw'))

            rinexfileobj.set_antenna(modification_kw.get('antenna_serial'),
                                     modification_kw.get('antenna_type'))

            rinexfileobj.set_antenna_pos(modification_kw.get('antenna_X_pos'),
                                         modification_kw.get('antenna_Y_pos'),
                                         modification_kw.get('antenna_Z_pos'))

            rinexfileobj.set_antenna_delta(modification_kw.get('antenna_X_delta'),
                                           modification_kw.get('antenna_Y_delta'),
                                           modification_kw.get('antenna_Z_delta'))

            rinexfileobj.set_agencies(modification_kw.get('operator'),
                                      modification_kw.get('agency'))

            rinexfileobj.set_observable_type(modification_kw.get('observables'))

        if verbose:
            logger.info('File Metadata :\n' + rinexfileobj.get_metadata())

        # Adding comment in the header
        rinexfileobj.add_comment('rinexmoded on {}'.format(datetime.strftime(now, '%Y-%m-%d %H:%M')))
        if sitelog or modification_kw:
            rinexfileobj.add_comment('rinexmoded from {}'.format(modification_source))
        if marker:
            rinexfileobj.add_comment('file assigned from {}'.format(modification_source))

        ##### We convert the file back to Hatanaka Compressed Rinex #####
        if not compression:
            compression = rinexfileobj.compression

        outputfile = rinexfileobj.write_to_path(myoutputfolder, compression = compression)

        if verbose:
            logger.info('Output file : ' + outputfile)

        ### Construct return dict by adding key if doesn't exists and appending file to corresponding list ###
        major_rinex_version = rinexfileobj.version[0]
        # Dict ordered as : RINEX_VERSION, SAMPLE_RATE, FILE_PERIOD
        if major_rinex_version not in return_lists:
            return_lists[major_rinex_version] = {}
        if rinexfileobj.sample_rate not in return_lists[major_rinex_version]:
            return_lists[major_rinex_version][rinexfileobj.sample_rate] = {}
        if rinexfileobj.file_period not in return_lists[major_rinex_version][rinexfileobj.sample_rate]:
            return_lists[major_rinex_version][rinexfileobj.sample_rate][rinexfileobj.file_period] = []

        return_lists[major_rinex_version][rinexfileobj.sample_rate][rinexfileobj.file_period].append(outputfile)

    logger.handlers.clear()

    return return_lists


if __name__ == '__main__':

    import argparse

    class ParseKwargs(argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):
            setattr(namespace, self.dest, dict())
            for value in values:
                key, value = value.split('=')
                getattr(namespace, self.dest)[key] = value

    # Parsing Args
    parser = argparse.ArgumentParser(description='Read a Sitelog file and create a CSV file output')
    parser.add_argument('rinexlist', type=str, help='Input rinex list file to process')
    parser.add_argument('outputfolder', type=str, help='Output folder for modified Rinex files')
    parser.add_argument('-s', '--sitelog', help='Get the rinex header values from file\'s station\'s sitelog. Provide a sitelog or a folder contaning sitelogs.', type=str, default=0)
    parser.add_argument('-k', '--modification_kw', help='''Modification keywords for header. Format : keyword_1=\'value\' keyword2=\'value\'. Acceptable keywords:\n
                                                           station, receiver_serial, receiver_type, receiver_fw, antenna_serial, antenna_type,
                                                           antenna_X_pos, antenna_Y_pos, antenna_Z_pos, antenna_X_delta, antenna_Y_delta, antenna_Z_delta,
                                                           operator, agency, observables''', nargs='*', action=ParseKwargs, default=0)
    parser.add_argument('-m', '--marker', help='Change 4 first letters of file\'s name to set it to another marker', type=str, default=0)
    parser.add_argument('-n', '--ninecharfile', help='Path of a file that contains 9-char. site names from the M3G database', type=str, default=0)
    parser.add_argument('-r', '--reconstruct', help='Reconstruct files subdirectories. You have to indicate the part of the path that is common to all files and that will be replaced with output folder', type=str, default=0)
    parser.add_argument('-c', '--compression', type=str, help='Set file\'s compression (acceptables values : \'gz\' (recommended to fit IGS standards), \'Z\')', default=0)
    parser.add_argument('-l', '--longname', help='Rename file using long name rinex convention', action='store_true', default=0)
    parser.add_argument('-f', '--force', help='Force appliance of sitelog based header values when station name within file does not correspond to sitelog', action='store_true')
    parser.add_argument('-i', '--ignore', help='Ignore firmware changes between instrumentation periods when getting header values info from sitelogs', action='store_true')
    parser.add_argument('-a', '--alone', help='INPUT is a alone Rinex file and not a file containing list of Rinex files paths', action='store_true')
    parser.add_argument('-v', '--verbose', help='Prompt file\'s metadata before and after modifications.', action='store_true', default=0)

    args = parser.parse_args()

    rinexlist = args.rinexlist
    outputfolder = args.outputfolder
    marker = args.marker
    longname = args.longname
    ninecharfile = args.ninecharfile
    alone = args.alone
    sitelog = args.sitelog
    force = args.force
    ignore = args.ignore
    reconstruct = args.reconstruct
    compression = args.compression
    verbose = args.verbose
    modification_kw = args.modification_kw

    rinexmod(rinexlist, outputfolder, marker, longname, alone, sitelog, force, reconstruct, ignore, ninecharfile, modification_kw, verbose, compression)
