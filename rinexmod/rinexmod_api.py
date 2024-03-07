#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API functions of RinexMod

Created on Wed Mar  8 12:14:54 2023

@author: psakic
"""
import os
import re
from datetime import datetime
import hatanaka
import subprocess
import multiprocessing as mp
import pandas as pd

import rinexmod.metadata as rimo_mda
import rinexmod.rinexfile as rimo_rnx
import rinexmod.gamit_meta as rimo_gmm
import rinexmod.logger as rimo_log

logger = rimo_log.logger_define('INFO')


# *****************************************************************************
# define Python user-defined exceptions
class RinexModError(Exception):
    pass

class RinexModInputArgsError(RinexModError):
    pass

class RinexFileError(RinexModError):
    pass

class MetaDataError(RinexModError):
    pass

class ReturnListError(RinexModError):
    pass

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
    script_path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

    cmd = ['git', '--git-dir', script_path +
           '/.git', 'rev-parse', '--short', 'HEAD']
    try:
        githash = subprocess.check_output(cmd).decode('ascii').strip()[:7]
    except:
        logger.warn('unable to get the git commit version')
        githash = "xxxxxxx"

    #### 2msec to run this fuction

    return githash


# *****************************************************************************
# Sitelog import

def sitelog_input_manage(sitelog_inp, force=False):
    """
    Manage the multiple types possible for a Sitelog inputs
    Return a list of MetaData to be handeled by metadata_find_site
    
    Possible inputs are: 
     * list of string (sitelog file paths),
     * single string (single sitelog file path)
     * single string (directory containing the sitelogs)
     * list of MetaData objects
     * single MetaData object
    

    Parameters
    ----------
    sitelog_inp : list of str, str, list of MetaData. single MetaData
        Various Input sitelogs.
    force : bool
        Force a single sitelog file path.

    Returns
    -------
    list of MetaData

    """
    if isinstance(sitelog_inp, rimo_mda.MetaData):
        return [sitelog_inp]
    elif type(sitelog_inp) is list and isinstance(sitelog_inp[0], rimo_mda.MetaData):
        return sitelog_inp
    else:
        return sitelogs2metadata_objs(sitelog_inp,
                                      force=force,
                                      return_list_even_if_single_input=True)


def gamit2metadata_objs(station_info_inp, lfile_inp,
                        force_fake_coords=False):
    """
    Read a GAMIT files and convert their content to MetaData objects

    Parameters
    ----------
    station_info_inp : str
        Path of a GAMIT station.info file to obtain 
        GNSS site metadata information.
    lfile_inp : TYPE
        Path of a GAMIT apriori apr/L-File to obtain 
        GNSS site position and DOMES information.
    force_fake_coords : bool, optional
        hen using GAMIT station.info metadata without apriori coordinates in 
        the L-File, gives fake coordinates at (0°,0°) to the site. 
        The default is False.

    Returns
    -------
    metadataobj_lis : list
        list of MetaData objects.

    """
    if type(station_info_inp) is pd.core.frame.DataFrame:
        df_stinfo_raw = station_info_inp
        stinfo_name = 'station.info'
    else:
        df_stinfo_raw = rimo_gmm.read_gamit_station_info(station_info_inp)
        stinfo_name = os.path.basename(station_info_inp)

    if type(lfile_inp) is pd.core.frame.DataFrame:
        df_apr = lfile_inp
    else:
        df_apr = rimo_gmm.read_gamit_apr_lfile(lfile_inp)

    sites_isin = df_stinfo_raw['site'].isin(df_apr['site'])
    ### for the stats only
    sites_uniq = pd.Series(df_stinfo_raw['site'].unique())
    sites_isin_uniq = sites_uniq.isin(df_apr['site'].unique())
    n_sites_notin = len(sites_uniq) - sum(sites_isin_uniq)

    if n_sites_notin > 0 and not force_fake_coords:
        logger.warning("%i/%i sites in %s are not in apr/lfile. They are skipped (you can force fake coords with -fc)",
                       n_sites_notin, len(sites_uniq), stinfo_name)
        df_stinfo = df_stinfo_raw[sites_isin]
    elif n_sites_notin > 0 and force_fake_coords:
        logger.warning("%i/%i sites in %s are not in apr/lfile. Fake coords at (0°,0°) used",
                       n_sites_notin, len(sites_uniq), stinfo_name)
        df_stinfo = df_stinfo_raw
    else:  #### no missing coords, n_sites_notin == 0
        df_stinfo = df_stinfo_raw

    df_stinfo_grp = df_stinfo.groupby('site')

    metadataobj_lis = []

    logger.info('%i sites will be extracted from %s',
                len(df_stinfo_grp), stinfo_name)

    for site, site_info in df_stinfo_grp:
        logger.debug('extract %s from %s', site, stinfo_name)
        metadataobj = rimo_mda.MetaData(sitelogfile=None)
        metadataobj.set_from_gamit_meta(site, df_stinfo, df_apr,
                                        force_fake_coords=force_fake_coords,
                                        station_info_name=stinfo_name)
        metadataobj_lis.append(metadataobj)

    logger.info('%i sites have been extracted from %s',
                len(metadataobj_lis), stinfo_name)

    return metadataobj_lis


def sitelogs2metadata_objs(sitelog_filepath,
                           force=False,
                           return_list_even_if_single_input=True):
    """
    Read a set of sitelog files and convert them to MetaData objects

    Parameters
    ----------
    sitelog_filepath : str or list of str
        path of a single sitelog file or a set of sitelogs (stored in a list).
    force : bool, optional
        if it is not possible to read a sitelog (bad format), we skip it. 
        The default is False.
    return_list_even_if_single_input : bool, optional
        if a single sitelog is given, return the corresponding MetaData object
        into a list (singleton). The default is True.

    Raises
    ------
    MetaDataError
    RinexModInputArgsError

    Returns
    -------
    metadata_obj_list : list
        list of MetaData objects.

    """
        
    def _load_sitelog(sitelog_filepath,force):
        # Creating MetaData object
        try:
            metadataobj = rimo_mda.MetaData(sitelog_filepath)
        except Exception as e:    
            # If sitelog is not parsable
            logger.error('The sitelog is not parsable: %s (%s)',
                         os.path.basename(sitelog_filepath), str(e))
            if not force:
                raise MetaDataError
            else:
                metadataobj = None

        return metadataobj
    
    #### differenciating cases
    # Case of a list of sitelogs
    if type(sitelog_filepath) is list:
        all_sitelogs = sitelog_filepath
        sitelog_filepath = 'input sitelog list'
    # Case of one single sitelog
    elif os.path.isfile(sitelog_filepath):
        all_sitelogs = [sitelog_filepath]
    # Case of a folder
    elif os.path.isdir(sitelog_filepath):
        sitelog_extension = '.log'
        all_sitelogs = listfiles(sitelog_filepath, sitelog_extension)

        sitelog_pattern = re.compile('\w{4,9}_\d{8}.log')
        all_sitelogs = [file for file in all_sitelogs if sitelog_pattern.match(
            os.path.basename(file))]
    ### case of no file nor folder
    else:
        logger.error("unable to handle file/directory. Does it exists?: %s", 
                     sitelog_filepath)
        raise RinexModInputArgsError
    
    #### Read the sitelogs
    logger.info('**** %i sitelogs detected: (in %s)', len(all_sitelogs),
                sitelog_filepath)
    for sl in all_sitelogs:
        logger.debug(sl)
    # Get last version of sitelogs if multiple available
    latest_sitelogs = _sitelog_find_latest_files(all_sitelogs)

    metadata_obj_list = []
    bad_sitelogs_list = []
    for sta_sitelog in latest_sitelogs:
        metadataobj = _load_sitelog(sta_sitelog,force)
        # Appending to list
        if metadataobj:
            metadata_obj_list.append(metadataobj)
        else:
            bad_sitelogs_list.append(sta_sitelog) 

    logger.info('**** %i most recent sitelogs selected:',
                len(metadata_obj_list))
    
    for sl in metadata_obj_list:
        logger.debug(sl.path)
    
    if len(bad_sitelogs_list) > 0:
        logger.warning('**** %i badly-parsed & ignored sitelogs',
                       len(bad_sitelogs_list))   
            
    if len(metadata_obj_list) <= 1 and not return_list_even_if_single_input:
        metadata_obj_list = metadata_obj_list[0]

    return metadata_obj_list


def _sitelog_find_latest_files(all_sitelogs_filepaths):
    """
    Find the latest version of a sitelog within a list of sitelogs,
    mainly for time consumption reduction
    """
    # We list the available sites to group sitelogs
    bnm = os.path.basename
    sl_bnm = [bnm(sl) for sl in all_sitelogs_filepaths]
    sl_sta = [sl[0:4] for sl in sl_bnm]

    # set the output latest sitelog list
    latest_sitelogs_filepaths = []

    for sta in sl_sta:
        # Grouping by site
        sta_sitelogs = [slp for (slp,sln) in zip(all_sitelogs_filepaths,
                                                 sl_bnm) if sln[0:4] == sta]
        # Getting dates from basename
        #sitelogs_dates0 = [os.path.splitext(bnm(sl))[0][-8:] for sl in sta_sitelogs]
        # Getting dates from basename and parsing 'em
        sitelogs_dates = []
        for sl in sta_sitelogs:
            try:
                d = datetime.strptime(os.path.splitext(bnm(sl))[0][-8:], '%Y%m%d')
                sitelogs_dates.append(d)
            except ValueError as e:
                logger.error("bad date in sitelog's filename: %s",sl)
                raise e                
        # We get the max date and put it back to string format.
        maxdate = max(sitelogs_dates).strftime('%Y%m%d')
        # We filter the list with the max date string, and get a one entry list, then transform it to string
        sta_sitelog = [sl for sl in sta_sitelogs if maxdate in os.path.splitext(bnm(sl))[0][-8:]][0]

        latest_sitelogs_filepaths.append(sta_sitelog)

    return latest_sitelogs_filepaths


def metadata_find_site(rnxobj_or_site4char, metadata_obj_list, force):
    """
    Finding the right MetaData object

    If is list, can not use force.
    If no metadata found, do not process.
    """
    if type(rnxobj_or_site4char) is str:
        rnx_4char = rnxobj_or_site4char[:4]
        err_label = rnxobj_or_site4char
    else:
        rnx_4char = rnxobj_or_site4char.get_site(True, True)
        err_label = rnxobj_or_site4char.filename

    logger.debug('Searching corresponding metadata for site : ' + rnx_4char)

    if rnx_4char not in [sl.site4char for sl in metadata_obj_list]:
        if len(metadata_obj_list) == 1:
            if not force:
                logger.error('{:110s} - {}'.format(
                    '33 - RINEX name\'s site does not correspond to provided metadata - use -f option to force',
                    err_label))
                raise RinexModInputArgsError
            else:
                logger.warning('{:110s} - {}'.format(
                    '34 - RINEX name\'s site does not correspond to provided metadata, forced processing anyway',
                    err_label))
        else:
            logger.error(
                '{:110s} - {}'.format('33 - No metadata found for this RINEX', err_label))
            raise RinexModInputArgsError
    else:
        metadataobj = [md for md in metadata_obj_list if md.site4char == rnx_4char][0]
        ## we assume the latest sitelog has been found in sitelogs2metadata_objs

    return metadataobj


def metadataobj_apply_on_rnxobj(rnxobj, metadataobj, ignore=False):
    """
    apply a MetaData object on a RinexFile object
    to modify this RinexFile with the rights metadata
    """
    rnx_4char = rnxobj.get_site(True, True)
    # Site name from the sitelog
    metadata_4char = metadataobj.misc_meta['Four Character ID'].lower()

    if rnx_4char != metadata_4char:
        logger.warning(
            "RINEX and metadata 4 char. codes do not correspond, but I assume you know what you are doing (%s,%s)",
            rnx_4char, metadata_4char)

    # Get rinex header values from sitelog infos and start and end time of the file
    # ignore option is to ignore firmware changes between instrumentation periods.
    metadata_vars, ignored = metadataobj.rinex_metadata_lines(
        rnxobj.start_date, rnxobj.end_date, ignore)

    if not metadata_vars:
        logger.error('{:110s} - {}'.format(
            '35 - No instrumentation corresponding to the RINEX epoch', rnxobj.filename))
        raise MetaDataError

    if ignored:
        logger.warning('{:110s} - {}'.format(
            '36 - Instrumentation comes from merged metadata periods with different firmwares, processing anyway',
            rnxobj.filename))

    (fourchar_id, domes_id, observable_type, agencies, receiver,
     antenna, antenna_pos, antenna_delta) = metadata_vars

    # # Apply the modifications to the RinexFile object
    rnxobj.mod_marker(fourchar_id, domes_id)
    rnxobj.mod_receiver(**receiver)
    rnxobj.mod_interval(rnxobj.sample_rate_numeric)
    rnxobj.mod_antenna(**antenna)
    rnxobj.mod_antenna_pos(**antenna_pos)
    rnxobj.mod_antenna_delta(**antenna_delta)
    rnxobj.mod_agencies(**agencies)
    rnxobj.mod_sat_system(observable_type)

    return rnxobj


# *****************************************************************************
# modification keyword dictionary functions

def _modif_kw_check(modif_kw):
    """
    Check if acceptable modification keywords have been provided

    Raise a RinexModInputArgsError Exception if not
    """
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
                           'sat_system',
                           'observables',
                           'interval',
                           'filename_data_freq',
                           'filename_file_period',
                           'filename_data_source',
                           'filename_data_type',
                           'comment']

    for kw in modif_kw:
        if kw not in acceptable_keywords:
            logger.error('{}\' is not an acceptable keyword for header modification.'.format(kw))
            return RinexModInputArgsError

    return None


def modif_kw_apply_on_rnxobj(rinexfileobj, modif_kw):
    """
    apply a modification keywords on a RinexFile object
    to modify this RinexFile with the rights metadata
    """

    def __keys_in_modif_kw(keys_in):
        return all([e in modif_kw.keys() for e in keys_in])

    rinexfileobj.mod_marker(modif_kw.get('marker_name'),
                            modif_kw.get('marker_number'))

    # legacy keyword, 'marker_name' should be used instead
    rinexfileobj.mod_marker(modif_kw.get('station'))

    rinexfileobj.mod_receiver(modif_kw.get('receiver_serial'),
                              modif_kw.get('receiver_type'),
                              modif_kw.get('receiver_fw'))

    rinexfileobj.mod_antenna(modif_kw.get('antenna_serial'),
                             modif_kw.get('antenna_type'))

    rinexfileobj.mod_antenna_pos(modif_kw.get('antenna_X_pos'),
                                 modif_kw.get('antenna_Y_pos'),
                                 modif_kw.get('antenna_Z_pos'))

    rinexfileobj.mod_antenna_delta(modif_kw.get('antenna_H_delta'),
                                   modif_kw.get('antenna_E_delta'),
                                   modif_kw.get('antenna_N_delta'))

    rinexfileobj.mod_agencies(modif_kw.get('operator'),
                              modif_kw.get('agency'))

    rinexfileobj.mod_sat_system(modif_kw.get('sat_system'))
    # legacy keyword, 'sat_system' should be used instead
    rinexfileobj.mod_sat_system(modif_kw.get('observables'))

    rinexfileobj.mod_interval(modif_kw.get('interval'))

    # for the filename
    rinexfileobj.mod_filename_file_period(
        modif_kw.get('filename_file_period'))
    rinexfileobj.mod_filename_data_freq(
        modif_kw.get('filename_data_freq'))
    rinexfileobj.mod_filename_data_source(
        modif_kw.get('filename_data_source'))
    rinexfileobj.mod_filename_data_type(
        modif_kw.get('filename_data_type'))

    # comment
    rinexfileobj.add_comment(modif_kw.get('comment'))

    return rinexfileobj


# *****************************************************************************
# dictionnary as output for gnss_delivery workflow

def _return_lists_maker(rnxobj_or_dict, return_lists=dict()):
    """
    Construct the so called ``return_lists`` (which are actually dictionnaries)

    return_lists have the structure:

    ```
    return_lists[major_rinex_version][sample_rate_string][file_period]
    ```

    the input ``return_lists`` is populated with the content of the input
    ``rnxobj_or_dict``

    Parameters
    ----------
    rnxobj_or_dict : RinexFile object or dict

        The input new information which will populate the return_lists

        if a dict is provided, we assume it is a singleton with a standard
        return_lists structure to be merged in a bigger return_lists

    return_lists : dict, optional
        A potential pre-exisiting return_lists.
        Per default it is a brand new return_lists for scratch.
        The default is dict().

    Returns
    -------
    return_lists : dict
        The input return_lists populated with the input rnxobj_or_dict.

    Note
    ----
    Specific usage for the IPGP's gnss_delivery workflow

    """

    if type(rnxobj_or_dict) is rimo_rnx.RinexFile:
        rnxobj = rnxobj_or_dict
        major_rinex_version = rnxobj.version[0]
        sample_rate_string = rnxobj.sample_rate_string
        file_period = rnxobj.file_period
        path_output = rnxobj.path_output
    elif type(rnxobj_or_dict) is dict:
        rtrnlst = rnxobj_or_dict
        major_rinex_version = list(rtrnlst.keys())[0]
        sample_rate_string = list(rtrnlst[major_rinex_version].keys())[0]
        file_period = list(rtrnlst[major_rinex_version][sample_rate_string].keys())[0]
        path_output = rtrnlst[major_rinex_version][sample_rate_string][file_period][0]
    else:
        logger.error("Wrong Input, must be RinexFile object or dict. Input given: %s, %s",
                     rnxobj_or_dict, type(rnxobj_or_dict))
        raise ReturnListError

    # Dict ordered as : RINEX_VERSION, SAMPLE_RATE, FILE_PERIOD
    if major_rinex_version not in return_lists:
        return_lists[major_rinex_version] = {}
    if sample_rate_string not in return_lists[major_rinex_version]:
        return_lists[major_rinex_version][sample_rate_string] = {}
    if file_period not in return_lists[major_rinex_version][sample_rate_string]:
        return_lists[major_rinex_version][sample_rate_string][file_period] = []

    return_lists[major_rinex_version][sample_rate_string][file_period].append(path_output)

    return return_lists


def _return_lists_write(return_lists, logfolder, now_dt=None):
    # Writing an output file for each RINEX_VERSION, SAMPLE_RATE, FILE_PERIOD lists
    if not now_dt:
        now_dt = datetime.now()

    for rinex_version in return_lists:
        for sample_rate in return_lists[rinex_version]:
            for file_period in return_lists[rinex_version][sample_rate]:
                this_outputfile = '_'.join(
                    ['RINEX' + rinex_version, sample_rate, file_period, datetime.strftime(now_dt, '%Y%m%d%H%M'),
                     'delivery.lst'])
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
             verbose=True, full_history=False, tolerant_file_period=False,
             return_lists=None, station_info=None, lfile_apriori=None,
             force_fake_coords=False):
    """
    Parameters
    ----------
    rinexfile : str
        Input RINEX file to process.
    outputfolder : str
        Folder where to write the modified RINEX files.
    sitelog : str, list of str, MetaData object, list of MetaData objects, optional
        Get the RINEX header values from a sitelog.
        Possible inputs are:
         * list of string (sitelog file paths),
         * single string (single sitelog file path or directory containing the sitelogs),
         * list of MetaData object
         * single MetaData object
        The function will search for the latest and right sitelog
        corresponding to the site.
        One can force a single sitelog with force_sitelog.
        The default is None.
    modif_kw : dict, optional
        Modification keywords for RINEX's header fields and/or filename.
        Will override the information from the sitelog.
        Acceptable keywords for the header fields:
         * comment
         * marker_name
         * marker_number
         * station (legacy alias for marker_name)
         * receiver_serial
         * receiver_type
         * receiver_fw
         * antenna_serial
         * antenna_type
         * antenna_X_pos
         * antenna_Y_pos
         * antenna_Z_pos
         * antenna_H_delta
         * antenna_E_delta
         * antenna_N_delta
         * operator
         * agency
         * sat_system (M, G, R, E, C...)
         * observables (legacy alias for sat_system)
         * interval
        Acceptable keywords for the filename:
         * filename_file_period (01H, 01D...)
         * filename_data_freq (30S, 01S...)
         * filename_data_source (R, S, U)
        The default is dict().
    marker : str, optional
        A four or nine character site code that will be used to rename
        input files.
        Apply also to the header's MARKER NAME,
        but a custom modification keyword marker_name='XXXX' overrides it
        (modif_kw argument below)
        The default is ''.
    longname : bool, optional
        Rename file using long name RINEX convention (force gzip compression).
        The default is False.
    force_rnx_load : bool, optional
        Force the loading of the input RINEX. Useful if its name is not standard.
        The default is False.
    force_sitelog : bool, optional
        If a single sitelog is provided, force sitelog-based header 
        values when RINEX's header and sitelog site name do not correspond.
        If several sitelogs are provided, skip badly-formated sitelogs.
        The default is False.
    ignore : bool, optional
        Ignore firmware changes between instrumentation periods
        when getting header values info from sitelogs. The default is False.
    ninecharfile : str, optional
        Path of a file that contains 9-char. site names from the M3G database.
        The default is None.
    compression : str, optional
        Set RINEX compression
        acceptable values : gz (recommended to fit IGS standards), 'Z', None.
        The default is None.
    relative : str, optional
        Reconstruct files relative subfolders.
        You have to indicate the common parent folder,
        that will be replaced with the output folder. The default is ''.
    verbose : bool, optional
        set the level of verbosity
        (False for the INFO level, True for the DEBUG level).
        The default is True.
    full_history : bool, optional
        Add the full history of the station in
        the RINEX's header as comment.
    tolerant_file_period : bool, optional
        If True, the RINEX file period is tolerant and stick to
        the actual data content, but then can be odd (e.g. 07H, 14H...).
        If False, A strict file period is applied per default (01H or 01D),
        being compatible with the IGS conventions.
        The default is False.
    return_lists : dict, optional
        Specific option for file distribution through a GLASS node.
        Store the rinexmoded RINEXs in a dictionary
        to activates it, give a dict as input (an empty one - dict() works)
        The default is None.
    station_info: str, optional
        Path of a GAMIT station.info file to obtain GNSS site
        metadata information (needs also lfile_apriori option)
    lfile_apriori: str, optional
        Path of a GAMIT apriori apr/L-File to obtain GNSS site
        position and DOMES information (needs also station_info option)
    force_fake_coords: bool, optional
        When using GAMIT station.info metadata without apriori coordinates
        in the L-File, gives fake coordinates at (0°,0°) to the site

    Raises
    ------
    RinexModInputArgsError
        Something is wrong with the input arguments.
    RinexFileError
        Something is wrong with the input RINEX File.

    Returns
    -------
    outputfile : str
        the path of the rinexmoded RINEX

    OR

    return_lists : dict
        a dictionary of rinexmoded RINEXs for GLASS distribution.
    """

    now = datetime.now()

    if verbose:
        logger = rimo_log.logger_define('DEBUG',
                                        logfile=None,
                                        level_logfile='DEBUG')
    else:
        logger = rimo_log.logger_define('INFO',
                                        logfile=None,
                                        level_logfile='INFO')

    logger.info('# File : %s', rinexfile)

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

    if not modif_kw:
        modif_kw = dict()

    if os.path.abspath(os.path.dirname(rinexfile)) == myoutputfolder:
        logger.error(
            '{:110s} - {}'.format('30 - Input and output folders are the same !', rinexfile))
        raise RinexFileError

    if not os.path.exists(outputfolder):
        logger.warning("the output folder does not exists")
        os.makedirs(outputfolder)

    ###########################################################################
    ########## Open the rinex file as an object
    rnxobj = rimo_rnx.RinexFile(rinexfile, force_rnx_load=force_rnx_load)

    if rnxobj.status:
        logger.error('{:110s} - {}'.format(rnxobj.status, rinexfile))
        raise RinexFileError

    logger.debug('RINEX Origin Metadata :\n' + rnxobj.get_metadata()[0])

    # apply tolerant / strict (per default) file period
    if not tolerant_file_period:
        rnxobj.get_file_period_round(inplace_set=True)

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

    # set the marker as Rinex site, if any
    # This preliminary set_site is for th research of the right sitelog
    # a second set_site will take place a just after
    if marker:
        # We store the old site name to add a comment in rinex file's header
        ## modif_marker = rnxobj.get_site(True,False) ### Useless...
        rnxobj.set_site(marker)

    ### load the metadata from sitelog or GAMIT files if any
    ## sitelogs
    if sitelog:
        metadata_obj_list = sitelog_input_manage(sitelog,
                                                 force=force_sitelog)
    ## GAMIT files
    # We read the GAMIT files only if no input 'sitelog' variable is given.
    # Indeed, the GAMIT files might have been read outside this function
    # (most likely actually). The already read GAMIT files are then stored
    # in the 'sitelog' variable as a list of MetaData objects
    if (station_info and lfile_apriori) and not sitelog:
        metadata_obj_list = gamit2metadata_objs(station_info,
                                                lfile_apriori,
                                                force_fake_coords=force_fake_coords)

    ### find the right MetaData object corresponding to the RINEX
    if sitelog or (station_info and lfile_apriori):
        metadataobj = metadata_find_site(rnxobj,
                                         metadata_obj_list,
                                         force=force_sitelog)
        logger.debug("metadata used: %s", metadataobj)
    else:
        metadataobj = None

    ###########################################################################
    ########## Handle the similar options to set the site code
    ### Priority for the Country source
    # 1) the marker option if 9 char are given
    # 2) the nine_char_dict from the ninecharfile option
    # 3) the MetaData object (most useful actually),
    #    but we maintain a fallback mechanism here if the sitelog is wrong
    # 4) last chance: test if the country code we get from the input 9-char
    #    code is not XXX. If so, we keep it
    # Finally, set default value for the monument & country codes

    rnx_4char = rnxobj.get_site(True, True)
    rnx_9char = rnxobj.get_site(False, False)

    if marker and len(marker) == 9:
        monum = marker[4:6]
        country = marker[6:]
    elif ninecharfile:
        if not rnx_4char in nine_char_dict:
            logger.warning('32 - Site\'s missing in the input 9-char. file: %s', rinexfile)
        else:
            monum = nine_char_dict[rnx_4char].upper()[4:6]
            country = nine_char_dict[rnx_4char].upper()[6:]
    elif metadataobj:
        monum = "00"
        country = metadataobj.get_country()
    elif rnx_9char[6:] != 'XXX':
        monum = rnx_9char[4:6]
        country = rnx_9char[6:]
    else:
        monum = "00"
        country = "XXX"

    if country == "XXX":
        logger.warning('32 - Site\'s country not retrevied, will not be properly renamed: %s', rinexfile)

    rnxobj.set_site(rnx_4char, monum, country)

    ###########################################################################
    ########## Remove previous comments
    if metadataobj or modif_kw or (station_info and lfile_apriori):
        rnxobj.clean_rinexmod_comments(clean_history=True)

    ###########################################################################
    ########## Apply the MetaData object on the RinexFile object
    if metadataobj:
        rnxobj = metadataobj_apply_on_rnxobj(rnxobj, metadataobj, ignore=ignore)
        logger.debug('RINEX Sitelog-Modified Metadata :\n' + rnxobj.get_metadata()[0])
        modif_source_metadata = metadataobj.filename

    ###########################################################################
    ########## Apply the modif_kw dictionnary on the RinexFile object
    if modif_kw:
        # Checking input keyword modification arguments
        _modif_kw_check(modif_kw)

        modif_source_kw = 'keywords:' + " ".join(modif_kw.keys())
        rnxobj = modif_kw_apply_on_rnxobj(rnxobj, modif_kw)
        logger.debug('RINEX Manual Keywords-Modified Metadata :\n' + rnxobj.get_metadata()[0])

    ###########################################################################
    ########## Apply the site as the MARKER NAME within the RINEX
    # Must be after metadataobj_apply_on_rnxobj and modif_kw_apply_on_rnxobj
    # apply only is modif_kw does not overrides it (it is the overwhelming case)
    if "marker_name" not in modif_kw.keys():
        rnxobj.mod_marker(rnxobj.get_site(False, False, True))

    ###########################################################################
    ########## Correct the first and last time obs
    rnxobj.mod_time_obs(rnxobj.start_date, rnxobj.end_date)

    ###########################################################################
    ########## Add comment in the header
    vers_num = git_get_revision_short_hash()
    # rnxobj.add_comment(("RinexMod (IPGP)","METADATA UPDATE"),add_pgm_cmt=True)
    rnxobj.add_comment(("RinexMod " + vers_num, "METADATA UPDATE"),
                       add_pgm_cmt=True)
    rnxobj.add_comment('RinexMod / IPGP-OVS (github.com/IPGP/rinexmod)')
    rnxobj.add_comment('rinexmoded on {}'.format(
        datetime.strftime(now, '%Y-%m-%d %H:%M')))
    if metadataobj:
        rnxobj.add_comment('rinexmoded with {}'.format(modif_source_metadata))
    if modif_kw:
        rnxobj.add_comment('rinexmoded with {}'.format(modif_source_kw))
    # if marker: ##### Useless...
    #    rnxobj.add_comment('filename assigned from {}'.format(modif_marker))

    ###########################################################################
    ########## Write the station history in the header
    if metadataobj and full_history:
        title = ["- - - - - - - - - - - -", "SITE FULL HISTORY"]
        rnxobj.add_comments(title + metadataobj.rinex_full_history_lines())

    ###########################################################################
    ########## Sort the header
    rnxobj.sort_header()

    ###########################################################################
    ########## we regenerate the filenames
    if rnxobj.name_conv == "SHORT" and not longname:
        rnxobj.get_shortname(inplace_set=True, compression='',
                             tolerant_file_period=tolerant_file_period)
    else:
        rnxobj.get_longname(inplace_set=True, compression='',
                            tolerant_file_period=tolerant_file_period,
                            data_source=rnxobj.data_source)

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
        outputfile = rnxobj.write_to_path(myoutputfolder,
                                          compression=output_compression)
        logger.info('Output file : ' + outputfile)
    except hatanaka.hatanaka.HatanakaException as e:
        logger.error('{:110s} - {}'.format('06 - File could not be written - hatanaka exception', rinexfile))
        outputfile = None
        raise e

    ###########################################################################
    ########## Construct return dict by adding key if doesn't exists
    ########## and appending file to corresponding list
    if type(return_lists) is dict:
        return_lists = _return_lists_maker(rnxobj, return_lists)
        final_return = return_lists
    else:
        ###########################################################################
        ###### if no return dict  given, return simply the path of the outputfile
        final_return = outputfile

    return final_return


# *****************************************************************************
# Upper level rinexmod for a Console run

def rinexmod_cli(rinexinput, outputfolder, sitelog=None, modif_kw=dict(), marker='',
                 longname=False, force_sitelog=False, force_rnx_load=False, ignore=False,
                 ninecharfile=None, compression=None, relative='', verbose=True,
                 alone=False, output_logs=None, write=False, sort=False, full_history=False,
                 tolerant_file_period=False, multi_process=1, debug=False, station_info=None,
                 lfile_apriori=None, force_fake_coords=False):
    """
    Main function for reading a Rinex list file. It process the list, and apply
    file name modification, command line based header modification, or sitelog-based
    header modification.
    
    Optimized for a CLI (in a Terminal usage) but can be used also in a 
    stand-alone API mode.
    
    For a detailled description, check the help of the lower level 
    `rinexmod` function or the help of the frontend CLI function in a Terminal
    
    Parameters
    ----------
    rinexinput : list or str
        a filepath of a textfile containing a RINEX paths list 
        or directly a Python list of RINEX paths
    """

    # If no longname, modif_kw and sitelog, return
    if not sitelog and not modif_kw and not marker and not longname and not station_info and not lfile_apriori:
        logger.critical(
            'No action asked, provide at least one of the following args : --sitelog, --modif_kw, --marker, --longname, --station_info, --lfile_apriori')
        raise RinexModInputArgsError

    # If force option provided, check if sitelog option too, if not, not relevant.
    if force_sitelog and not sitelog:
        logger.critical(
            '--force option is relevant only when --sitelog option with a **single** sitelog is also provided')
        raise RinexModInputArgsError

    # If ignore option provided, check if sitelog option too, if not, not relevant.
    if ignore and not sitelog:
        logger.critical('--ignore option is relevant only when using also --sitelog option')
        raise RinexModInputArgsError

    if ninecharfile and not longname:
        logger.critical('--ninecharfile option is relevant only when using also --longname option')
        raise RinexModInputArgsError

    if (station_info and not lfile_apriori) or (not station_info and lfile_apriori):
        logger.critical('--station_info and --lfile_apriori must be provided together')
        raise RinexModInputArgsError

    if station_info and lfile_apriori and sitelog:
        logger.critical('both sitelogs and GAMIT files given as metadata input. Managing both is not implemented yet')
        raise RinexModInputArgsError

    # If inputfile doesn't exists, return
    if isinstance(rinexinput, list):
        pass
    elif not os.path.isfile(rinexinput):
        logger.critical('The input file doesn\'t exist : ' + rinexinput)
        raise RinexModInputArgsError

    if output_logs and not os.path.isdir(output_logs):
        logger.critical('The specified output folder for logs doesn\'t exist : ' + output_logs)
        raise RinexModInputArgsError

    outputfolder = os.path.abspath(outputfolder)
    if not os.path.isdir(outputfolder):
        # mkdirs ???
        os.makedirs(outputfolder)

    # Creating log file
    now = datetime.now()
    nowstr = datetime.strftime(now, '%Y%m%d%H%M%S')

    if output_logs:
        logfolder = output_logs
    else:
        logfolder = outputfolder

    logfile = os.path.join(logfolder, nowstr + '_' + 'rinexmod_errors.log')
    if verbose:
        _ = rimo_log.logger_define('DEBUG', logfile, 'DEBUG')
    else:
        _ = rimo_log.logger_define('INFO', logfile, 'INFO')

    # Opening and reading lines of the file containing list of rinex to proceed
    if alone:
        rinexinput = [rinexinput]
    elif isinstance(rinexinput, list):
        pass
    else:
        try:
            rinexinput = [line.strip() for line in open(rinexinput).readlines()]
        except:
            logger.error('The input file is not a list : ' + rinexinput)
            return RinexModInputArgsError

    # sort the RINEX list
    if sort:
        rinexinput.sort()

    ### load the sitelogs/GAMIT-files as a **list of MetaData objects**
    # from sitelogs 
    if sitelog:
        sitelogs_list_use = sitelog_input_manage(sitelog, force_sitelog)
    # from GAMIT files
    if station_info and lfile_apriori:
        sitelogs_list_use = gamit2metadata_objs(station_info, lfile_apriori,
                                                force_fake_coords=force_fake_coords)

    ### Looping in file list ###
    return_lists = dict()
    ####### Iterate over each RINEX
    rinexmod_kwargs_list = []
    for rnx in rinexinput:
        rnxmod_kwargs = {"rinexfile": rnx,
                         "outputfolder": outputfolder,
                         "sitelog": sitelogs_list_use,
                         "modif_kw": modif_kw,
                         "marker": marker,
                         "longname": longname,
                         "force_rnx_load": force_rnx_load,
                         "force_sitelog": force_sitelog,
                         "ignore": ignore,
                         "ninecharfile": ninecharfile,
                         "compression": compression,
                         "relative": relative,
                         "verbose": verbose,
                         "return_lists": return_lists,
                         "full_history": full_history,
                         "tolerant_file_period": tolerant_file_period,
                         "station_info": station_info,
                         "lfile_apriori": lfile_apriori,
                         "force_fake_coords": force_fake_coords}

        rinexmod_kwargs_list.append(rnxmod_kwargs)

    global rinexmod_mp_wrapper

    def rinexmod_mp_wrapper(rnxmod_kwargs_inp):
        try:
            return_lists_out = rinexmod(**rnxmod_kwargs_inp)
            return return_lists_out
        except Exception as e:
            if debug:  ### set as True for debug mode
                raise e
            else:
                logger.error("%s raised, RINEX is skiped: %s", type(e).__name__,
                             rnxmod_kwargs_inp["rinexfile"])

    # number of parallel processing
    if multi_process > 1:
        logger.info("multiprocessing: %d cores used", multi_process)
    Pool = mp.Pool(processes=multi_process)
    results_raw = [Pool.apply_async(rinexmod_mp_wrapper, args=(x,)) for x in rinexmod_kwargs_list]
    results = [e.get() for e in results_raw]

    for return_lists_mono in results:
        try:
            _return_lists_maker(return_lists_mono, return_lists)
        except ReturnListError:
            logger.warning("one file has been skipped because of an odd individual return list")
            continue

    #########################################
    logger.handlers.clear()

    if write:
        _return_lists_write(return_lists, logfolder, now)

    return return_lists

# *****************************************************************************
