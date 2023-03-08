#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API function of rinexmod

Created on Wed Mar  8 12:14:54 2023

@author: psakicki
"""
import os
import re
from datetime import datetime
import logging
from sitelogs_IGS import SiteLog
from rinexfile import RinexFile
import hatanaka
import subprocess

# *****************************************************************************
# define Python user-defined exceptions
class RinexModError(Exception):
    pass

class RinexModInputArgsError(RinexModError):
    pass

class RinexFileError(RinexModError):
    pass

class SitelogError(RinexModError):
    pass

# *****************************************************************************
# logger definition

def logger_define(level_prompt,logfile,level_logfile=None):
    '''
    This function manage logging levels. It has two outputs, one to the prompt,
    the other to a logfile defined by 'logfile'.
    '''

    logger = logging.getLogger()
    logger.setLevel(level_prompt)
    
    # This handler is for prompt (console)
    prompthandler = logging.StreamHandler()
    promptformatter = logging.Formatter('%(asctime)s - %(levelname)-7s - %(message)s')
    prompthandler.setFormatter(promptformatter)
    prompthandler.setLevel(level_prompt)
    if not len(logger.handlers):
        logger.addHandler(prompthandler)
    
    # This handler will write to a log file
    if logfile:
        if not level_logfile:
            level_logfile = level_prompt
        filehandler = logging.FileHandler(logfile, mode='a', encoding='utf-8')  
        fileformatter = logging.Formatter('%(asctime)s - %(levelname)-7s - %(message)s')
        filehandler.setFormatter(fileformatter)
        filehandler.setLevel(level_logfile)
        logger.addHandler(filehandler)

    return logger

logfile = None
logger = logger_define('DEBUG',logfile)

def logger_tester():
    logger.debug("debug message")
    logger.info("info message")
    logger.warning("warning message")
    logger.error("error message")
    logger.critical("critical message")
    
    
# *****************************************************************************
# misc functions

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
def git_get_revision_short_hash():
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


# *****************************************************************************
# Sitelog import

def _sitelog_input_manage(sitelog_inp,force):
    """
    Manage the multiple types possible for a Sitelog inputs
    Return a list of SiteLog to be handeled by _sitelog_find_site
    
    Possible inputs are 
    * list of string (sitelog file paths),
    * single string (single sitelog file path or directory containing the sitelogs),
    * list of SiteLog object
    * single SiteLog object
    

    Parameters
    ----------
    sitelog_inp : list of str, str, list of SiteLog. single SiteLog
        Various Input sitelogs.
    force : bool
        Force a single sitelog file path.

    Returns
    -------
    list of SiteLog

    """
    if isinstance(sitelog_inp,SiteLog):
        return [sitelog_inp]
    elif type(sitelog_inp) is list and isinstance(sitelog_inp[0],SiteLog):
        return sitelog_inp
    else:
        return _sitelog_files2objs_convert(sitelog_inp,
                                           force=force,
                                           return_list_even_if_single_input=True)
        

def _sitelog_files2objs_convert(sitelog_filepath,
                                force = False,
                                return_list_even_if_single_input=True):
    
    # Case of one sitelog:
    if os.path.isfile(sitelog_filepath):
    
        # Creating sitelog object
        sitelogobj = SiteLog(sitelog_filepath)
        # If sitelog is not parsable
        if sitelogobj.status != 0:
            logger.error('The sitelog is not parsable : ' + sitelog_filepath)
            raise SitelogError
            
        if return_list_even_if_single_input:
            sitelogs_obj_list = [sitelogobj]
        else:
            sitelogs_obj_list = sitelogobj
    
    # Case of a folder
    elif os.path.isdir(sitelog_filepath):
    
        if force:
            logger.error('--force option is meaningful only when providing a single sitelog (and not a folder contaning several sitelogs)')
            raise SitelogError
    
        sitelog_extension = '.log'
        all_sitelogs = listfiles(sitelog_filepath, sitelog_extension)
    
        sitelog_pattern = re.compile('\w{3,9}_\d{8}.log')
        all_sitelogs = [file for file in all_sitelogs if sitelog_pattern.match(
            os.path.basename(file))]
    
        logger.debug('**** All sitelogs detected:')
        for sl in all_sitelogs:
            logger.debug(sl)

        # Get last version of sitelogs if multiple available
        latest_sitelogs = _sitelog_find_latest_files(all_sitelogs)
        
        sitelogs_obj_list = []
        for sta_sitelog in latest_sitelogs:
            # Creating sitelog object
            sitelogobj = SiteLog(sta_sitelog)
    
            # If sitelog is not parsable
            if sitelogobj.status != 0:
                logger.error('The sitelog is not parsable: ' +
                      sitelogobj.path)
                raise SitelogError
    
            # Appending to list
            sitelogs_obj_list.append(sitelogobj)
    
        logger.debug('**** Most recent sitelogs selected:')
        for sl in sitelogs_obj_list:
            logger.debug(sl.path)

    return sitelogs_obj_list


def _sitelog_find_latest_files(all_sitelogs_filepaths):
    # We list the available sites to group sitelogs
    sitelogsta = [os.path.basename(sl)[0:4] for sl in all_sitelogs_filepaths]
    # set the output latest sitelog list
    latest_sitelogs_filepaths = []
    
    for sta in sitelogsta:
        # Grouping by site
        sta_sitelogs = [sl for sl in all_sitelogs_filepaths if os.path.basename(sl)[0:4] == sta]
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
        
        latest_sitelogs_filepaths.append(sta_sitelog)
    
    return latest_sitelogs_filepaths
    

def _sitelog_find_site(rnxobj,sitelogs_obj_list,force):
    # Finding the right sitelog. If is list, can not use force. If no sitelog found, do not process.
    rnx_4char = rnxobj.get_site_from_filename('lower', only_4char=True)
    logger.debug('Searching corresponding sitelog for site : ' + rnx_4char)

    if rnx_4char not in [sl.site4char for sl in sitelogs_obj_list]:
        if len(sitelogs_obj_list) == 1:
            if not force:
                logger.error('{:110s} - {}'.format(
                    '33 - RINEX name\'s site does not correspond to provided sitelog - use -f option to force', rnxobj.filename))
                raise RinexModInputArgsError
            else:
                logger.warning('{:110s} - {}'.format(
                    '34 - RINEX name\'s site does not correspond to provided sitelog, forced processing anyway', rnxobj.filename))
        else:
            logger.error(
                '{:110s} - {}'.format('33 - No sitelog found for this RINEX', rnxobj.filename))
            raise RinexModInputArgsError
    else:
        sitelogobj = [sl for sl in sitelogs_obj_list if sl.site4char == rnx_4char][0] 
        ## we assume the latest sitelog has been found in _sitelog_files2objs_convert
        
    return sitelogobj
        

def _sitelogobj_apply_on_rnxobj(rnxobj,sitelogobj,ignore=False):
    rnx_4char = rnxobj.get_site_from_filename('lower', only_4char=True)
    # Site name from the sitelog
    sitelog_4char = sitelogobj.info['1.']['Four Character ID'].lower()
    
    if rnx_4char != sitelog_4char:
        logger.debug("RINEX and Sitelog 4 char. codes do not correspond, but I assume you know what you are doing (%s,%s)",rnx_4char,sitelog_4char)

    # Get rinex header values from sitelog infos and start and end time of the file
    # ignore option is to ignore firmware changes between instrumentation periods.
    metadata_vars, ignored = sitelogobj.rinex_metadata_lines(
        rnxobj.start_date, rnxobj.end_date, ignore)

    if not metadata_vars:
        logger.error('{:110s} - {}'.format(
            '35 - No sitelog instrumentation corresponding to the RINEX epoch', rnxobj.filename))
        raise SitelogError

    if ignored:
        logger.warning('{:110s} - {}'.format(
            '36 - Instrumentation cames from merged periods of sitelog with different firmwares, processing anyway', rnxobj.filename))

    (fourchar_id, domes_id, observable_type, agencies, receiver,
     antenna, antenna_pos, antenna_delta) = metadata_vars

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

# *****************************************************************************
# modification keyword dictionnary functions

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
            logger.error('{}\' is not an acceptable keyword for header modification.'.format(kw))
            return RinexModInputArgsError
        
    return None
        
   
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

# *****************************************************************************
# dictionnary as output for rinexmod

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
                    logger.debug('Output rinex list written to ' + this_outputfile)
    return this_outputfile
                        
            
# *****************************************************************************
# Main function            
            
def rinexmod(rinexfile, outputfolder, sitelog=None, modif_kw=dict(), marker='',
             longname=False, force_rnx_load=False, force_sitelog=False,
             ignore=False, ninecharfile=None, compression=None, relative='', 
             verbose=True, return_lists=dict()):
    """
    Parameters
    ----------
    rinexfile : str
        Input RINEX file to process.
    outputfolder : str
        Folder where to write the modified RINEX files.
    sitelog : str, list of str, SiteLog object, list of SiteLog objects, optional
        Get the RINEX header values from a sitelog.
        Possible inputs are 
        * list of string (sitelog file paths),
        * single string (single sitelog file path or directory containing the sitelogs),
        * list of SiteLog object
        * single SiteLog object
        The function will search for the latest and right sitelog
        corresponding to the site.
        One can force a single sitelog with force_sitelog.
        The default is None.
    modif_kw : dict, optional
        Modification keywords for RINEX's header fields and/or filename.
        Will override the information from the sitelog.
        Acceptable keywords for the header fields:
        * marker_name
        * marker_number
        * station (legacy alias for marker_name)
        * receiver_serial
        * receiver_type
        * receiver_fw 
        * antenna_serial
        * antenna_type,
        * antenna_X_pos
        * antenna_Y_pos
        * antenna_Z_pos
        * antenna_H_delta, 
        * antenna_E_delta
        * antenna_N_delta,
        * operator
        * agency
        * observables
        * interval
        Acceptable keywords for the header fields:
        * filename_file_period (01H, 01D...), 
        * filename_data_freq (30S, 01S...)
        The default is dict().
    marker : str, optional
        A four or nine character site code that will be used to rename
        input files.
        Apply also to the header's MARKER NAME, 
        but a custom modification kewyord marker_name='XXXX' overrides it 
        (modif_kw argument below)
        The default is ''.
    longname : bool, optional
        Rename file using long name RINEX convention (force gzip compression).
        The default is False.
    force_rnx_load : bool, optional
        Force the loading of the input RINEX. Useful if its name is not standard.
        The default is False.
    force_sitelog : bool, optional
        Force sitelog-based header values when RINEX's header
        and sitelog site name do not correspond. The default is False.
    ignore : bool, optional
        Ignore firmware changes between instrumentation periods 
        when getting header values info from sitelogs. The default is False.
    ninecharfile : str, optional
        Path of a file that contains 9-char. site names from the M3G database.
        The default is None.
    compression : TYPE, optional
        Set RINEX compression 
        acceptables values : gz (recommended to fit IGS standards), 'Z', None. 
        The default is None.
    relative : str, optional
        Reconstruct files relative subfolders. 
        You have to indicate the common parent folder, 
        that will be replaced with the output folder. The default is ''.
    verbose : bool, optional
        set the level of verbosity 
        (False for the INFO level, True for the DEBUG level).
        The default is True.
    return_lists : dict, optional
        DESCRIPTION. The default is dict().

    Raises
    ------
    RinexModInputArgsError
        Something is wrong with the input arguments.
    RinexFileError
        Something is wrong with the input RINEX File.

    Returns
    -------
    return_lists : dict
        DESCRIPTION.

    """
    
    now = datetime.now()

    if verbose:
        logger = logger_define('DEBUG', logfile, 'DEBUG')
    else:
        logger = logger_define('INFO', logfile, 'INFO')

    logger.info('# File : ' + rinexfile)

    if relative:
        if not relative in rinexfile:
            logger.error(
                '{:110s} - {}'.format('31 - The relative subfolder can not be reconstructed for RINEX file', rinexfile))
            raise RinexModInputArgsError

        # We construct the output path with relative path between file name and parameter
        relpath = os.path.relpath(os.path.dirname(rinexfile), relative)
        myoutputfolder = os.path.join(outputfolder, relpath)
        if not os.path.isdir(myoutputfolder):
            os.makedirs(myoutputfolder)
    else:
        myoutputfolder = outputfolder

    if os.path.abspath(os.path.dirname(rinexfile)) == myoutputfolder:
        logger.error(
            '{:110s} - {}'.format('30 - Input and output folders are the same !', rinexfile))
        raise RinexFileError

    # Declare the rinex file as an object
    rnxobj = RinexFile(rinexfile,force_rnx_load=force_rnx_load)

    if rnxobj.status == 1:
        logger.error(
            '{:110s} - {}'.format('01 - The specified file does not exists', rinexfile))
        raise RinexFileError

    if rnxobj.status == 2:
        logger.error(
            '{:110s} - {}'.format('02 - Not an observation RINEX file', rinexfile))
        raise RinexFileError

    if rnxobj.status == 3:
        logger.error(
            '{:110s} - {}'.format('03 - Invalid or empty Zip file', rinexfile))
        raise RinexFileError

    if rnxobj.status == 4:
        logger.error(
            '{:110s} - {}'.format('04 - Invalid Compressed RINEX file', rinexfile))
        raise RinexFileError

    if rnxobj.status == 5:
        logger.error(
            '{:110s} - {}'.format('05 - Less than two epochs in the file', rinexfile))
        raise RinexFileError
        
    logger.debug('RINEX Origin Metadata :\n' + rnxobj.get_metadata()[0])

    # Check that the provided marker is a 4-char site name
    if marker and (len(marker) != 4 and len(marker) != 9):
        logger.error('The site name provided is not 4 or 9-char valid : ' + marker)
        raise RinexModInputArgsError
    
    # Get the 4 char > 9 char dictionnary from the input list
    nine_char_dict = dict()  # in any case, nine_char_dict is initialized
    if ninecharfile:
        if not os.path.isfile(ninecharfile):
            logger.error('The specified 9-chars. list file does not exists : ' + ninecharfile)
            raise RinexModInputArgsError

        with open(ninecharfile, "r") as F:
            nine_char_list = F.readlines()

        for site_key in nine_char_list:
            nine_char_dict[site_key[:4].lower()] = site_key.strip()

    ###########################################################################
    ########## Apply the sitelog objects on the RinexFile object
    if sitelog:            
        sitelogs_obj_list = _sitelog_input_manage(sitelog,
                                                  force=force_sitelog)
        sitelogobj = _sitelog_find_site(rnxobj,
                                        sitelogs_obj_list,
                                        force=force_sitelog)
        
        rnxobj = _sitelogobj_apply_on_rnxobj(rnxobj, sitelogobj,ignore=ignore)
        logger.debug('RINEX Sitelog-Modified Metadata :\n' + rnxobj.get_metadata()[0])
        modif_source = sitelogobj.filename

    ###########################################################################
    ########## Apply the modif_kw dictionnary on the RinexFile object
    if modif_kw:
        # Checking input keyword modification arguments
        _modif_kw_check(modif_kw)

        modif_source = 'manual keywords'
        rnxobj = _modif_kw_apply_on_rnxobj(rnxobj,modif_kw)
        logger.debug('RINEX Manual Keywords-Modified Metadata :\n' + rnxobj.get_metadata()[0])

    ###########################################################################
    ########## Handle the similar options + longname + marker option + country
    ### Priority for the Country source
    # 1) the marker option if 9 char are given
    # 2) the nine_char_dict from the ninecharfile option
    # 3) the sitelog (most useful actually,
    #    but a fallback mechanism has to be here if the sitelog is wrong)
    # set default value for the monument & country codes
    
    rnx_4char = rnxobj.get_site_from_filename('lower', True)

    if marker and len(marker) == 9:
        monum = marker[4:6]
        country = marker[6:]  
    elif ninecharfile:
        if not rnx_4char in nine_char_dict:
            logger.warning('32 - Site\'s missing in the input 9-char. file: %s', rinexfile)
        else:
            monum = nine_char_dict[rnx_4char].upper()[4:6]
            country = nine_char_dict[rnx_4char].upper()[6:]
    elif sitelog:
        monum = "00"
        country = sitelogobj.get_country()
    else:
        monum = "00"
        country = "XXX"
        
    if country == "XXX":
        logger.warning('32 - Site\'s country not retrevied, will not be properly renamed: %s', rinexfile)
      
    rnxobj.set_site_filename(rnx_4char+monum+country)
    
    if not marker and not ("marker_name" in modif_kw.keys()): # General case
        rnxobj.set_marker(rnxobj.get_site_from_filename('upper', False))
    elif marker: # specific actions if marker is given
        # We store the old site name to add a comment in rinex file's header
        modif_marker = rnxobj.get_site_from_filename('lower', False)
        rnxobj.set_site_filename(marker)
        if "marker_name" not in modif_kw.keys(): ### apply only is modif_kw does not overrides it
            rnxobj.set_marker(marker)

    ###########################################################################
    ########## Adding comment in the header
    vers_num = git_get_revision_short_hash()
    #rnxobj.add_comment(("RinexMod (IPGP)","METADATA UPDATE"),add_pgm_cmt=True)
    rnxobj.add_comment(("RinexMod "+vers_num, "METADATA UPDATE"),
                       add_pgm_cmt=True)
    rnxobj.add_comment('rinexmoded on {}'.format(
        datetime.strftime(now, '%Y-%m-%d %H:%M')))
    if sitelog or modif_kw:
        rnxobj.add_comment('rinexmoded with {}'.format(modif_source))
    if marker:
        rnxobj.add_comment('filename assigned from {}'.format(modif_marker))

    ###########################################################################
    ########## we regenerate the filenames
    if rnxobj.name_conv == "SHORT" and not longname:
        rnxobj.get_shortname(inplace_set=True, compression='')
    else:
        rnxobj.get_longname(monum, country, inplace_set=True, compression='')

    # NB: here the compression type must be forced to ''
    #     it will be added in the next step 
    # (in the block "We convert the file back to Hatanaka Compressed Rinex")
    # inplace_set = True => rnxobj's filename is updated

    ###########################################################################
    ########## We convert the file back to Hatanaka Compressed Rinex 
    if longname and not compression:
        # If not specified, we set compression to gz when file changed to longname
        output_compression = 'gz'
    elif not compression:
        output_compression = rnxobj.compression
    else:
        output_compression = compression

    ###########################################################################
    ########## Writing output file
    try:
        outputfile = rnxobj.write_to_path(
            myoutputfolder, compression=output_compression)
    except hatanaka.hatanaka.HatanakaException:
        logger.error(
            '{:110s} - {}'.format('06 - File could not be written - hatanaka exception', rinexfile))
        pass

    logger.info('Output file : ' + outputfile)

    ###########################################################################
    ########## Construct return dict by adding key if doesn't exists
    # and appending file to corresponding list ###
    major_rinex_version = rnxobj.version[0]
    # Dict ordered as : RINEX_VERSION, SAMPLE_RATE, FILE_PERIOD
    if major_rinex_version not in return_lists:
        return_lists[major_rinex_version] = {}
    if rnxobj.sample_rate_string not in return_lists[major_rinex_version]:
        return_lists[major_rinex_version][rnxobj.sample_rate_string] = {}
    if rnxobj.file_period not in return_lists[major_rinex_version][rnxobj.sample_rate_string]:
        return_lists[major_rinex_version][rnxobj.sample_rate_string][rnxobj.file_period] = []

    return_lists[major_rinex_version][rnxobj.sample_rate_string][rnxobj.file_period].append(outputfile)
    
    return return_lists


# *****************************************************************************
# Upper level rinexmod for a Console run

def rinexmod_cli(rinexlist,outputfolder,sitelog=None,modif_kw=dict(),marker='',
     longname=False, force_sitelog=False, force_rnx_load=False, ignore=False, ninecharfile=None, compression=None,
     relative='', verbose=True, alone=False, output_logs=None, write=False, sort=False):
    
    """
    Main function for reading a Rinex list file. It process the list, and apply
    file name modification, command line based header modification, or sitelog-based
    header modification.
    
    Optimized for a CLI (in a Terminal usage) but can be used also in a 
    stand-alone API mode.
    
    For a detailled description, check the help of the lower level 
    rinexmod function or the help of the frontend CLI function in a Terminal
    
    Parameters
    ----------
    rinexlist : list or str
        a filepath of a textfile containing a RINEX paths list 
        or directly a Python list of RINEX paths
    """

    # If no longname, modif_kw and sitelog, return
    if not sitelog and not modif_kw and not marker and not longname:
        logger.critical('No action asked, provide at least one of the following args : --sitelog, --modif_kw, --marker, --longname.')
        raise RinexModInputArgsError

    # If force option provided, check if sitelog option too, if not, not relevant.
    if force_sitelog and not sitelog:
        logger.critical('--force option is meaningful only when --sitelog option with a **single** sitelog is also provided')
        raise RinexModInputArgsError

    # If ignore option provided, check if sitelog option too, if not, not relevant.
    if ignore and not sitelog:
        logger.critical('--ignore option is meaningful only when using also --sitelog option')
        raise RinexModInputArgsError

    if ninecharfile and not longname:
        logger.critical('--ninecharfile option is meaningful only when using also --longname option')
        raise RinexModInputArgsError

    # If inputfile doesn't exists, return
    if isinstance(rinexlist, list):
        pass
    elif not os.path.isfile(rinexlist):
        logger.critical('The input file doesn\'t exist : ' + rinexlist)
        raise RinexModInputArgsError

    if output_logs and not os.path.isdir(output_logs):
        logger.critical('The specified output folder for logs doesn\'t exist : ' + output_logs)
        raise RinexModInputArgsError

    outputfolder = os.path.abspath(outputfolder)

    # Creating log file
    now = datetime.now()
    nowstr = datetime.strftime(now, '%Y%m%d%H%M%S')
    
    if output_logs:
        logfolder = output_logs
    else:
        logfolder = outputfolder

    logfile = os.path.join(logfolder, nowstr + '_' + 'rinexmod_errors.log')
    if verbose:
        _ = logger_define('DEBUG', logfile, 'DEBUG')
    else:
        _ = logger_define('INFO', logfile, 'INFO')

    if not os.path.isdir(outputfolder):
        # mkdirs ???
        os.makedirs(outputfolder)

    # Opening and reading lines of the file containing list of rinex to proceed
    if alone:
        rinexlist = [rinexlist]
    elif isinstance(rinexlist, list):
        pass
    else:
        try:
            rinexlist = [line.strip() for line in open(rinexlist).readlines()]
        except:
            logger.error('The input file is not a list : ' + rinexlist)
            return RinexModInputArgsError

    # sort the RINEX list
    if sort:
        rinexlist.sort()
        
    # load the sitelogs as a list of SiteLog objects
    if sitelog:
        sitelog_use = _sitelog_input_manage(sitelog, force_sitelog)

    ### Looping in file list ###
    return_lists = {}
    ####### Iterate over each RINEX
    for rnx in rinexlist:     
        try:
            return_lists = rinexmod(rinexfile=rnx,
                                    outputfolder=outputfolder,
                                    sitelog=sitelog_use,
                                    modif_kw=modif_kw,
                                    marker=marker,
                                    longname=longname,
                                    force_rnx_load=force_rnx_load,
                                    force_sitelog=force_sitelog,
                                    ignore=ignore,
                                    ninecharfile=ninecharfile,
                                    compression=compression,
                                    relative=relative, 
                                    verbose=verbose,
                                    return_lists=return_lists)
        except Exception as e:
            logger.error("%s raised, RINEX is skiped: %s",type(e).__name__,rnx)
        
    #########################################
    logger.handlers.clear()

    if write:
        _return_lists_write(return_lists,logfolder,now)

    return return_lists



