#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This script takes a list of RINEX Hanakata compressed files (.d.Z or .d.gz or .rnx.gz),
loop the RINEX files list to modifiy the file's header. It then write them back to Hanakata
compressed format in an output folder. It permits also to rename the files changing
the four first characters of the file name with another site code. It can write
those files with the long name naming convention with the --longname option.

Two ways of passing parameters to modifiy headers are possible:

--modification_kw : you pass as argument the field(s) that you want to modifiy and its value.
                      Acceptable_keywords are : marker_name, marker_number, 
                      site (legacy alias for marker_name), receiver_serial,
                      receiver_type, receiver_fw, antenna_serial, antenna_type,
                      antenna_X_pos, antenna_Y_pos, antenna_Z_pos,
                      antenna_H_delta, antenna_E_delta, antenna_N_delta,
                      operator, agency, observables, interval, 
                      filename_file_period, filename_data_freq

--sitelog  : you pass sitelogs file. The argument must be a sitelog path or the path of a folder
               containing sitelogs. You then have to pass a list of files and the script will
               assign sitelogs to correspondig files, based on the file's name.
               The script will take the start and end time of each proceeded file
               and use them to extract from the sitelog the site instrumentation
               of the corresponding period and fill file's header with following infos :
                       Four Character ID
                       X coordinate (m)
                       Y coordinate (m)
                       Z coordinate (m)
                       Receiver Type
                       Serial Number
                       Firmware Version
                       Satellite System (will translate this info to one-letter code, see RinexFile.set_sat_system())
                       Antenna Type
                       Serial Number
                       Marker->ARP Up Ecc. (m)
                       Marker->ARP East Ecc(m)
                       Marker->ARP North Ecc(m)
                       On-Site Agency Preferred Abbreviation
                       Responsible Agency Preferred Abbreviation

You can not provide both --modification_kw and --sitelog options.

The script will add two comment lines, one indicating the source of the modifiaction
(sitelog or arguments) and the other the timestamp of the modification.

USE :

RINEXLIST : Input list file of the RINEX files to process
generated with a find or ls command for instance.
OUTPUTFOLDER : Folder where to write the modified RINEX files. 
This is a compulsory argument, you can not modify files inplace.

OPTIONS :

-s : --sitelog :            Sitelog file in witch rinexmod will find file's period's
                            instrumentation informations, or folder containing sitelogs.
-k : --modification_kw :    Header fields that you want to modify.
                            Will override the information from the sitelog.
                            The sitelogs must be valid as the script does not check it.
-f : --force :              Force sitelog-based header values when RINEX's header
                            and sitelog's site name do not correspond.
-i : --ignore :             Ignore firmware changes between instrumentation periods
                            when getting headers args info from sitelogs.
-m : --marker :             A four or nine character site code that will be used to rename
                            input files.
                            (does not apply to the header\'s MARKER NAME, 
                             use -k marker_name='<MARKER>' for this)
-n : --ninecharfile :       path a of a list file containing 9-char. site names from
                            the M3G database generated with get_m3g_stations.
                            This will be used for longname file's renaming.
                            Not mandatory, but nessessary to get the country code to rename
                            files to long name standard. If not provided the country code will be XXX.
-l : --longname :           Rename file using long name RINEX convention (force gzip compression).
-a : --alone :              Option to provide if you want to run this script on a alone
                            RINEX file and not on a list of files.
-c : --compression :        Set file's compression. Acceptables values : 'gz' (recommended
                            to fit IGS standards), 'Z' or 'none'. Default value will retrieve
                            the actual compression of the input file.
-r : --relative :           Reconstruct files relative subfolders.
                            You have to indicate the common parent folder,
                            that will be replaced with the output folder
-o : --output_logs :        Folder where to write output log. If not provided, logs
                            will be written to OUTPUTFOLDER.
-w : --write :              Write (RINEX version, sample rate, file period, observatory)
                            dependant output lists to log folder.
-v : --verbose:             Will print file's metadata before and after modifications.
-t : --sort:                Sort the input RINEX list.

EXAMPLES:

./rinexmod.py RINEXLIST OUTPUTFOLDER (-k antenna_type='ANT TYPE' antenna_X_pos=9999 agency=AGN) (-m AGAL) (-r ./ROOTFOLDER/) (-f) (-v)
./rinexmod.py (-a) RINEXFILE OUTPUTFOLDER (-s ./sitelogsfolder/stationsitelog.log) (-i) (-w) (-o ./LOGFOLDER) (-v)

REQUIREMENTS :

You need Python Hatanaka library from Martin Valgur:

pip install hatanaka

2021-02-07 Félix Léger - leger@ipgp.fr
"""

import os
import re
from datetime import datetime
import logging
from sitelogs_IGS import SiteLog
from rinexfile import RinexFile
import hatanaka
import subprocess


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

    promptformatter = logging.Formatter(
        '%(asctime)s - %(levelname)-7s - %(message)s')
    fileformatter = logging.Formatter(
        '%(asctime)s - %(levelname)-7s - %(message)s')

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
    return list(sorted(liste))

# get Git hash (to get a version number-equivalent of the RinexMod used)


def get_git_revision_short_hash():
    script_path = os.path.dirname(os.path.realpath(__file__))
    cmd = ['git', '--git-dir', script_path +
           '/.git', 'rev-parse', '--short', 'HEAD']
    try:
        return subprocess.check_output(cmd).decode('ascii').strip()[:7]
    except:
        return "xxxxxxx"


def rinexmod(rinexlist, outputfolder, marker, longname, alone, sitelog, force,
             relative, ignore, ninecharfile, modification_kw, verbose,
             compression, output_logs, write,  sort):
    """
    Main function for reading a Rinex list file. It process the list, and apply
    file name modification, command line based header modification, or sitelog-based
    header modification.
    """

    # If no longname, modification_kw and sitelog, return
    if not sitelog and not modification_kw and not marker and not longname:
        print('# ERROR : No action asked, provide at least one of the following args : --sitelog, --modification_kw, --marker, --longname.')
        return

    # If force option provided, check if sitelog option too, if not, not relevant.
    if force and not sitelog:
        print('# ERROR : --force option is meaningful only when --sitelog option with a **single** sitelog is also provided')
        return

    # If ignore option provided, check if sitelog option too, if not, not relevant.
    if ignore and not sitelog:
        print(
            '# ERROR : --ignore option is meaningful only when using also --sitelog option')
        return

    if ninecharfile and not longname:
        print('# ERROR : --ninecharfile option is meaningful only when using also --longname option')
        return

    # If inputfile doesn't exists, return
    if isinstance(rinexlist, list):
        pass
    elif not os.path.isfile(rinexlist):
        print('# ERROR : The input file doesn\'t exist : ' + rinexlist)
        return

    if output_logs and not os.path.isdir(output_logs):
        print(
            '# ERROR : The specified output folder for logs doesn\'t exist : ' + output_logs)
        return

    outputfolder = os.path.abspath(outputfolder)

    if not os.path.isdir(outputfolder):
        # mkdirs ???
        os.makedirs(outputfolder)

    ########### Logging levels ###########

    # Creating log file
    now = datetime.now()
    dt = datetime.strftime(now, '%Y%m%d%H%M%S')

    if output_logs:
        logfolder = output_logs
    else:
        logfolder = outputfolder

    logfile = os.path.join(logfolder, dt + '_' + 'rinexmod_errors.log')

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
                print('# ERROR : --force option is meaningful only when providing a single sitelog (and not a folder contaning several sitelogs)')
                return

            sitelog_extension = '.log'
            all_sitelogs = listfiles(sitelog, sitelog_extension)

            sitelog_pattern = re.compile('\w{3,9}_\d{8}.log')
            all_sitelogs = [file for file in all_sitelogs if sitelog_pattern.match(
                os.path.basename(file))]

            if verbose:
                logger.info('**** All sitelogs detected:')
                for sl in all_sitelogs:
                    logger.info(sl)

            # Get last version of sitelogs if multiple available
            sitelogs = []
            # We list the available sites to group sitelogs
            sitelogsta = [os.path.basename(sitelog)[0:4]
                          for sitelog in all_sitelogs]

            for sta in sitelogsta:
                # Grouping by site
                sta_sitelogs = [sitelog for sitelog in all_sitelogs if os.path.basename(sitelog)[
                    0:4] == sta]
                # Getting dates from basename
                sitelogs_dates = [os.path.splitext(os.path.basename(sitelog))[
                    0][-8:] for sitelog in sta_sitelogs]
                # Parsing 'em
                sitelogs_dates = [datetime.strptime(
                    sitelogs_date, '%Y%m%d') for sitelogs_date in sitelogs_dates]
                # We get the max date and put it back to string format.
                maxdate = max(sitelogs_dates).strftime('%Y%m%d')
                # We filter the list with the max date string, and get a one entry list, then transform it to string
                sta_sitelog = [sitelog for sitelog in sta_sitelogs if maxdate in os.path.splitext(
                    os.path.basename(sitelog))[0][-8:]][0]
                # Creating sitelog object
                sitelogobj = SiteLog(sta_sitelog)

                # If sitelog is not parsable
                if sitelogobj.status != 0:
                    print('# ERROR : The sitelog is not parsable : ' +
                          sitelogobj.path)
                    return

                # Appending to list
                sitelogs.append(sitelogobj)

            if verbose:
                logger.info('**** Most recent sitelogs selected:')
                for sl in sitelogs:
                    logger.info(sl.path)

    ####### Checking input keyword modification arguments ######

    if modification_kw:

        acceptable_keywords = ['station',
                               'marker_name',
                               'marker_number',
                               'receiver_serial',
                               'receiver_type',
                               'receiver_fw',
                               'antenna_serial',
                               'antenna_type',
                               'antenna_X_pos',
                               'antenna_Y_pos',
                               'antenna_Z_pos',
                               'antenna_H_delta',
                               'antenna_E_delta',
                               'antenna_N_delta',
                               'operator',
                               'agency',
                               'observables',
                               'interval',
                               'filename_data_freq',
                               'filename_file_period']

        for kw in modification_kw:
            if kw not in acceptable_keywords:
                print(
                    '# ERROR : \'{}\' is not an acceptable keyword for header modification.'.format(kw))
                return

    # Opening and reading lines of the file containing list of rinex to proceed
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

    # Get the 4 char > 9 char dictionnary from the input list
    nine_char_dict = dict()  # in any case, nine_char_dict is initialized
    if ninecharfile:
        if not os.path.isfile(ninecharfile):
            print(
                '# ERROR : The specified 9-chars. list file does not exists : ' + ninecharfile)
            return
        with open(ninecharfile, "r") as F:
            nine_char_list = F.readlines()

        for site_key in nine_char_list:
            nine_char_dict[site_key[:4].lower()] = site_key.strip()

    # Check that the provided marker is a 4-char site name
    if marker and (len(marker) != 4 and len(marker) != 9):
        print('# ERROR : The site name provided is not 4 or 9-char valid : ' + marker)
        return

    # sort the RINEX list
    if sort:
        rinexlist.sort()

    ### Looping in file list ###
    return_lists = {}

    for file in rinexlist:

        logger.info('# File : ' + file)

        if relative:
            if not relative in file:
                logger.error(
                    '{:110s} - {}'.format('31 - The relative subfolder can not be reconstructed for file', file))
                continue

            # We construct the output path with relative path between file name and parameter
            relpath = os.path.relpath(os.path.dirname(file), relative)
            myoutputfolder = os.path.join(outputfolder, relpath)
            if not os.path.isdir(myoutputfolder):
                os.makedirs(myoutputfolder)
        else:
            myoutputfolder = outputfolder

        if os.path.abspath(os.path.dirname(file)) == myoutputfolder:
            logger.error(
                '{:110s} - {}'.format('30 - Input and output folders are the same !', file))
            continue

        # Declare the rinex file as an object
        rinexfileobj = RinexFile(file)

        if rinexfileobj.status == 1:
            logger.error(
                '{:110s} - {}'.format('01 - The specified file does not exists', file))
            continue

        if rinexfileobj.status == 2:
            logger.error(
                '{:110s} - {}'.format('02 - Not an observation Rinex file', file))
            continue

        if rinexfileobj.status == 3:
            logger.error(
                '{:110s} - {}'.format('03 - Invalid or empty Zip file', file))
            continue

        if rinexfileobj.status == 4:
            logger.error(
                '{:110s} - {}'.format('04 - Invalid Compressed Rinex file', file))
            continue

        if rinexfileobj.status == 5:
            logger.error(
                '{:110s} - {}'.format('05 - Less than two epochs in the file', file))
            continue

        if marker:
            # We store the old site name to add a comment in rinex file's header
            modification_source = rinexfileobj.filename[:4]
            rinexfileobj.set_filename_site(marker)

        if longname:
            # We rename the file to the rinex long name convention
            # Get the site 9-char name
            if not ninecharfile or not rinexfileobj.get_site_from_filename('lower', True) in nine_char_dict:
                logger.warning('{:110s} - {}'.format(
                    '32 - Site\'s country not retrevied, will not be properly renamed', file))
                monum_country = "00XXX"
            else:
                monum_country = nine_char_dict[rinexfileobj.get_site_from_filename(
                    'lower', True)].upper()[4:]
                 

            # NB: the longfilename will be generated later 
            # (The block "we regenerate the filenames")

        if sitelog:
            # Site name from the rinex's header line
            site_meta = rinexfileobj.get_site_from_filename('lower',
                                                            only_4char=True)
            if verbose:
                logger.info(
                    'Searching corresponding sitelog for site : ' + site_meta)

            # Finding the right sitelog. If is list, can not use force. If no sitelog found, do not process.
            if site_meta not in [sitelog.site4char for sitelog in sitelogs]:
                if len(sitelogs) == 1:
                    if not force:
                        logger.error('{:110s} - {}'.format(
                            '33 - Filename\'s site does not correspond to provided sitelog - use -f option to force', file))
                        continue
                    else:
                        logger.warning('{:110s} - {}'.format(
                            '34 - Filename\'s site does not correspond to provided sitelog, processing anyway', file))
                else:
                    logger.error(
                        '{:110s} - {}'.format('33 - No provided sitelog for this file\'s site', file))
                    continue
            else:
                sitelogobj = [
                    sitelog for sitelog in sitelogs if sitelog.site4char == site_meta][0]

            modification_source = sitelogobj.filename

            # Site name from the sitelog
            sitelog_site_code = sitelogobj.info['1.']['Four Character ID'].lower()

            # Get rinex header values from sitelog infos and start and end time of the file
            # ignore option is to ignore firmware changes between instrumentation periods.
            metadata_vars, ignored = sitelogobj.rinex_metadata_lines(
                rinexfileobj.start_date, rinexfileobj.end_date, ignore)

            if not metadata_vars:
                logger.error('{:110s} - {}'.format(
                    '35 - No instrumentation corresponding to the data period on the sitelog', file))
                continue

            if ignored:
                logger.warning('{:110s} - {}'.format(
                    '36 - Instrumentation cames from merged periods of sitelog with different firmwares, processing anyway', file))

            (fourchar_id, domes_id, observable_type, agencies, receiver,
             antenna, antenna_pos, antenna_delta) = metadata_vars

            if verbose:
                logger.info('File Metadata :\n' +
                            rinexfileobj.get_metadata()[0])

            # # Apply the modifications to the RinexFile object
            rinexfileobj.set_marker(fourchar_id, domes_id)
            rinexfileobj.set_receiver(**receiver)
            rinexfileobj.set_interval(rinexfileobj.sample_rate_numeric)
            rinexfileobj.set_antenna(**antenna)
            rinexfileobj.set_antenna_pos(**antenna_pos)
            rinexfileobj.set_antenna_delta(**antenna_delta)
            rinexfileobj.set_agencies(**agencies)
            rinexfileobj.set_sat_system(observable_type)

        if modification_kw:

            if verbose:
                logger.info('File Metadata :\n' +
                            rinexfileobj.get_metadata()[0])

            modification_source = 'command line'

            rinexfileobj.set_marker(modification_kw.get('marker_name'),
                                    modification_kw.get('marker_number'))

            # legacy keyword, 'marker_name' should be used instead
            rinexfileobj.set_marker(modification_kw.get('station'))

            rinexfileobj.set_receiver(modification_kw.get('receiver_serial'),
                                      modification_kw.get('receiver_type'),
                                      modification_kw.get('receiver_fw'))

            rinexfileobj.set_antenna(modification_kw.get('antenna_serial'),
                                     modification_kw.get('antenna_type'))

            rinexfileobj.set_antenna_pos(modification_kw.get('antenna_X_pos'),
                                         modification_kw.get('antenna_Y_pos'),
                                         modification_kw.get('antenna_Z_pos'))

            rinexfileobj.set_antenna_delta(modification_kw.get('antenna_H_delta'),
                                           modification_kw.get(
                                               'antenna_E_delta'),
                                           modification_kw.get('antenna_N_delta'))

            rinexfileobj.set_agencies(modification_kw.get('operator'),
                                      modification_kw.get('agency'))

            rinexfileobj.set_sat_system(modification_kw.get('observables'))

            rinexfileobj.set_interval(modification_kw.get('interval'))

            # for the filename
            rinexfileobj.set_filename_file_period(
                modification_kw.get('filename_file_period'))
            rinexfileobj.set_filename_data_freq(
                modification_kw.get('filename_data_freq'))

        if verbose:
            logger.info('File Metadata :\n' + rinexfileobj.get_metadata()[0])

        # Adding comment in the header
        vers_num = get_git_revision_short_hash()
        #rinexfileobj.add_comment(("RinexMod (IPGP)","METADATA UPDATE"),add_pgm_cmt=True)
        rinexfileobj.add_comment(
            ("RinexMod "+vers_num, "METADATA UPDATE"), add_pgm_cmt=True)
        rinexfileobj.add_comment('rinexmoded on {}'.format(
            datetime.strftime(now, '%Y-%m-%d %H:%M')))
        if sitelog or modification_kw:
            rinexfileobj.add_comment(
                'rinexmoded from {}'.format(modification_source))
        if marker:
            rinexfileobj.add_comment(
                'file assigned from {}'.format(modification_source))

        #### we regenerate the filenames
        if rinexfileobj.name_conv == "SHORT" and not longname:
            rinexfileobj.get_shortname(inplace=True, compression='')
        else:
            rinexfileobj.get_longname(monum_country,inplace=True, compression='')

        # NB: here the compression type must be forced to ''
        #     it will be added in the next step 
        # (in the block "We convert the file back to Hatanaka Compressed Rinex")
        # inplace = True => rinexfileobj's filename is updated

        #### We convert the file back to Hatanaka Compressed Rinex 
        if longname and not compression:
            # If not specified, we set compression to gz when file changed to longname
            output_compression = 'gz'
        elif not compression:
            output_compression = rinexfileobj.compression
        else:
            output_compression = compression

        # Writing output file
        try:
            outputfile = rinexfileobj.write_to_path(
                myoutputfolder, compression=output_compression)
        except hatanaka.hatanaka.HatanakaException:
            logger.error(
                '{:110s} - {}'.format('06 - File could not be written - hatanaka exception', file))
            continue

        logger.info('Output file : ' + outputfile)

        ### Construct return dict by adding key if doesn't exists and appending file to corresponding list ###
        major_rinex_version = rinexfileobj.version[0]
        # Dict ordered as : RINEX_VERSION, SAMPLE_RATE, FILE_PERIOD
        if major_rinex_version not in return_lists:
            return_lists[major_rinex_version] = {}
        if rinexfileobj.sample_rate_string not in return_lists[major_rinex_version]:
            return_lists[major_rinex_version][rinexfileobj.sample_rate_string] = {}
        if rinexfileobj.file_period not in return_lists[major_rinex_version][rinexfileobj.sample_rate_string]:
            return_lists[major_rinex_version][rinexfileobj.sample_rate_string][rinexfileobj.file_period] = []

        return_lists[major_rinex_version][rinexfileobj.sample_rate_string][rinexfileobj.file_period].append(
            outputfile)

    logger.handlers.clear()

    if write:
        # Writing an output file for each RINEX_VERSION, SAMPLE_RATE, FILE_PERIOD lists
        for rinex_version in return_lists:
            for sample_rate in return_lists[rinex_version]:
                for file_period in return_lists[rinex_version][sample_rate]:

                    this_outputfile = '_'.join(
                        ['RINEX' + rinex_version, sample_rate, file_period, datetime.strftime(now, '%Y%m%d%H%M'), 'delivery.lst'])
                    this_outputfile = os.path.join(logfolder, this_outputfile)

                    # Writting output to temporary file and copying it them to target files
                    with open(this_outputfile, 'w') as f:
                        f.writelines('{}\n'.format(
                            line) for line in return_lists[rinex_version][sample_rate][file_period])
                        print('# Output rinex list written to ' + this_outputfile)

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
    parser = argparse.ArgumentParser(
        description='Read a Sitelog file and create a CSV file output')
    parser.add_argument('rinexlist', type=str,
                        help='Input list file of the RINEX paths to process (see also -a/--alone for a single input file)')
    parser.add_argument('outputfolder', type=str,
                        help='Output folder for modified RINEX files')
    parser.add_argument(
        '-s', '--sitelog', help='Get the RINEX header values from file\'s site\'s sitelog. Provide a single sitelog path or a folder contaning sitelogs.', type=str, default="")
    parser.add_argument('-k', '--modification_kw', help='''Modification keywords for RINEX's header and/or filename. Will override the information from the sitelog. 
                                                           Format : keyword_1=\'value\' keyword2=\'value\'. Acceptable keywords:\n
                                                           marker_name, marker_number, station (legacy alias for marker_name), receiver_serial, receiver_type, receiver_fw, antenna_serial, antenna_type,
                                                           antenna_X_pos, antenna_Y_pos, antenna_Z_pos, antenna_H_delta, antenna_E_delta, antenna_N_delta,
                                                           operator, agency, observables, interval, filename_file_period (01H, 01D...), filename_data_freq (30S, 01S...)''', nargs='*', action=ParseKwargs, default=None)
    parser.add_argument('-m', '--marker', help="Change 4 or 9 first letters of file\'s name to set it to another site (does not apply to the header\'s MARKER NAME, use -k marker_name='XXXX' for this)", type=str, default='')
    parser.add_argument('-n', '--ninecharfile',
                        help='Path of a file that contains 9-char. site names from the M3G database', type=str, default="")
    parser.add_argument('-r', '--relative', help='Reconstruct files relative subfolders. You have to indicate the common parent folder, that will be replaced with the output folder', type=str, default=0)
    parser.add_argument('-c', '--compression', type=str,
                        help='Set file\'s compression (acceptables values : \'gz\' (recommended to fit IGS standards), \'Z\', \'none\')', default='')
    parser.add_argument(
        '-l', '--longname', help='Rename file using long name RINEX convention (force gzip compression).', action='store_true', default=False)
    parser.add_argument(
        '-f', '--force', help="Force sitelog-based header values when RINEX's header and sitelog site name do not correspond", action='store_true')
    parser.add_argument(
        '-i', '--ignore', help='Ignore firmware changes between instrumentation periods when getting header values info from sitelogs', action='store_true')
    parser.add_argument(
        '-a', '--alone', help='INPUT is a alone RINEX file and not a file containing list of RINEX files paths', action='store_true')
    parser.add_argument('-o', '--output_logs',
                        help='Folder where to write output logs', type=str)
    parser.add_argument(
        '-w', '--write', help='Write (RINEX version, sample rate, file period) dependant output lists', action='store_true')
    parser.add_argument(
        '-v', '--verbose', help='Print file\'s metadata before and after modifications.', action='store_true', default=False)
    parser.add_argument('-t', '--sort', help='Sort the input RINEX list.', action='store_true', default=False)
    
    args = parser.parse_args()

    rinexlist = args.rinexlist
    outputfolder = args.outputfolder
    sitelog = args.sitelog
    modification_kw = args.modification_kw
    marker = args.marker
    ninecharfile = args.ninecharfile
    relative = args.relative
    compression = args.compression
    longname = args.longname
    force = args.force
    ignore = args.ignore
    alone = args.alone
    output_logs = args.output_logs
    write = args.write
    verbose = args.verbose
    sort = args.sort

    rinexmod(rinexlist, outputfolder, marker, longname, alone, sitelog, force, relative,
             ignore, ninecharfile, modification_kw, verbose, compression, output_logs, write, sort)
