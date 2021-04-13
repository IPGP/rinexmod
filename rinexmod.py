#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This script takes a list of RINEX Hanakata compressed files (.d.Z), extract the
rinex files and allows to pass parameters to teqc to modify headers, then put
them back to Hanakata Z format. It permits also to rename the files changing
the four first characters of the file name with another station code.

Two ways of passing parameters to teqc are possible:

* --teqcargs : you pass as argument the command that teqc has to execute.
               E.g. : --teqcargs "-O.mn 'AGAL' -O.rt 'LEICA GR25'"

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
                       Satellite System (will translate this info to one-letter code, see line 586)
                       Antenna Type
                       Serial Number
                       Marker->ARP Up Ecc. (m)
                       Marker->ARP East Ecc(m)
                       Marker->ARP North Ecc(m)
                       On-Site Agency Preferred Abbreviation
                       Responsible Agency Preferred Abbreviation

You can not provide both --teqcargs and --sitelog options.

USAGE :

RINEXLIST : Rinex list file
OUTPUTFOLDER : Folder where to write the modified files. This is a compulsory
argument, you can not modify files inplace.

OPTIONS :

-t : --teqcargs :     Teqc modification command between double quotes
                      (eg "-O.mn 'AGAL' -O.rt 'LEICA GR25'").
                      You can refer to teqc -help to see which arguments can be
                      passed to teqc. Here, the pertinent ones are mostly those
                      starting with O, that permits to modifiy rinex headers.
-l : --sitelog :      Sitelog file in with rinexmod will find file's period's
                      instrumentation informations. The sitelog must be valid
                      as the script does not check it.
-f : --force :        Force appliance of sitelog based teqc arguments when
                      station name within file does not correspond to sitelog.
-i : --ignore :       Ignore firmware changes between instrumentation periods
                      when getting teqc args info from sitelogs.
-n : --name :         A four characater station code that will be used to rename
                      input files.
-s : --single :       Option to provide if you want to run this script on a single
                      rinex file and not on a list of files.
-r : --reconstruct :  Reconstruct files subdirectory. You have to indicate the
                      part of the path that is common to all files in the list and
                      that will be replaced with output folder.
-v : --verbose:       Increase output verbosity. Will prompt teqc +meta of each
                      file before and after teqc modifications.

EXAMPLES:

./rinexmod.py  RINEXLIST OUTPUTFOLDER (-t "-O.mo 'Abri_du_Gallion' -O.mn 'AGAL' -O.o OVSG") (-n AGAL) (-s) (-r /ROOTFOLDER/) (-vv)
./rinexmod.py  RINEXLIST OUTPUTFOLDER (-l ./sitelogsfolder/stationsitelog.log) (-n AGAL) (-s) (-r /ROOTFOLDER/) (-f) (-i) (-vv)

REQUIREMENTS :

You have to have teqc installed and declared in your path.
The program must be present on the machine, if not, available there :
https://www.unavco.org/software/data-processing/teqc/teqc.html#executables

2021-02-07 Félix Léger - leger@ipgp.fr
"""

import subprocess
import os, sys, re
from   datetime import datetime
import logging
from   shutil import copy, move
import configparser
from sitelogs_IGS import Sitelog
import hatanaka



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


def meta2dict(metadata):
    """ Takes ini style conf, returns dict """
    metadata = '[dummy_section]\n' + metadata

    metadataparser = configparser.RawConfigParser(allow_no_value=True)
    metadataparser.optionxform = str # Respect case
    metadataparser.read_string(metadata)

    metadata = dict(metadataparser['dummy_section'])

    # Correction on antenna type
    metadata['antenna type'] = metadata['antenna type'][:16].rstrip()

    # Date string to datetime object
    metadata['start date & time'] = datetime.strptime(metadata['start date & time'], '%Y-%m-%d %H:%M:%S.%f')
    metadata['final date & time'] = datetime.strptime(metadata['final date & time'], '%Y-%m-%d %H:%M:%S.%f')

    return metadata


def teqcmod(file, teqcargs):
    """
    Calling UNAVCO 'teqc' program via subprocess and use the teqcargs variable to
    modifiy the Rinex file. Tipical use : header modification.
    The program must be present on the machine, if not, available there :
    https://www.unavco.org/software/data-processing/teqc/teqc.html#executables
    Discriminates Notice and Warning messages from error messages, and return only errors.
    """
    tempfile = file + '_tmp'

    # Preparing the teqc command line
    args = ['teqc', '+out', tempfile, teqcargs, file]

    # Run the command
    stdoutdata = subprocess.getoutput(' '.join(args))

    # If teqc writes output message :
    if stdoutdata:
        # Sdterr to list, then quit Notice and Warning messages.
        stdoutdata = stdoutdata.strip().split('\n')
        acceptable = ['notice', 'warning']
        stdoutdata = [l for l in stdoutdata if not any(w in l.lower() for w in acceptable)]
        # If messages left, i.e if error message(s), raise error
        if len(stdoutdata) != 0:
            os.remove(tempfile)
            return stdoutdata
        else:
            stdoutdata = None

    # Replacing the file with the modified temp file
    move(tempfile, file)

    return None


def loggersVerbose(verbose, logfile):
    '''
    This function manage logging levels. It has two outpus, one to the prompt,
    the other to a logfile defined by 'logfile'. We first test if the output
    folder for log file is valid.
    Then, depending on the level of verbose (0, 1 or 2), we increase the level
    of logging to prompt and log file.
    verbose = 0 : Info to prompt, Error to logfile
    verbose = 1 : Debug to prompt, Error to logfile
    verbose = 2 : Debug to prompt, Info to logfile
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

    # Setting handler logging level. Higher level for prompt than for file.
    if verbose == 0: # Minimum logging
        prompthandler.setLevel(logging.INFO)
        filehandler.setLevel(logging.ERROR)
    elif verbose == 1: # Full logging to console
        prompthandler.setLevel(logging.DEBUG)
        filehandler.setLevel(logging.ERROR)
    elif verbose > 1: # Increased level to log file
        prompthandler.setLevel(logging.DEBUG)
        filehandler.setLevel(logging.INFO)

    logger.addHandler(prompthandler)
    logger.addHandler(filehandler)

    return logger


def rinexmod(rinexlist, outputfolder, teqcargs, name, single, sitelog, force, reconstruct, ignore, verbose):
    """
    Main function for reading a Rinex list file. It process the list, and apply
    file name modification, teqc args based header modification, or sitelog-based
    header modification.
    """

    # If sitelog option, no teqc argument must be provided
    if sitelog and teqcargs:
        print('# ERROR : If you get metadata from sitelog, don\'t provide arguments for teqc !')
        return

    # If force option provided, check if sitelog option too, if not, not relevant.
    if force and not sitelog:
        print('# WARNING : --force option is meaningful only when using also --sitelog option')

    # If ignore option provided, check if sitelog option too, if not, not relevant.
    if ignore and not sitelog:
        print('# WARNING : --ignore option is meaningful only when using also --sitelog option')

    # If inputfile doesn't exists, return
    if not os.path.isfile(rinexlist):
        print('# ERROR : The input file doesn\'t exist : ' + rinexlist)
        return

    outputfolder = os.path.abspath(outputfolder)

    if not os.path.isdir(outputfolder):
        # mkdirs ???
        os.mkdir(outputfolder)

    ########### Logging levels ###########

    # Creating log file
    dt = datetime.strftime(datetime.now(), '%Y%m%d%H%M%S')
    logfile = os.path.join(outputfolder, dt + '_' + 'rinexmod.log')

    logger = loggersVerbose(verbose, logfile)

    ####### Converting sitelog to dict ######

    if sitelog:
        # Creating sitelog object
        sitelogobj = Sitelog(sitelog)
        # If success,
        if not sitelogobj.info:
            print('# ERROR : The sitelog is not parsable : ' + sitelog)
            return

    ########### Looping into file list ###########

    # Opening and reading lines of the file containing list of rinex to proceed
    if single:
        rinexlist = [rinexlist]
    else:
        try:
            rinexlist = [line.strip() for line in open(rinexlist).readlines()]
        except:
            print('# ERROR : The input file is not a list : ' + rinexlist)
            return

    for file in rinexlist:

        logger.info('# File : ' + file)

        if not os.path.isfile(file):
            logger.error('01 - The specified file does not exists - ' + file)
            continue

        if os.path.abspath(os.path.dirname(file)) == outputfolder:
            logger.error('02 - Input and output folders are the same ! - ' + file)
            continue

        if reconstruct:
            if not reconstruct in file:
                logger.error('03 - The subfolder can not be reconstructed for file - ' + file)
                continue

            # We construct the output path with relative path between file name and parameter
            relpath = os.path.relpath(os.path.dirname(file), reconstruct)
            myoutputfolder = os.path.join(outputfolder, relpath)
            if not os.path.isdir(myoutputfolder):
                os.makedirs(myoutputfolder)
        else:
            myoutputfolder = outputfolder

        # Copying file to temporary folder
        success = copy(file, myoutputfolder)

        if not success:
            logger.error('04 - Copy of file to temp directory impossible - ' + file)
            continue

        tempfile = os.path.join(myoutputfolder, os.path.basename(file))
        workfile = tempfile

        if name:

            dirname, basename = os.path.split(workfile)
            newfile = os.path.join(dirname, name.lower() + basename[4:])

            success = move(workfile, newfile)

            if not success:
                logger.error('05 - Could not rename the file - ' + file)
                continue

            workfile = newfile
            logger.debug('File renamed : ' + workfile)

        if teqcargs or sitelog:

            convertedfile = None

            ##### Lauchning crz2rnx to extract Rinex file from archive #####
            logger.debug('Converting file to RNX')
            convertedfile = hatanaka.decompress_on_disk(workfile)
            workfile = convertedfile

            if not success:
                logger.error('06 - Invalid Compressed Rinex file - ' + file)
                if convertedfile:
                    for line in convertedfile.strip().split('\n'):
                        logger.error('Message - 06 - ' + line)
                    os.remove(workfile)
                continue

            if sitelog or verbose:
                metadata = teqcmeta(workfile)

            if verbose >= 1:
                logger.debug('File Metadata :\n' + metadata)

            if sitelog:

                # Parse teqc metadata output
                metadata = meta2dict(metadata)

                sitelog_sta_code = sitelogobj.info['1.']['Four Character ID'].lower()

                metadata_sta_codes = [metadata['station ID number'],
                                      metadata['station name']]

                if not any(sitelog_sta_code in metadata_code.lower() for metadata_code in metadata_sta_codes):
                    if force:
                        logger.error('10 - File\'s station does not correspond to provided sitelog, processing anyway - ' + file)
                    else:
                        logger.error('11 - File\'s station does not correspond to provided sitelog - use -f option to force ' + file)
                        os.remove(workfile)
                        continue

                # Get teqc args from sitelog infos and start and end time of the file
                # ignore option is to ignore firmware changes between instrumentation periods
                teqcargs, ignored = sitelogobj.teqcargs(metadata['start date & time'],
                                               metadata['final date & time'],
                                               ignore)

                if not teqcargs:
                    logger.error('12 - No instrumentation corresponding to the data period on the sitelog : ' + file)
                    os.remove(workfile)
                    continue

                if ignored:
                    logger.error('13 - Instrumentation cames from merged periods of sitelog with different firmwares, processing anyway - ' + file)

                teqcargs = ' '.join(teqcargs)

                logger.debug('Teqc args from sitelog : ' + teqcargs)

            stdoutdata = teqcmod(workfile, teqcargs)

            if stdoutdata:
                logger.error('07 - Could not execute teqc command. Args incorrects or file invalid - ' + file)
                for line in stdoutdata:
                    logger.error('Message - 07 - ' + line)
                os.remove(workfile)
                continue

            if verbose >= 1:
                metadata = teqcmeta(workfile)
                logger.debug('File Metadata :\n' + metadata)

            ##### We convert the file back to Hatanaka Compressed Rinex .crx or .XXd #####
            if workfile.endswith('.rnx') or re.match(r'\d{2}o', workfile[-3:]):

                logger.debug('Converting file to CRZ')
                crzfile = hatanaka.decompress_on_disk(workfile)

                if not success:
                    logger.error('08 - Invalid Rinex file - ' + file)
                    for line in crzfile.strip().split('\n'):
                        logger.error('Message - 08 - ' + line)
                    os.remove(workfile)
                    continue

                # Removing the rinex file
                os.remove(workfile)
                workfile = crzfile

    return


if __name__ == '__main__':

    import argparse

    # Parsing Args
    parser = argparse.ArgumentParser(description='Read a Sitelog file and create a CSV file output')
    parser.add_argument('rinexlist', type=str, help='Input rinex list file to process')
    parser.add_argument('outputfolder', type=str, help='Output folder for modified Rinex files')
    parser.add_argument('-t', '--teqcargs', help='Teqc modification command between double quotes (eg "-O.mn \'AGAL\' -O.rt \'LEICA GR25\'")', type=str, default=0)
    parser.add_argument('-n', '--name', help='Change 4 first letters of file name', type=str, default=0)
    parser.add_argument('-s', '--single', help='INPUT is a standalone Rinex file and not a file containing list of Rinex files paths', action='store_true')
    parser.add_argument('-l', '--sitelog', help='Get the Teqc args values from file\'s station\'s sitelog', type=str, default=0)
    parser.add_argument('-f', '--force', help='Force appliance of sitelog based teqc arguments when station name within file does not correspond to sitelog', action='store_true')
    parser.add_argument('-i', '--ignore', help='Ignore firmware changes between instrumentation periods when getting teqc args info from sitelogs', action='store_true')
    parser.add_argument('-r', '--reconstruct', help='Reconstruct files subdirectories. You have to indicate the part of the path that is common to all files and that will be replaced with output folder', type=str, default=0)
    parser.add_argument('-v', '--verbose', help='Increase output verbosity', action='count', default=0)

    args = parser.parse_args()

    rinexlist = args.rinexlist
    outputfolder = args.outputfolder
    teqcargs = args.teqcargs
    name=args.name
    single = args.single
    sitelog = args.sitelog
    force = args.force
    ignore = args.ignore
    reconstruct = args.reconstruct
    verbose = args.verbose

    rinexmod(rinexlist, outputfolder, teqcargs, name, single, sitelog, force, reconstruct, ignore, verbose)
