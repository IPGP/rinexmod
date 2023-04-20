#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This script takes a list of RINEX Hanakata compressed files (.d.Z or .d.gz or .rnx.gz),
loop the RINEX files list to modifiy the file's header. It then write them back to Hanakata
compressed format in an output folder. It permits also to rename the files changing
the four first characters of the file name with another site code. It can write
those files with the long name naming convention with the --longname option.

Two ways of passing parameters to modifiy headers are possible:

--modif_kw : you pass as argument the field(s) that you want to modifiy and its value.
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

You can not provide both --modif_kw and --sitelog options.

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
-k : --modif_kw :    Header fields that you want to modify.
                            Will override the information from the sitelog.
                            The sitelogs must be valid as the script does not check it.
-f : --force :              Force sitelog-based header values when RINEX's header
                            and sitelog's site name do not correspond.
-i : --ignore :             Ignore firmware changes between instrumentation periods
                            when getting headers args info from sitelogs.
-m : --marker :             A four or nine character site code that will be used to rename
                            input files.
                            (apply also to the header\'s MARKER NAME, 
                             but a custom -k marker_name='XXXX' overrides it)
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
-r : --relative :           Reconstruct files relative subdirectory. You have to indicate the
                            part of the path that is common to all files in the list and
                            that will be replaced with output folder.
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

   
# define Python user-defined exceptions

class RinexModError(Exception):
    pass

class RinexModInputArgsError(RinexModError):
    pass

class RinexFileError(RinexModError):
    pass

class SitelogError(RinexModError):
    pass



def loggersVerbose(logfile=None):
    '''
    This function manage logging levels. It has two outputs, one to the prompt,
    the other to a logfile defined by 'logfile'.
    '''

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    # This handler will write to a log file
    if logfile:
        filehandler = logging.FileHandler(logfile, mode='a', encoding='utf-8')  
    # This one is for prompt
    prompthandler = logging.StreamHandler()

    promptformatter = logging.Formatter(
        '%(asctime)s - %(levelname)-7s - %(message)s')
    fileformatter = logging.Formatter(
        '%(asctime)s - %(levelname)-7s - %(message)s')

    prompthandler.setFormatter(promptformatter)
    if logfile:
        filehandler.setFormatter(fileformatter)

    # Setting handler logging level.
    prompthandler.setLevel(logging.INFO)
    if logfile:
        filehandler.setLevel(logging.WARNING)

    logger.addHandler(prompthandler)
    if logfile:
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
    """
    Gives the Git hash to have a tracking of the used version

    Returns
    -------
    7 characters Git hash

    """
    script_path = os.path.dirname(os.path.realpath(__file__))
    cmd = ['git', '--git-dir', script_path +
           '/.git', 'rev-parse', '--short', 'HEAD']
    try:
        return subprocess.check_output(cmd).decode('ascii').strip()[:7]
    except:
        return "xxxxxxx"


def _sitelog_files2objs_convert(sitelog_inp,
                                logger=None,
                                force = False,
                                return_list_even_if_single_input=True,
                                verbose=True):
    
    if not logger:
        logger = loggersVerbose(None)
    
    # Case of one sitelog:
    if os.path.isfile(sitelog_inp):
    
        # Creating sitelog object
        sitelogobj = SiteLog(sitelog_inp)
        # If sitelog is not parsable
        if sitelogobj.status != 0:
            print('# ERROR : The sitelog is not parsable : ' + sitelog_inp)
            raise SitelogError
            
        if return_list_even_if_single_input:
            sitelogs_obj_list = [sitelogobj]
        else:
            sitelogs_obj_list = sitelogobj
    
    # Case of a folder
    elif os.path.isdir(sitelog_inp):
    
        if force:
            print('# ERROR : --force option is meaningful only when providing a single sitelog (and not a folder contaning several sitelogs)')
            raise SitelogError
    
        sitelog_extension = '.log'
        all_sitelogs = listfiles(sitelog_inp, sitelog_extension)
    
        sitelog_pattern = re.compile('\w{3,9}_\d{8}.log')
        all_sitelogs = [file for file in all_sitelogs if sitelog_pattern.match(
            os.path.basename(file))]
    
        if verbose:
            logger.info('**** All sitelogs detected:')
            for sl in all_sitelogs:
                logger.info(sl)
    
        # Get last version of sitelogs if multiple available
        sitelogs_obj_list = []
        # We list the available sites to group sitelogs
        sitelogsta = [os.path.basename(sl)[0:4] for sl in all_sitelogs]
    
        for sta in sitelogsta:
            # Grouping by site
            sta_sitelogs = [sl for sl in all_sitelogs if os.path.basename(sl)[0:4] == sta]
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
                raise SitelogError
    
            # Appending to list
            sitelogs_obj_list.append(sitelogobj)
    
        if verbose:
            logger.info('**** Most recent sitelogs selected:')
            for sl in sitelogs_obj_list:
                logger.info(sl.path)

    return sitelogs_obj_list

def _sitelog_find(rnxobj,sitelogs_obj_list,logger=None):
    if not logger:
        logger = loggersVerbose(None)
    
    # Finding the right sitelog. If is list, can not use force. If no sitelog found, do not process.
    rnx_4char = rnxobj.get_site_from_filename('lower', only_4char=True)

    if rnx_4char not in [sl.site4char for sl in sitelogs_obj_list]:
        if len(sitelogs_obj_list) == 1:
            if not force:
                logger.error('{:110s} - {}'.format(
                    '33 - Filename\'s site does not correspond to provided sitelog - use -f option to force', rnxobj.filename))
                raise RinexModInputArgsError
            else:
                logger.warning('{:110s} - {}'.format(
                    '34 - Filename\'s site does not correspond to provided sitelog, processing anyway', rnxobj.filename))
        else:
            logger.error(
                '{:110s} - {}'.format('33 - No provided sitelog for this file\'s site', rnxobj.filename))
            raise RinexModInputArgsError
    else:
        sitelogobj = [sl for sl in sitelogs_obj_list if sl.site4char == rnx_4char][0] 
        ## we assume the latest sitelog has been found in _sitelog_files2objs_convert
        
    return sitelogobj
        

def _sitelogobj_apply_on_rnxobj(rnxobj,sitelogobj,logger=None,verbose=True,ignore=False):
    if not logger:
        logger = loggersVerbose(None)
        
    # Site name from the rinex's filename
    site_meta = rnxobj.get_site_from_filename('lower', only_4char=True)
    if verbose:
        logger.info('Searching corresponding sitelog for site : ' + site_meta)

    # Site name from the sitelog
    sitelog_site_code = sitelogobj.info['1.']['Four Character ID'].lower()

    # Get rinex header values from sitelog infos and start and end time of the file
    # ignore option is to ignore firmware changes between instrumentation periods.
    metadata_vars, ignored = sitelogobj.rinex_metadata_lines(
        rnxobj.start_date, rnxobj.end_date, ignore)

    if not metadata_vars:
        logger.error('{:110s} - {}'.format(
            '35 - No instrumentation corresponding to the data period on the sitelog', rnxobj.filename))
        raise SitelogError

    if ignored:
        logger.warning('{:110s} - {}'.format(
            '36 - Instrumentation cames from merged periods of sitelog with different firmwares, processing anyway', rnxobj.filename))

    (fourchar_id, domes_id, observable_type, agencies, receiver,
     antenna, antenna_pos, antenna_delta) = metadata_vars

    if verbose:
        logger.info('File Metadata :\n' +
                    rnxobj.get_metadata()[0])

    # # Apply the modifications to the RinexFile object
    rnxobj.set_marker(fourchar_id, domes_id)
    rnxobj.set_receiver(**receiver)
    rnxobj.set_interval(rnxobj.sample_rate_numeric)
    rnxobj.set_antenna(**antenna)
    rnxobj.set_antenna_pos(**antenna_pos)
    rnxobj.set_antenna_delta(**antenna_delta)
    rnxobj.set_agencies(**agencies)
    rnxobj.set_sat_system(observable_type)
    
    return rnxobj


def _modif_kw_check(modif_kw):

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

    for kw in modif_kw:
        if kw not in acceptable_keywords:
            print(
                '# ERROR : \'{}\' is not an acceptable keyword for header modification.'.format(kw))
            return RinexModInputArgsError
        
        
def _modif_kw_apply_on_rnxobj(modif_kw,rinexfileobj):
    rinexfileobj.set_marker(modif_kw.get('marker_name'),
                            modif_kw.get('marker_number'))

    # legacy keyword, 'marker_name' should be used instead
    rinexfileobj.set_marker(modif_kw.get('station'))

    rinexfileobj.set_receiver(modif_kw.get('receiver_serial'),
                              modif_kw.get('receiver_type'),
                              modif_kw.get('receiver_fw'))

    rinexfileobj.set_antenna(modif_kw.get('antenna_serial'),
                             modif_kw.get('antenna_type'))

    rinexfileobj.set_antenna_pos(modif_kw.get('antenna_X_pos'),
                                 modif_kw.get('antenna_Y_pos'),
                                 modif_kw.get('antenna_Z_pos'))

    rinexfileobj.set_antenna_delta(modif_kw.get('antenna_H_delta'),
                                   modif_kw.get(
                                       'antenna_E_delta'),
                                   modif_kw.get('antenna_N_delta'))

    rinexfileobj.set_agencies(modif_kw.get('operator'),
                              modif_kw.get('agency'))

    rinexfileobj.set_sat_system(modif_kw.get('observables'))

    rinexfileobj.set_interval(modif_kw.get('interval'))

    # for the filename
    rinexfileobj.set_filename_file_period(
        modif_kw.get('filename_file_period'))
    rinexfileobj.set_filename_data_freq(
        modif_kw.get('filename_data_freq'))
    
    return rinexfileobj


def _return_lists_write(return_lists,logfolder,now_dt=None):
    # Writing an output file for each RINEX_VERSION, SAMPLE_RATE, FILE_PERIOD lists
    if not now_dt:
        now_dt = datetime.now()
        
    for rinex_version in return_lists:
        for sample_rate in return_lists[rinex_version]:
            for file_period in return_lists[rinex_version][sample_rate]:

                this_outputfile = '_'.join(
                    ['RINEX' + rinex_version, sample_rate, file_period, datetime.strftime(now_dt, '%Y%m%d%H%M'), 'delivery.lst'])
                this_outputfile = os.path.join(logfolder, this_outputfile)

                # Writting output to temporary file and copying it them to target files
                with open(this_outputfile, 'w') as f:
                    f.writelines('{}\n'.format(
                        line) for line in return_lists[rinex_version][sample_rate][file_period])
                    print('# Output rinex list written to ' + this_outputfile)
    return this_outputfile
                        
                        
def rinexmod(file, outputfolder, marker=None, longname=None, sitelog=None,
             force_rnx_load=False, force_sitelog=False, relative=False,
             ignore=False, ninecharfile=None, modif_kw=None, verbose=True,
             compression='', return_lists=dict(), logger=None):
    
    if not logger:
        logger = loggersVerbose(None)
    
    now = datetime.now()

    logger.info('# File : ' + file)

    if relative:
        if not relative in file:
            logger.error(
                '{:110s} - {}'.format('31 - The relative subfolder can not be reconstructed for file', file))
            raise RinexModInputArgsError

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
        raise RinexFileError

    # Declare the rinex file as an object
    rnxobj = RinexFile(file,force_loading=force_rnx_load)

    if rnxobj.status == 1:
        logger.error(
            '{:110s} - {}'.format('01 - The specified file does not exists', file))
        raise RinexFileError

    if rnxobj.status == 2:
        logger.error(
            '{:110s} - {}'.format('02 - Not an observation Rinex file', file))
        raise RinexFileError

    if rnxobj.status == 3:
        logger.error(
            '{:110s} - {}'.format('03 - Invalid or empty Zip file', file))
        raise RinexFileError

    if rnxobj.status == 4:
        logger.error(
            '{:110s} - {}'.format('04 - Invalid Compressed Rinex file', file))
        raise RinexFileError

    if rnxobj.status == 5:
        logger.error(
            '{:110s} - {}'.format('05 - Less than two epochs in the file', file))
        raise RinexFileError
    
    # Check that the provided marker is a 4-char site name
    if marker and (len(marker) != 4 and len(marker) != 9):
        print('# ERROR : The site name provided is not 4 or 9-char valid : ' + marker)
        raise RinexModInputArgsError
    
    # Get the 4 char > 9 char dictionnary from the input list
    nine_char_dict = dict()  # in any case, nine_char_dict is initialized
    if ninecharfile:
        if not os.path.isfile(ninecharfile):
            print(
                '# ERROR : The specified 9-chars. list file does not exists : ' + ninecharfile)
            raise RinexModInputArgsError

        with open(ninecharfile, "r") as F:
            nine_char_list = F.readlines()

        for site_key in nine_char_list:
            nine_char_dict[site_key[:4].lower()] = site_key.strip()

    # Checking input keyword modification arguments
    if modif_kw:
        _modif_kw_check(modif_kw)

    if marker:
        # We store the old site name to add a comment in rinex file's header
        modif_marker = rnxobj.filename[:4]
        rnxobj.set_filename_site(marker)
        modif_kw_marker = {"marker_name" : marker}
        rnxobj = _modif_kw_apply_on_rnxobj(rnxobj,modif_kw)

    # set default value for the monument & country codes
    monum_country = "00XXX"
    if longname:
        # We rename the file to the rinex long name convention
        # Get the site 9-char name
        if not ninecharfile or not rnxobj.get_site_from_filename('lower', True) in nine_char_dict:
            logger.warning('{:110s} - {}'.format(
                '32 - Site\'s country not retrevied, will not be properly renamed', file))
        else:
            monum_country = nine_char_dict[rnxobj.get_site_from_filename('lower', True)].upper()[4:]
            
        # NB: the longfilename will be generated later 
        # (The block "we regenerate the filenames")

    ######## Apply the sitelog objects on the RinexFile object
    if sitelog:
        if type(sitelog) is list:
            sitelogs = sitelog
        else:
            sitelogs = [sitelog]
        
        sitelogs_obj_list = _sitelog_files2objs_convert(sitelog,
                                                        logger,
                                                        force_sitelog)
        
        sitelogobj = _sitelog_find(rnxobj,
                                   sitelogs_obj_list,
                                   logger=logger)
        rnxobj = _sitelogobj_apply_on_rnxobj(rnxobj, sitelogobj,ignore=ignore)
        modif_source = sitelogobj.filename

    ######## Apply the modif_kw dictionnary on the RinexFile object
    if modif_kw:
        if verbose:
            logger.info('File Metadata :\n' +
                        rnxobj.get_metadata()[0])
        modif_source = 'command line'
        rnxobj = _modif_kw_apply_on_rnxobj(rnxobj,modif_kw)

    if verbose:
        logger.info('File Metadata :\n' + rnxobj.get_metadata()[0])

    # Adding comment in the header
    vers_num = get_git_revision_short_hash()
    #rnxobj.add_comment(("RinexMod (IPGP)","METADATA UPDATE"),add_pgm_cmt=True)
    rnxobj.add_comment(
        ("RinexMod "+vers_num, "METADATA UPDATE"), add_pgm_cmt=True)
    rnxobj.add_comment('rinexmoded on {}'.format(
        datetime.strftime(now, '%Y-%m-%d %H:%M')))
    if sitelog or modif_kw:
        rnxobj.add_comment(
            'rinexmoded from {}'.format(modif_source))
    if marker:
        rnxobj.add_comment(
            'file assigned from {}'.format(modif_marker))

    #### we regenerate the filenames
    if rnxobj.name_conv == "SHORT" and not longname:
        rnxobj.get_shortname(inplace=True, compression='')
    else:
        rnxobj.get_longname(monum_country, inplace=True, compression='')

    # NB: here the compression type must be forced to ''
    #     it will be added in the next step 
    # (in the block "We convert the file back to Hatanaka Compressed Rinex")
    # inplace = True => rnxobj's filename is updated

    #### We convert the file back to Hatanaka Compressed Rinex 
    if longname and not compression:
        # If not specified, we set compression to gz when file changed to longname
        output_compression = 'gz'
    elif not compression:
        output_compression = rnxobj.compression
    else:
        output_compression = compression

    # Writing output file
    try:
        outputfile = rnxobj.write_to_path(
            myoutputfolder, compression=output_compression)
    except hatanaka.hatanaka.HatanakaException:
        logger.error(
            '{:110s} - {}'.format('06 - File could not be written - hatanaka exception', file))
        pass

    logger.info('Output file : ' + outputfile)

    ### Construct return dict by adding key if doesn't exists and appending file to corresponding list ###
    major_rinex_version = rnxobj.version[0]
    # Dict ordered as : RINEX_VERSION, SAMPLE_RATE, FILE_PERIOD
    if major_rinex_version not in return_lists:
        return_lists[major_rinex_version] = {}
    if rnxobj.sample_rate_string not in return_lists[major_rinex_version]:
        return_lists[major_rinex_version][rnxobj.sample_rate_string] = {}
    if rnxobj.file_period not in return_lists[major_rinex_version][rnxobj.sample_rate_string]:
        return_lists[major_rinex_version][rnxobj.sample_rate_string][rnxobj.file_period] = []

    return_lists[major_rinex_version][rnxobj.sample_rate_string][rnxobj.file_period].append(
        outputfile)
    
    return return_lists


def rinexmod_cli(rinexlist, outputfolder, marker, longname, alone, sitelog,
                 force, relative, ignore, ninecharfile, modif_kw, verbose,
                 compression, output_logs, write, sort):
    """
    Main function for reading a Rinex list file. It process the list, and apply
    file name modification, command line based header modification, or sitelog-based
    header modification.
    """

    # If no longname, modif_kw and sitelog, return
    if not sitelog and not modif_kw and not marker and not longname:
        print('# ERROR : No action asked, provide at least one of the following args : --sitelog, --modif_kw, --marker, --longname.')
        raise RinexModInputArgsError

    # If force option provided, check if sitelog option too, if not, not relevant.
    if force and not sitelog:
        print('# ERROR : --force option is meaningful only when --sitelog option with a **single** sitelog is also provided')
        raise RinexModInputArgsError

    # If ignore option provided, check if sitelog option too, if not, not relevant.
    if ignore and not sitelog:
        print(
            '# ERROR : --ignore option is meaningful only when using also --sitelog option')
        raise RinexModInputArgsError

    if ninecharfile and not longname:
        print('# ERROR : --ninecharfile option is meaningful only when using also --longname option')
        raise RinexModInputArgsError

    # If inputfile doesn't exists, return
    if isinstance(rinexlist, list):
        pass
    elif not os.path.isfile(rinexlist):
        print('# ERROR : The input file doesn\'t exist : ' + rinexlist)
        raise RinexModInputArgsError


    if output_logs and not os.path.isdir(output_logs):
        print(
            '# ERROR : The specified output folder for logs doesn\'t exist : ' + output_logs)
        raise RinexModInputArgsError

    outputfolder = os.path.abspath(outputfolder)

    if not os.path.isdir(outputfolder):
        # mkdirs ???
        os.makedirs(outputfolder)

    # Creating log file
    now = datetime.now()
    dt = datetime.strftime(now, '%Y%m%d%H%M%S')

    if output_logs:
        logfolder = output_logs
    else:
        logfolder = outputfolder

    logfile = os.path.join(logfolder, dt + '_' + 'rinexmod_errors.log')

    logger = loggersVerbose(logfile)


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
            return RinexModInputArgsError

    # sort the RINEX list
    if sort:
        rinexlist.sort()

    ### Looping in file list ###
    return_lists = {}


    ####### Iterate over each RINEX
    for rnx in rinexlist:
        return_lists = rinexmod(rnx, outputfolder, marker, longname,
                                sitelog, force, relative, ignore,
                                ninecharfile, modif_kw, verbose,
                                compression, output_logs, write,  sort)
        
    #########################################


    logger.handlers.clear()

    if write:
        _return_lists_write(return_lists,logfolder,now)

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
    parser.add_argument('-k', '--modif_kw', help='''Modification keywords for RINEX's header and/or filename. Will override the information from the sitelog. 
                                                           Format : keyword_1=\'value\' keyword2=\'value\'. Acceptable keywords:\n
                                                           marker_name, marker_number, station (legacy alias for marker_name), receiver_serial, receiver_type, receiver_fw, antenna_serial, antenna_type,
                                                           antenna_X_pos, antenna_Y_pos, antenna_Z_pos, antenna_H_delta, antenna_E_delta, antenna_N_delta,
                                                           operator, agency, observables, interval, filename_file_period (01H, 01D...), filename_data_freq (30S, 01S...)''', nargs='*', action=ParseKwargs, default=None)
    parser.add_argument('-m', '--marker', help="Change 4 or 9 first letters of file\'s name to set it to another site (apply also to the header\'s MARKER NAME, but a custom -k marker_name='XXXX' overrides it)", type=str, default='')
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
    modif_kw = args.modif_kw
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

    rinexmod_cli(rinexlist, outputfolder, marker, longname, alone, sitelog, force, relative,
                 ignore, ninecharfile, modif_kw, verbose, compression, output_logs, write, sort)
