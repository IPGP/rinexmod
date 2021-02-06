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
                       Antenna Type
                       Serial Number
                       Marker->ARP Up Ecc. (m)
                       Marker->ARP East Ecc(m)
                       Marker->ARP North Ecc(m)

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
./rinexmod.py  RINEXLIST OUTPUTFOLDER (-l ./sitelogsfolder/stationsitelog.log) (-n AGAL) (-s) (-r /ROOTFOLDER/) (-vv)

REQUIREMENTS :

You have to have RNX2CRZ and CRZ2RNX installed and declared in your path.
The program must be present on the machine, if not, available there :
http://terras.gsi.go.jp/ja/crx2rnx.html

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


def tryparsedate(date):
    # Different date format to test on the string in case of bad standard compliance
    formats = ['%Y-%m-%dT%H:%MZ', '%Y-%m-%d %H:%M', '%Y-%m-%dT%H:%M',
               '%Y/%m/%dT%H:%MZ', '%Y-%m-%d %H:%M', '%Y-%m-%dT%H:%M',
               '%d/%m/%YT%H:%MZ', '%d/%m/%Y %H:%M', '%d/%m/%YT%H:%M', '%Y-%m-%d %H:%M:%S.%f',
               '%Y-%m-%d',        '%Y/%m/%d',       '%d/%m/%Y'      ]
    if date:
        # Parse to date trying different formats
        for format in formats:
            try:
                date = datetime.strptime(date, format)
                break
            except:
                pass
    if not isinstance(date, datetime):
        # We set the date to 'infinity' date. If not a date, it's because it's an open border.
        date = datetime.strptime('9999-01-01', '%Y-%m-%d')

    return date


def sitelog2dict(sitelogfile):
    """
    Main function for reading a Sitelog file. From the sitelog file,
    returns a dict with all readed values.
    """

    ###### Input and output file tests #######

    # Checking if inexisting file
    if not os.path.isfile(sitelogfile):
        print('The provided Sitelog is not valid : ' + sitelogfile)
        return None

    # Getting filename and basename for output purposes
    filename = (os.path.splitext(os.path.basename(sitelogfile))[0])
    dirname = os.path.dirname(sitelogfile)

    ####### Reading Sitelog File #########

    # Reading the sitelog file
    try:
        with open(sitelogfile, "r", encoding="utf-8") as datafile:
            sitelog = datafile.read()
    except UnicodeDecodeError: # OVPF sitelogs are in iso-8859-1
        try:
            with open(sitelogfile, "r", encoding="iso-8859-1") as datafile:
                sitelog = datafile.read()
        except:
            raise

    # We delete all initial space.
    pattern = re.compile(r'\n +')
    sitelog = re.sub(pattern, r'\n', sitelog)

    # We rearrange multiline content to be complient with .ini format.
    pattern = re.compile(r'(\n *): *')
    sitelog = re.sub(pattern, ' ', sitelog)

    # We transform  multiple contacts into sub blocs
    pattern = re.compile(r'((?:Secondary|Primary) [Cc]ontact):{0,1}')
    sitelog = re.sub(pattern, r'[\1]', sitelog)

    # We remove the final graphic if exists
    antennagraphic = re.search(r'Antenna Graphics with Dimensions', sitelog)
    if antennagraphic:
        sitelog = sitelog[:antennagraphic.start(0)]

    # List of formated blocs
    formatedblocs = []
    # Final dict to store values
    sitelogdict = {}

    # We split the file into major blocs (reading the '4.'' type pattern)
    iter = re.finditer(r'\d{1,2}\. +.+\n', sitelog)
    indices = [m.start(0) for m in iter]

    blocs = [sitelog[i:j] for i,j in zip(indices, indices[1:]+[None])]

    if len(blocs) == 0:
        print('The provided Sitelog is not correct : ' + sitelogfile)
        return None

    # We loop into those blocs, after a test that permits keeping only blocs
    # beggining with patterns like '6.'. This permits removing the title bloc.
    for bloc in [bloc for bloc in blocs if re.match(r'\d.', bloc[:2])]:

        # We search for '4.3', '4.3.', '4.2.3' patterns for subbloc detection
        iter = re.finditer(r'\n\d{1,2}\.\d{0,2}\.{0,1}\w{0,2}\.{0,1}', bloc)
        indices = [m.start(0) +1 for m in iter]

        if len(indices) > 0: # If subblocs
            subblocs = [bloc[i:j] for i,j in zip(indices, indices[1:]+[None])]

            for subbloc in subblocs:
                # We separate index (the first line) from values
                index, subbloc = subbloc.split('\n', 1)
                # If available, the data contained in the first line (now stored in index)
                # is pushed back in the subbloc varaible in a new 'type' entry.
                try:
                    index, title = index.split(' ', 1)
                    if ':' not in title:
                        title = 'type : ' + title
                    subbloc = title.lstrip() + '\n' + subbloc
                except :
                    pass
                # We append the subbloc to the list of blocs to read
                formatedblocs.append([index, subbloc])

        elif re.search(r'\n', bloc):
            # Get index and bloc content
            index, bloc = bloc.split('\n', 1)
            index = re.match(r'\d{1,2}\.', index).group(0)

            # We append it to the list of blocs to read
            formatedblocs.append([index, bloc])

        else:
            pass

    # Now that blocs are formated, we read them with configparser
    for [index, bloc] in formatedblocs:

        if 'x' in index[0:5]:
            pass # If it's a model section (like 3.x), we don't proceed it
        else:
            # We add a section header to work on it with ConfigParser
            bloc = '[dummy_section]\n' + bloc

            cfgparser = configparser.RawConfigParser(allow_no_value=True)
            cfgparser.optionxform = str # Respect case
            cfgparser.read_string(bloc)

            # We construct the bloc dict
            blocdict = {}
            for section_name in cfgparser.sections():
                # For 'dummy_section' section, we quit the section_name
                if section_name == 'dummy_section':
                    blocdict.update(dict(cfgparser[section_name]))
                # For other sections (Primary & Secondary contact, added earlier), we keep the section_name
                else:
                    blocdict.update({section_name: dict(cfgparser[section_name])})

            # We append the bloc dict to the global dict
            sitelogdict[index] = blocdict

    # Contact corrections - putting the field 'Additional Information' in the right level dict
    # and removing network information
    for key in [key for key in sitelogdict.keys() if key in ['11.' ,'12.']]:
        if 'network' in sitelogdict[key]['Agency'].lower():
            index_network =  sitelogdict[key]['Agency'].lower().index('network')
            sitelogdict[key]['Agency'] = sitelogdict[key]['Agency'][:index_network]
        # Removing extra spaces
        sitelogdict[key]['Agency'] = sitelogdict[key]['Agency'].strip()
        sitelogdict[key]['Agency'] = " ".join(sitelogdict[key]['Agency'].split())
        if sitelogdict[key]['Secondary Contact']['Additional Information']:
            # Putting the 'Additional Information' in the lower level dict
            sitelogdict[key]['Additional Information'] = sitelogdict[key]['Secondary Contact']['Additional Information']
            # Removing it from the incorrect dict level
            sitelogdict[key]['Secondary Contact'].pop('Additional Information', None)

    return sitelogdict


def get_instrumentation(sitelogdict, starttime, endtime):
    """
    This function identifies the different complete installations from the antenna
    and receiver change dates, and then construct a CSV, GSAC complient line for each of
    those installations. It then write this line to new file or append it to exisitng one.
    """

    ##### Constructing a list of date intervals from all changes dates #####

    listdates = []

    # We extract dates for blocs 3. and 4. (reveiver, antenna)
    for key in [key for key in sitelogdict.keys() if key.startswith('3.') or key.startswith('4.')]:
        # Formating parsed dates - set empty to 'infinity' date. If not a date, it's because it's an open border.
        sitelogdict[key]['Date Installed'] = tryparsedate(sitelogdict[key]['Date Installed'])
        sitelogdict[key]['Date Removed'] = tryparsedate(sitelogdict[key]['Date Removed'])
        # Adding dates to listdate
        listdates += sitelogdict[key]['Date Installed'], sitelogdict[key]['Date Removed']

    # # We extract dates from blocs 8 (meteo). If found and parsable, we add them to the list.
    # for key in [key for key in sitelogdict.keys() if key.startswith('8.')]:
    #     dates = re.findall(r'\d{4}-\d{1,2}-\d{1,2}', sitelogdict[key]['Effective Dates'])
    #     if len(dates) == 2:
    #         metpackstartdate = tryparsedate(dates[0])
    #         metpackenddate = tryparsedate(dates[1])
    #         listdates += metpackstartdate, metpackenddate
    #     elif len(dates) == 1:
    #         metpackstartdate = tryparsedate(dates[0])
    #         metpackenddate = tryparsedate(None) # Infinity date
    #         listdates += metpackstartdate, metpackenddate
    #     else:
    #         pass

    # Quitting null values
    listdates = [date for date in listdates if date]
    # Quitting duplicates
    listdates = list(set(listdates))
    # Sorting
    listdates.sort()

    # List of installations. An installation is a date interval, a receiver and an antena
    installations = []

    # Constructiong the installations list - date intervals
    for i in range(0, len(listdates) - 1):
        # Construct interval from listdates
        dates = [listdates[i], listdates[i+1]]
        # Setting date interval in Dict of installation
        installation = dict(dates = dates, receiver = None, antenna = None, metpack = None)
        # Append it to list of installations
        installations.append(installation)

    ##### Getting Receiver info for each interval #####

    receivers = [sitelogdict[key] for key in sitelogdict.keys() if key.startswith('3.')]

    # Constructiong the installations list - Receivers
    for installation in installations:
        # We get the receiver corresponding to the date interval
        for receiver in receivers:
            if (receiver['Date Installed']  <= installation['dates'][0]) and \
               (receiver['Date Removed'] >= installation['dates'][1]) :
                installation['receiver'] = receiver
                # Once found, we quit the loop
                break

    ##### Getting Antena info for each interval #####

    antennas = [sitelogdict[key] for key in sitelogdict.keys() if key.startswith('4.')]

    # Constructiong the installations list - Antennas
    for installation in installations:
        # We get the antenna corresponding to the date interval
        for antenna in antennas:
            if (antenna['Date Installed']  <= installation['dates'][0]) and \
               (antenna['Date Removed'] >= installation['dates'][1]) :
                installation['antenna'] = antenna
                # Once found, we quit the loop
                break

    ##### Removing from installation list periods without antenna or receiver #####

    installations = [i for i in installations if i['receiver'] and i['antenna']]

    # We get the installation corresponding to the starttime and endtime

    thisinstall = None

    for installation in installations:
        if installation['dates'][0] < starttime and installation['dates'][1] > endtime:
            thisinstall = installation
            break

    if not thisinstall:
        print('y\'a R')
        return None

    else:

        # print(sitelogdict['1.']['Four Character ID'])
        # print(sitelogdict['2.']['X coordinate (m)'])
        # print(sitelogdict['2.']['Y coordinate (m)'])
        # print(sitelogdict['2.']['Z coordinate (m)'])
        # print(thisinstall['receiver']['Receiver Type'])
        # print(thisinstall['receiver']['Serial Number'])
        # print(thisinstall['receiver']['Firmware Version'])
        # print(thisinstall['antenna']['Antenna Type'])
        # print(thisinstall['antenna']['Serial Number'])
        # print(thisinstall['antenna']['Marker->ARP Up Ecc. (m)'])
        # print(thisinstall['antenna']['Marker->ARP East Ecc(m)'])
        # print(thisinstall['antenna']['Marker->ARP North Ecc(m)'])

        # We construct the TEQC args line

        # -M.mo[nument] ? XXXXXX

        teqcargs = "-O.mo[nument] '{}' -M.mo[nument] '{}' -O.px[WGS84xyz,m] {} {} {} -O.s[ystem] {}"
        teqcargs += " -O.rt '{}' -O.rn '{}' -O.rv '{}'"
        teqcargs += " -O.at '{}' -O.an '{}' -O.pe[hEN,m] {} {} {}"

        # XXXXXXX #
        o_system = 'M'

        teqcargs = teqcargs.format(sitelogdict['1.']['Four Character ID'],
                                  sitelogdict['1.']['Four Character ID'],
                                  sitelogdict['2.']['X coordinate (m)'],
                                  sitelogdict['2.']['Y coordinate (m)'],
                                  sitelogdict['2.']['Z coordinate (m)'],
                                  o_system,
                                  thisinstall['receiver']['Receiver Type'],
                                  thisinstall['receiver']['Serial Number'],
                                  thisinstall['receiver']['Firmware Version'],
                                  thisinstall['antenna']['Antenna Type'],
                                  thisinstall['antenna']['Serial Number'],
                                  thisinstall['antenna']['Marker->ARP Up Ecc. (m)'].zfill(8),
                                  thisinstall['antenna']['Marker->ARP East Ecc(m)'].zfill(8),
                                  thisinstall['antenna']['Marker->ARP North Ecc(m)'].zfill(8)
                                  )

    return teqcargs


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


def rinexmod(rinexlist, outputfolder, teqcargs, name, single, sitelog, reconstruct, verbose):
    """
    Main function for reading a Rinex list file. It process the list,
    get metadata of the file, and push to the GSAC DB
    the metadata and file location informations.
    """

    # If sitelog option, no teqc argument must be provided
    if sitelog and teqcargs:
        print('# ERROR : If you get metadata from sitelog, don\'t provide arguments for teqc !')
        return

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
        # Converting sitelog file to json dict
        sitelogdict = sitelog2dict(sitelog)
        # If success,
        if not sitelogdict:
            print('# ERROR : The sitelog is not parsable : ' + sitelog)
            return

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
            success, convertedfile = crz2rnx(workfile)
            workfile = convertedfile

            if not success:
                logger.error('06 - Invalid Compressed Rinex file - ' + file)
                continue

            if sitelog or verbose:
                metadata = teqcmeta(workfile)

            if verbose >= 1:
                logger.debug('File Metadata :\n' + metadata)

            if sitelog:

                # Parse teqc metadata output
                metadata = meta2dict(metadata)

                # Check that sitelog corresponds to file's station
                if sitelogdict['1.']['Four Character ID'].lower() != metadata['station ID number'].lower():
                    logger.error('10 - File\'s station does not correspond to provided sitelog - ' + file)
                    continue

                # Get teqc args from sitelog infos and start and end time of the file
                teqcargs = get_instrumentation(sitelogdict, metadata['start date & time'],
                                                            metadata['final date & time'])

                if not teqcargs:
                    logger.error('11 - No instrumentation corresponding to the data period on the sitelog : ' + file)
                    continue

                logger.debug('Teqc args from sitelog : ' + teqcargs)

            stdoutdata = teqcmod(workfile, teqcargs)

            if stdoutdata:
                logger.error('07 - Could not execute teqc command. Args incorrects or file invalid - ' + file)
                continue

            if verbose >= 1:
                metadata = teqcmeta(workfile)
                logger.debug('File Metadata :\n' + metadata)

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
    parser.add_argument('-l', '--sitelog', help='Get the Teqc args values from file\'s station\'s sitelog', type=str, default=0)
    parser.add_argument('-r', '--reconstruct', help='Reconstruct files subdirectories. You have to indicate the part of the path that is common to all files and that will be replaced with output folder', type=str, default=0)
    parser.add_argument('-v', '--verbose', help='Increase output verbosity', action='count', default=0)

    args = parser.parse_args()

    rinexlist = args.rinexlist
    outputfolder = args.outputfolder
    teqcargs = args.teqcargs
    name=args.name
    single = args.single
    sitelog = args.sitelog
    reconstruct = args.reconstruct
    verbose = args.verbose

    rinexmod(rinexlist, outputfolder, teqcargs, name, single, sitelog, reconstruct, verbose)
