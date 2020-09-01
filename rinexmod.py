#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This script takes a list of RINEX Hanakata compressed files (.d.Z), extract the
rinex files and allows to pass to teqc parameters to modify headers, then put
them back to Hanakata Z format. It permits also to rename the files changing
the four first characters with another station code.

USAGE :

RINEXLIST : Rinex list file
OUTPUTFOLDER : Folder where to write the modified files. This is a compulsory
argument, you can not modify files inplace.

OPTIONS :
-t : teqcargs :     Teqc modification command between double quotes
                    (eg "-O.mn 'AGAL' -O.rt 'LEICA GR25'").
                    You can refer to teqc -help to see which arguments can be
                    passed to teqc. Here, the pertinent ones are mostly those
                    starting with O, that permits to modifiy rinex headers.
-n : name :         A four characater station code that will be used to rename
                    input files.
-s : single :       Option to provide if you want to run this script on a single
                    rinex file and not on a list of files.
-r : reconstruct :  Reconstruct files subdirectory. You have to indicate the
                    part of the path that is common to all files in the list and
                    that will be replaced with output folder.
-v : verbose:       Increase output verbosity. Will prompt teqc +meta of each
                    file before and after teqc modifications.

EXAMPLE:
./rinexmod.py  RINEXLIST OUTPUTFOLDER (-t "-O.mo 'Abri_du_Gallion' -O.mn 'AGAL' -O.o OVSG") (-n AGAL) (-s) (-r /ROOTFOLDER/) (-vv)

REQUIREMENTS :

You have to have RNX2CRZ and CRZ2RNX installed and declared in your path.
The program must be present on the machine, if not, available there :
http://terras.gsi.go.jp/ja/crx2rnx.html

You have to have teqc installed and declared in your path.
The program must be present on the machine, if not, available there :
https://www.unavco.org/software/data-processing/teqc/teqc.html#executables

2019-12-13 Félix Léger - leger@ipgp.fr
"""

import subprocess
import os, sys, re
from   datetime import datetime
import logging
from   shutil import copy, move


def crz2rnx(file):
    """
    Calling 'crz2rnx' program via subprocess to uncomrpess CRX files.
    The program must be present on the machine, if not, available there :
    http://terras.gsi.go.jp/ja/crx2rnx.html
    """

    if not file.endswith('crx.Z') and not file.endswith('d.Z'):
        success = False
        rnxfile = None
        return success, rnxfile

    # crx2rnx -f : force overwriting
    p = subprocess.Popen(['crz2rnx', '-f', file], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()

    if err:
        success = False
        rnxfile = None
    else:
        success = True
        if file.endswith('crx.Z'):
            rnxfile = file[:-5] + 'rnx'
        elif file.endswith('d.Z'):
            rnxfile = file[:-3] + 'o'

    return success, rnxfile


def rnx2crz(file):
    """
    Calling 'rnx2crx' program via subprocess to uncomrpess CRX files.
    The program must be present on the machine, if not, available there :
    http://terras.gsi.go.jp/ja/crx2rnx.html
    """
    # crx2rnx -f : force overwriting
    p = subprocess.Popen(['rnx2crz', '-f', file], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()

    if err:
        success = False
        crzfile = None
    else:
        success = True
        if file.endswith('rnx'):
            crzfile = file[:-3] + 'crx.Z'
        elif file.endswith('o'):
            crzfile = file[:-1] + 'd.Z'

    return success, crzfile


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


def teqcmod(file, teqcargs):
    """
    Calling UNAVCO 'teqc' program via subprocess and use the teqcargs variable to
    modifiy the Rinex file. Tipical use : header modification.
    The program must be present on the machine, if not, available there :
    https://www.unavco.org/software/data-processing/teqc/teqc.html#executables
    """
    tempfile = file + '_tmp'

    # Preparing the teqc command line
    args = ['teqc', '+out', tempfile, teqcargs, file]

    # Run the command
    stdoutdata = subprocess.getoutput(' '.join(args))

    # If teqc writes output message, error !
    if stdoutdata:
        return stdoutdata
    else:
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


def rinexmod(rinexlist, outputfolder, teqcargs, name, single, reconstruct, verbose):
    """
    Main function for reading a Rinex list file. It process the list,
    get metadata of the file, and push to the GSAC DB
    the metadata and file location informations.
    """

    # If inputfile doesn't exists, return
    if not os.path.isfile(rinexlist):
        print('# ERROR : : The input file doesn\'t exist : ' + rinexlist)
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

    ########### Looping into file list ###########

    # Opening and reading lines of the file containing list of rinex to proceed
    if single:
        rinexlist = [rinexlist]
    else:
        rinexlist = [line.strip() for line in open(rinexlist).readlines()]

    for file in rinexlist:

        logger.info('############ File : ' + file + ' ############')

        if not os.path.isfile(file):
            logger.error('01 - The specified file does not exists - ' + file)
            continue

        if os.path.abspath(os.path.dirname(file)) == outputfolder:
            logger.error('02 - Input and output folders are the same !')
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

        if teqcargs:

            convertedfile = None

            ##### Lauchning crz2rnx to extract Rinex file from archive #####
            logger.debug('Converting file to RNX')
            success, convertedfile = crz2rnx(workfile)
            workfile = convertedfile

            if not success:
                logger.error('06 - Invalid Compressed Rinex file - ' + file)
                continue

            if verbose >= 1:
                metadata = teqcmeta(workfile)
                logger.debug('\n' + metadata)

            stdoutdata = teqcmod(workfile, teqcargs)

            if stdoutdata:
                logger.error('07 - Could not execute teqc command. Check your args !')
                continue

            if verbose >= 1:
                metadata = teqcmeta(workfile)
                logger.debug('\n' + metadata)

            ##### We convert the file back to Hatanaka Compressed Rinex .crx or .XXd #####
            if workfile.endswith('.rnx') or re.match(r'\d{2}o', workfile[-3:]):

                logger.debug('Converting file to CRZ')
                success, crzfile = rnx2crz(workfile)

                if not success:
                    logger.error('08 - Invalid Rinex file - ' + file)
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
    parser.add_argument('-r', '--reconstruct', help='Reconstruct files subdirectory. You have to indicate the part of the path that is common to all files and that will be replaced with output folder', type=str, default=0)
    parser.add_argument('-v', '--verbose', help='Increase output verbosity', action='count', default=0)

    args = parser.parse_args()

    rinexlist = args.rinexlist
    outputfolder = args.outputfolder
    teqcargs = args.teqcargs
    name=args.name
    single = args.single
    reconstruct = args.reconstruct
    verbose = args.verbose

    rinexmod(rinexlist, outputfolder, teqcargs, name, single, reconstruct, verbose)
