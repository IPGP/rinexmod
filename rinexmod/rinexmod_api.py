#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API functions of RinexMod

Created on Wed Mar  8 12:14:54 2023

@author: psakic
"""

import argparse
import multiprocessing as mp
import os
import re
import subprocess
from datetime import datetime

import hatanaka
import pandas as pd

import rinexmod as rimo
import rinexmod.gamit_meta as rimo_gmm
import rinexmod.logger as rimo_log
import rinexmod.metadata as rimo_mda
import rinexmod.rinexfile as rimo_rnx

logger = rimo_log.logger_define("INFO")


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


def listfiles(directory, extension, recursive=True):
    # returns list of paths
    liste = []
    extension = extension.lower()
    for dirpath, dirnames, files in os.walk(directory):
        for name in files:
            if name.lower().endswith(extension):
                file = os.path.join(dirpath, name)
                liste.append(file)
        if not recursive:
            break
    return list(sorted(liste))


# get Git hash (to get a version number-equivalent of the RinexMod used)
def get_git_hash():
    """
    Gives the Git hash to have a tracking of the used version

    Returns
    -------
    7 characters Git hash
    """
    script_path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

    cmd = ["git", "--git-dir", script_path + "/.git", "rev-parse", "--short", "HEAD"]
    try:
        githash = (
            subprocess.check_output(cmd, stderr=subprocess.DEVNULL)
            .decode("ascii")
            .strip()[:7]
        )
    except Exception:
        # logger.warn("unable to get the git commit version")
        githash = "xxxxxxx"

    ####NB: 2msec to run this fuction
    return githash


def make_site_id9(site_id_inp):
    """
    Converts a site ID to a 9-character format.

    This function takes a site ID and converts it to a 9-character format.
    If the input site ID is already 9 characters long, it returns the uppercase version of the input.
    If the input site ID is 4 characters long, it appends '00XXX' to the uppercase version of the input.
    Otherwise, it takes the first 4 characters of the input, converts them to uppercase, and appends '00XXX'.

    Parameters
    ----------
    site_id_inp : str
        The input site ID to be converted.

    Returns
    -------
    str
        The site ID in 9-character format.
    """
    if len(site_id_inp) == 9:
        return site_id_inp.upper()
    elif len(site_id_inp) == 4:
        return site_id_inp.upper() + "00XXX"
    else:
        return site_id_inp[:4].upper() + "00XXX"


# *****************************************************************************
# Metadata import


def metadata_input_manage(sitelog_inp, force=False):
    """
    Manage the multiple types possible for metadata inputs
    Return a list of MetaData to be handeled by find_mda4site

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
        list of MetaData objects.
        (can be a singleton)

    """
    # single MetaData object
    if isinstance(sitelog_inp, rimo_mda.MetaData):
        return [sitelog_inp]
    # list of MetaData objects
    elif isinstance(sitelog_inp, list) and isinstance(
        sitelog_inp[0], rimo_mda.MetaData
    ):
        return sitelog_inp
    # single string or list of string
    elif isinstance(sitelog_inp, str) or isinstance(sitelog_inp, list):
        return sitlgs2mda_objs(
            sitelog_inp, force=force, return_list_even_if_single_input=True
        )
    else:
        logger.error(
            "Wrong Input, must be a list of string (path), a single string (path),"
            "a MetaData object, or a list of MetaData objects. Input given: %s, %s",
            sitelog_inp,
            type(sitelog_inp),
        )
        raise RinexModInputArgsError


def gamit2mda_objs(
    station_info_inp,
    lfile_inp=None,
    force_fake_coords=False,
    ninecharfile_inp=None,
    rev=False,
):
    """
    Read a GAMIT files and convert their content to MetaData objects

    Parameters
    ----------
    station_info_inp : str or pd.DataFrame
        Path of a GAMIT station.info file to obtain
        GNSS site metadata information.
    lfile_inp : str or pd.DataFrame
        Path of a GAMIT apriori apr/L-File to obtain
        GNSS site position and DOMES information.
    force_fake_coords : bool, optional
        hen using GAMIT station.info metadata without apriori coordinates in
        the L-File, gives fake coordinates at (0°,0°) to the site.
        The default is False.
    ninecharfile_inp : str, optional
        Path of a file that contains 9-char. site names.
        The default is None.
    rev : bool, optional
        reverse order of inputs for station.info filled from the
        newest to the oldest change
        (Automatic sort of the station.info file as DataFrame
         is then disabled)
        The default is False.

    Returns
    -------
    mdaobjs_lis : list
        list of MetaData objects.

    """
    if isinstance(station_info_inp, pd.DataFrame):
        df_stinfo_raw = station_info_inp
        stinfo_name = "station.info"
    else:
        df_stinfo_raw = rimo_gmm.read_gamit_station_info(
            station_info_inp, sort=False
        )  # sort = not rev if rev, no sort
        stinfo_name = os.path.basename(station_info_inp)

    if not lfile_inp:
        df_apr = pd.DataFrame(columns=["site"])
        logger.warning(
            "No L-File provided, fake coordinates will be used! "
            "(force_fake_coords forced to True)"
        )
        force_fake_coords = True
    elif isinstance(lfile_inp, pd.DataFrame):
        df_apr = lfile_inp
    else:
        df_apr = rimo_gmm.read_gamit_apr_lfile(lfile_inp)

    if not ninecharfile_inp is None:
        nine_char_dict = rimo.rinexmod_api.read_ninecharfile(ninecharfile_inp)
    else:
        nine_char_dict = dict()

    sites_isin = df_stinfo_raw["site"].isin(df_apr["site"])
    ### for the stats only
    sites_uniq = pd.Series(df_stinfo_raw["site"].unique())
    sites_isin_uniq = sites_uniq.isin(df_apr["site"].unique())
    n_sites_notin = len(sites_uniq) - sum(sites_isin_uniq)

    if n_sites_notin > 0 and not force_fake_coords:
        logger.warning(
            "%i/%i sites in %s are not in apr/lfile. They are skipped (you can force fake coords with -fc)",
            n_sites_notin,
            len(sites_uniq),
            stinfo_name,
        )
        df_stinfo = df_stinfo_raw[sites_isin]
    elif n_sites_notin > 0 and force_fake_coords:
        logger.warning(
            "%i/%i sites in %s are not in apr/lfile. Fake coords at (0°,0°) used",
            n_sites_notin,
            len(sites_uniq),
            stinfo_name,
        )
        df_stinfo = df_stinfo_raw
    else:  #### no missing coords, n_sites_notin == 0
        df_stinfo = df_stinfo_raw

    df_stinfo_grp = df_stinfo.groupby("site")

    mdaobjs_lis = []

    logger.info("%i sites will be extracted from %s", len(df_stinfo_grp), stinfo_name)

    for site, site_info in df_stinfo_grp:
        logger.debug("extract %s from %s", site, stinfo_name)

        #### search in ninecharfile IMPROVE ME !!!
        if site in nine_char_dict.keys():
            site_use = nine_char_dict[site]
            logger.debug("4 > 9 char. conversion: %s > %s", site, site_use)
        else:
            site_use = site

        mdaobj = rimo_mda.MetaData(sitelogfile=None)
        mdaobj.set_from_gamit(
            site_use,
            df_stinfo,
            df_apr,
            force_fake_coords=force_fake_coords,
            station_info_name=stinfo_name,
        )
        if rev:
            mdaobj.instrus.reverse()
            logger.info("Reversing order of instrumental changes")
        mdaobjs_lis.append(mdaobj)

    logger.info("%i sites have been extracted from %s", len(mdaobjs_lis), stinfo_name)

    return mdaobjs_lis


def sitlgs2mda_objs(
    sitelog_filepath, force=False, return_list_even_if_single_input=True
):
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
    mdaobjs_lis : list
        list of MetaData objects.

    """

    #### differenciating cases
    # Case of a list of sitelogs
    if type(sitelog_filepath) is list:
        slgs_all = sitelog_filepath
        sitelog_filepath = "input sitelog list"
    # Case of one single sitelog
    elif os.path.isfile(sitelog_filepath):
        slgs_all = [sitelog_filepath]
    # Case of a folder
    elif os.path.isdir(sitelog_filepath):
        sitelog_extension = ".log"
        slgs_all = listfiles(sitelog_filepath, sitelog_extension)

        sitelog_pattern = re.compile(r"\w{4,9}_\d{8}.log")
        slgs_all = [f for f in slgs_all if sitelog_pattern.match(os.path.basename(f))]
    ### case of no file nor folder
    else:
        logger.error(
            "unable to handle file/directory. Does it exists?: %s", sitelog_filepath
        )
        raise RinexModInputArgsError

    #### Read the sitelogs
    logger.info("**** %i sitelogs detected (in %s)", len(slgs_all), sitelog_filepath)
    for sl in slgs_all:
        logger.debug(sl)
    # Get last version of sitelogs if multiple available
    # (1st gross search based on date in filename)
    slgs_latest = _slg_find_latest_name(slgs_all)
    # load the sitelogs as metadata objects
    mdaobjs_lis, slgs_bad_lis = load_sitelogs(slgs_latest, force)
    # Get last version of sitelogs if multiple available
    # (2nd fine search based on date in "Date Prepared" field)
    mdaobjs_lis = _mda_find_latest_prep(mdaobjs_lis)

    logger.info("**** %i most recent sitelogs selected", len(mdaobjs_lis))

    for sl in mdaobjs_lis:
        logger.debug(sl.path)

    if len(slgs_bad_lis) > 0:
        logger.warning("**** %i badly-parsed & ignored sitelogs", len(slgs_bad_lis))

    if len(mdaobjs_lis) <= 1 and not return_list_even_if_single_input:
        mdaobjs_lis = mdaobjs_lis[0]

    return mdaobjs_lis


def rinexs2mda_objs(rinex_paths, ninecharfile_inp=None):
    """
    Read a set of RINEX files and convert them to MetaData objects

    Parameters
    ----------
    rinex_paths : list of str
        path of a single rinex file or a set of rinex files (stored in a list).

    ninecharfile_inp : str, optional
        Path of a file that contains 9-char. site names.
        The default is None.

    Returns
    -------
    mdaobjs_lis : list
        list of MetaData objects.

    """

    if not isinstance(rinex_paths, list):
        rinex_paths = [rinex_paths]

    if not ninecharfile_inp is None:
        nine_char_dict = read_ninecharfile(ninecharfile_inp)
    else:
        nine_char_dict = dict()

    mda_stk = []
    for rnx in sorted(rinex_paths):
        mda = rimo_mda.MetaData()
        mda.set_from_rinex(rnx)

        #### search in ninecharfile IMPROVE ME !!!
        if mda.site_id9[-3:] == "XXX" and mda.site_id4 in nine_char_dict.keys():
            site_id4_orig = mda.site_id4
            mda.site_id = nine_char_dict[mda.site_id4]
            logger.info(f"4 > 9 char. conversion: {site_id4_orig:} > {mda.site_id9:}")

        mda_stk.append(mda)

    mdaobjs_lis, mdaobj_dic = group_mda(mda_stk)

    return mdaobjs_lis


def group_mda(mdaobj_list_inp):
    """
    Group a list of MetaData objects into a dictionary and return a list and dictionary of merged objects.

    This function processes a list of MetaData objects, grouping them by their `site_id9` attribute.
    If multiple MetaData objects share the same `site_id9`, their instrumentation data is merged.

    Parameters
    ----------
    mdaobj_list_inp : list
        A list of MetaData objects to be grouped.

    Returns
    -------
    mdaobj_lis : list
      A list of grouped MetaData objects.
    mdaobj_dic : dict
        A dictionary where keys are `site_id9` and values are the grouped MetaData objects.
    """
    mdaobj_dic = dict()  # Initialize an empty dictionary to store grouped MetaData objects.
    for mda in mdaobj_list_inp:
        # Check if the current MetaData object's site_id9 is already in the dictionary.
        if not mda.site_id9 in mdaobj_dic.keys():
            # If not, add it to the dictionary.
            mdaobj_dic[mda.site_id9] = mda
        else:
            # If it exists, merge the instrumentation data from the current object.
            for inst in mda.instrus:
                mdaobj_dic[mda.site_id9].add_instru(
                    inst["receiver"],
                    inst["antenna"],
                    inst["dates"][0],
                    inst["dates"][1],
                )

    # Convert the dictionary values to a list of grouped MetaData objects.
    mdaobj_lis = [v for k, v in mdaobj_dic.items()]

    return mdaobj_lis, mdaobj_dic


def load_sitelogs(sitelogs_inp, force=False):
    """
    Process a list of sitelogs and return a list of MetaData objects and a list of bad sitelogs.

    Parameters
    ----------
    sitelogs_inp : list
        List of paths to the latest sitelog files.
    force : bool, optional
        If True, force processing even if sitelog is not parsable. Default is False.

    Returns
    -------
    mdaobjs_lis : Iterable
        List of MetaData objects.
    bad_sitelogs_lis : Iterable
        List of sitelogs that could not be parsed.
    """

    def _load_slg(sitelog_filepath, force_load):
        # Creating MetaData object
        try:
            mdaobj_load = rimo_mda.MetaData(sitelog_filepath)
        except Exception as e:
            # If sitelog is not parsable
            logger.error(
                "The sitelog is not parsable: %s (%s)",
                os.path.basename(sitelog_filepath),
                str(e),
            )
            if not force_load:
                raise MetaDataError
            else:
                mdaobj_load = None

        return mdaobj_load

    mdaobjs_lis = []
    bad_sitelogs_lis = []
    for sta_sitelog in sitelogs_inp:
        mdaobj = _load_slg(sta_sitelog, force)
        # Appending to list
        if mdaobj:
            mdaobjs_lis.append(mdaobj)
        else:
            bad_sitelogs_lis.append(sta_sitelog)

    return mdaobjs_lis, bad_sitelogs_lis


def _slg_find_latest_name(all_sitelogs_filepaths):
    """
    Find the latest version of a sitelog within a list of sitelogs,
    based on date in its filename
    (mainly for time consumption reduction)

    see also _mda_find_latest_prep (more reliable but slower)
    """
    # We list the available sites to group sitelogs
    bnm = os.path.basename
    sl_bnm = [bnm(sl) for sl in all_sitelogs_filepaths]
    sl_sta = [sl[0:4] for sl in sl_bnm]

    # set the output latest sitelog list
    latest_sitelogs_filepaths = []

    for sta in sl_sta:
        # Grouping by site
        sta_sitelogs = [
            slp for (slp, sln) in zip(all_sitelogs_filepaths, sl_bnm) if sln[0:4] == sta
        ]
        # Getting dates from basename
        # sitelogs_dates0 = [os.path.splitext(bnm(sl))[0][-8:] for sl in sta_sitelogs]
        # Getting dates from basename and parsing 'em
        date_from_fn = lambda x: os.path.splitext(bnm(x))[0][-8:]
        sitelogs_dates = []
        for sl in sta_sitelogs:
            try:
                d = datetime.strptime(date_from_fn(sl), "%Y%m%d")
                sitelogs_dates.append(d)
            except ValueError as e:
                logger.error(
                    f"bad date {date_from_fn(sl):} in sitelog's filename: {sl:}"
                )
                raise e
        # We get the max date and put it back to string format.
        maxdate = max(sitelogs_dates).strftime("%Y%m%d")
        # We filter the list with the max date string, and get a one entry list, then transform it to string
        sta_sitelog = [sl for sl in sta_sitelogs if maxdate in date_from_fn(sl)][0]

        latest_sitelogs_filepaths.append(sta_sitelog)

    return latest_sitelogs_filepaths


def _mda_find_latest_prep(mdaobjs_inp):
    """
    Find the latest version of a MetaData object within a list of MetaData objects,
    based on preparation date

    more reliable than _slg_find_latest_name but requires that the metadata objects have been loaded
    """
    # We list the available sites to group sitelogs
    mdaobjs_lis = mdaobjs_inp
    # mdaobjs_lis = sorted(mdaobjs_lis, key=lambda x: x.misc_meta["date prepared"], reverse=True)

    # set the output latest sitelog list
    mdaobjs_latest = []

    sites_all = list(sorted(list(set([md.site_id4 for md in mdaobjs_lis]))))

    for site in sites_all:
        # Grouping by site
        mdaobjs_site = [m for m in mdaobjs_lis if m.site_id4 == site]
        # Getting dates from basename and parsing 'em
        mdaobjs_site_dates = [m.misc_meta["date prepared"] for m in mdaobjs_site]
        # We get the max date and put it back to string format.
        maxdate = max(mdaobjs_site_dates)
        # We filter the list with the max date string, and get a one entry list, then transform it to string
        mdaobj_latest = [
            md for md in mdaobjs_site if md.misc_meta["date prepared"] == maxdate
        ][0]

        mdaobjs_latest.append(mdaobj_latest)

    return mdaobjs_latest


def find_mda4site(rnxobj_or_site4char, mdaobjs_lis, force):
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

    logger.debug("Searching corresponding metadata for site: " + rnx_4char)

    if len(mdaobjs_lis) == 0:
        logger.warning("The metadata list provided is empty!")

    mdaobj = None
    if rnx_4char not in [mda.site_id4 for mda in mdaobjs_lis]:
        if len(mdaobjs_lis) == 1:
            if not force:
                errmsg = "33 - RINEX name's site does not correspond to provided metadata, use -f option to force"
                logger.error(f"{errmsg:110s} - {err_label:}")
                raise RinexModInputArgsError
            else:
                errmsg = "34 - RINEX name's site does not correspond to provided metadata, forced processing anyway"
                logger.warning(f"{errmsg:110s} - {err_label:}")
        else:
            errmsg = "33 - No metadata found for this RINEX"
            logger.error(f"{errmsg:110s} - {err_label:}")
            raise RinexModInputArgsError
    else:
        mdaobjs_site = [md for md in mdaobjs_lis if md.site_id4 == rnx_4char]
        if len(mdaobjs_site) == 1:
            mdaobj = mdaobjs_site[0]
        else:
            # the assumption that latest sitelog has been found in sitlgs2mda_objs is wrong!
            # a second search with the preparation date is performed here
            mdaobj = _mda_find_latest_prep(mdaobjs_site)[0]

    return mdaobj


def apply_mda2rnxobj(rnxobj, mdaobj, ignore=False, keep_rnx_rec=False):
    """
    apply a MetaData object on a RinexFile object
    to modify this RinexFile with the rights metadata
    """

    ### do this check with 9 chars at one point
    rnx_4char = rnxobj.get_site(True, True)
    # Site name from the sitelog
    mda_4char = mdaobj.site_id4 # misc_meta["ID"].lower()[:4]

    if rnx_4char != mda_4char:
        logger.warning(
            "RINEX and metadata 4 char. codes do not correspond, "
            "but I assume you know what you are doing (%s,%s)",
            rnx_4char,
            mda_4char,
        )

    # Get rinex header values from sitelog infos and start and end time of the file
    # ignore option is to ignore firmware changes between instrumentation periods.
    mda_vars, ignored = mdaobj.rinex_metadata_lines(
        rnxobj.start_date, rnxobj.end_date, ignore
    )

    if not mda_vars:
        logger.error(
            "35 - No instrumentation corresponding to the RINEX epoch - %s",
            rnxobj.filename,
        )
        raise MetaDataError

    if ignored:
        logger.warning(
            "36 - Instrumentation comes from merged metadata periods with different firmwares, processing anyway - %s",
            rnxobj.filename,
        )

    (
        fourchar_id,
        domes_id,
        sat_sys_long_fmt,
        agencies,
        rec,
        antenna,
        ant_pos,
        ant_delta,
    ) = mda_vars

    ## Apply the modifications to the RinexFile object
    rnxobj.mod_marker(fourchar_id, domes_id)
    rnxobj.mod_receiver(keep_rnx_rec=keep_rnx_rec, **rec)
    rnxobj.mod_interval(rnxobj.sample_rate_numeric)
    rnxobj.mod_antenna(**antenna)
    rnxobj.mod_antenna_pos(**ant_pos)
    rnxobj.mod_antenna_delta(**ant_delta)
    rnxobj.mod_agencies(**agencies)
    if not keep_rnx_rec:
        ### if keep_rnx_rec is active, we keep the sat system in the header
        rnxobj.mod_sat_system(sat_sys_long_fmt)

    return rnxobj


# *****************************************************************************
# modification keyword dictionary functions


def _modif_kw_check(modif_kw):
    """
    Check if acceptable modification keywords have been provided

    Raise a RinexModInputArgsError Exception if not
    """

    acceptable_keywords = [
        "station",
        "marker_name",
        "marker_number",
        "receiver_serial",
        "receiver_type",
        "receiver_fw",
        "antenna_serial",
        "antenna_type",
        "antenna_X_pos",
        "antenna_Y_pos",
        "antenna_Z_pos",
        "antenna_H_delta",
        "antenna_E_delta",
        "antenna_N_delta",
        "operator",
        "agency",
        "sat_system",
        "observables",
        "interval",
        "filename_data_freq",
        "filename_file_period",
        "filename_data_source",
        "comment(_[0-9]+)?",
    ]
    ### comment is a regex, bc several comments are possible
    # suffix _N is added by ParseKwargs
    # but comment without suffix must remain possible (for API mode)

    for kw in modif_kw:
        if not any([re.match(akw, kw) for akw in acceptable_keywords]):
            logger.error(
                "'{}' is not an acceptable keyword for header modification.".format(kw)
            )
            return RinexModInputArgsError

    return None


def apply_modifkw2rnxobj(rnxobj, modif_kw):
    """
    apply a modification keywords on a RinexFile object
    to modify this RinexFile with the rights metadata
    """

    def __keys_in_modif_kw(keys_in):
        return all([e in modif_kw.keys() for e in keys_in])

    rnxobj.mod_marker(modif_kw.get("marker_name"), modif_kw.get("marker_number"))

    # legacy keyword, 'marker_name' should be used instead
    rnxobj.mod_marker(modif_kw.get("station"))

    rnxobj.mod_receiver(
        modif_kw.get("receiver_serial"),
        modif_kw.get("receiver_type"),
        modif_kw.get("receiver_fw"),
    )

    rnxobj.mod_antenna(modif_kw.get("antenna_serial"), modif_kw.get("antenna_type"))

    rnxobj.mod_antenna_pos(
        modif_kw.get("antenna_X_pos"),
        modif_kw.get("antenna_Y_pos"),
        modif_kw.get("antenna_Z_pos"),
    )

    rnxobj.mod_antenna_delta(
        modif_kw.get("antenna_H_delta"),
        modif_kw.get("antenna_E_delta"),
        modif_kw.get("antenna_N_delta"),
    )

    rnxobj.mod_agencies(modif_kw.get("operator"), modif_kw.get("agency"))

    rnxobj.mod_sat_system(modif_kw.get("sat_system"))
    # legacy keyword, 'sat_system' should be used instead
    rnxobj.mod_sat_system(modif_kw.get("observables"))

    rnxobj.mod_interval(modif_kw.get("interval"))

    # for the filename
    rnxobj.mod_filename_file_period(modif_kw.get("filename_file_period"))
    rnxobj.mod_filename_data_freq(modif_kw.get("filename_data_freq"))
    rnxobj.mod_filename_data_source(modif_kw.get("filename_data_source"))

    # comment
    # special case: several keys comment_1, comment_2, comment_N are possible
    # number are added automatically by ParseKwargs
    comment_keys = [k for k in modif_kw.keys() if "comment" in k]
    for ck in comment_keys:
        rnxobj.add_comment(modif_kw.get(ck).split("_")[0])

    return rnxobj


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
        Per default it is a brand-new return_lists for scratch.
        The default is dict().

    Returns
    -------
    return_lists : dict
        The input return_lists populated with the input rnxobj_or_dict.

    Note
    ----
    Specific usage for the IPGP's gnss_delivery workflow

    """

    if isinstance(rnxobj_or_dict, rimo_rnx.RinexFile):
        rnxobj = rnxobj_or_dict
        major_rinex_version = rnxobj.version[0]
        sample_rate_string = rnxobj.sample_rate_string
        file_period = rnxobj.file_period
        path_output = rnxobj.path_output
    elif isinstance(rnxobj_or_dict, dict):
        rtrnlst = rnxobj_or_dict
        major_rinex_version = list(rtrnlst.keys())[0]
        sample_rate_string = list(rtrnlst[major_rinex_version].keys())[0]
        file_period = list(rtrnlst[major_rinex_version][sample_rate_string].keys())[0]
        path_output = rtrnlst[major_rinex_version][sample_rate_string][file_period][0]
    else:
        logger.error(
            "Wrong Input, must be RinexFile object or dict. Input given: %s, %s",
            rnxobj_or_dict,
            type(rnxobj_or_dict),
        )
        raise ReturnListError

    # Dict ordered as : RINEX_VERSION, SAMPLE_RATE, FILE_PERIOD
    if major_rinex_version not in return_lists:
        return_lists[major_rinex_version] = {}
    if sample_rate_string not in return_lists[major_rinex_version]:
        return_lists[major_rinex_version][sample_rate_string] = {}
    if file_period not in return_lists[major_rinex_version][sample_rate_string]:
        return_lists[major_rinex_version][sample_rate_string][file_period] = []

    return_lists[major_rinex_version][sample_rate_string][file_period].append(
        path_output
    )

    return return_lists


def _return_lists_write(return_lists, logfolder, now_dt=None):
    # Writing an output file for each RINEX_VERSION, SAMPLE_RATE, FILE_PERIOD lists
    if not now_dt:
        now_dt = datetime.now()

    this_outputfile = ""

    for rinex_version in return_lists:
        for sample_rate in return_lists[rinex_version]:
            for file_period in return_lists[rinex_version][sample_rate]:
                this_outputfile = "_".join(
                    [
                        "RINEX" + rinex_version,
                        sample_rate,
                        file_period,
                        datetime.strftime(now_dt, "%Y%m%d%H%M"),
                        "delivery.lst",
                    ]
                )
                this_outputfile = os.path.join(logfolder, this_outputfile)

                # Writting output to temporary file and copying it them to target files
                with open(this_outputfile, "w") as f:
                    f.writelines(
                        "{}\n".format(line)
                        for line in return_lists[rinex_version][sample_rate][
                            file_period
                        ]
                    )
                    logger.debug("Output rinex list written to " + this_outputfile)

    return this_outputfile


def read_ninecharfile(ninecharfile_inp):
    nine_char_dict = dict()

    if isinstance(ninecharfile_inp, str):
        with open(ninecharfile_inp, "r") as F:
            nine_char_list = F.readlines()
    elif isinstance(ninecharfile_inp, list):
        nine_char_list = ninecharfile_inp
    else:
        nine_char_list = list(ninecharfile_inp)

    for site_key in nine_char_list:
        nine_char_dict[site_key[:4].lower()] = site_key.strip()

    return nine_char_dict


# *****************************************************************************
# Main function


def rinexmod(
    rinexfile,
    outputfolder,
    sitelog=None,
    modif_kw=dict(),
    marker="",
    country="",
    longname=False,
    shortname=False,
    force_rnx_load=False,
    force_sitelog=False,
    ignore=False,
    ninecharfile=None,
    no_hatanaka=False,
    compression="gz",
    relative="",
    verbose=True,
    full_history=False,
    filename_style="basic",
    return_lists=None,
    station_info=None,
    lfile_apriori=None,
    force_fake_coords=False,
    remove=False,
    keep_rnx_rec=False,
):
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
    country : str, optional
        A three character string corresponding to the ISO 3166 Country code
        that will be used to rename input files.
        It overrides other country code sources (sitelog, --marker...)
        list of ISO country codes:
        https://en.wikipedia.org/wiki/List_of_ISO_3166_country_codes
        The default is ''.
    longname : bool, optional
        Force RINEX file renaming with long name convention (force gzip compression).
        Mutually exclusive with shortname.
        The default is False.
    shortname : bool, optional
        Force RINEX file renaming with short name convention.
        Mutually exclusive with longname.
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
    no_hatanaka : bool, optional
        Skip high-level RINEX-specific Hatanaka compression
        (performed per default).
        The default is False.
    compression : str, optional
        Set low-level RINEX file compression.
        acceptable values : 'gz' (recommended to fit IGS standards), 'Z', None.
        The default is 'gz'.
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
    filename_style : str, optional
        Set the RINEX filename style.
        acceptable values : 'basic' (per default), 'flex', 'exact'.
        * 'basic': a simple mode to apply a strict filename period (01H or 01D),
        being compatible with the IGS conventions.
        e.g.: `FNG000GLP_R_20242220000_01D_30S_MO.crx.gz`
        * 'flex': the filename period is tolerant and corresponds to
        the actual data content, but then can be odd (e.g. 07H, 14H...).
        The filename start time is rounded to the hour.
        e.g.: `FNG000GLP_R_20242221800_06H_30S_MO.crx.gz`
        * 'exact': the  filename start time is strictly the one of the
        first epoch in the RINEX.
        Useful for some specific cases needing splicing.
        e.g.: `FNG000GLP_R_20242221829_06H_30S_MO.crx.gz`
        The default is 'basic'.
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
    remove: bool, optional
        Remove input RINEX file if the output RINEX is correctly written
        The default is False.
    keep_rnx_rec: bool, optional
        Keep the RINEX receiver header record in the output RINEX.
        Metadata from the external source (e.g. sitelogs) will not be modded.
        The default is False.

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

    now = datetime.now().astimezone()

    if verbose:
        logger = rimo_log.logger_define("DEBUG", logfile=None, level_logfile="DEBUG")
    else:
        logger = rimo_log.logger_define("INFO", logfile=None, level_logfile="INFO")

    logger.info("# Inp. file: %s", rinexfile)

    if relative:
        if not relative in rinexfile:
            logger.error(
                "{:110s} - {}".format(
                    "31 - The relative subfolder can not be reconstructed for RINEX file",
                    rinexfile,
                )
            )
            raise RinexModInputArgsError

        # We construct the output path with relative path between file name and parameter
        relpath = os.path.relpath(os.path.dirname(rinexfile), relative)
        myoutputfolder = os.path.join(outputfolder, relpath)
        if not os.path.isdir(myoutputfolder):
            os.makedirs(myoutputfolder)
    elif os.path.basename(outputfolder) == "INPUT_FOLDER":
        myoutputfolder = os.path.dirname(rinexfile)
    else:
        myoutputfolder = outputfolder

    if not modif_kw:
        modif_kw = dict()

    if (
        os.path.abspath(os.path.dirname(rinexfile)) == myoutputfolder
        and not outputfolder == "IDEM"
    ):
        logger.error(
            "{:110s} - {}".format(
                "30 - Input and output folders are the same!", rinexfile
            )
        )
        raise RinexFileError

    if outputfolder == "IDEM":
        logger.warning("The output folder is forced as the same one as the input one")

    if not os.path.exists(outputfolder):
        logger.debug("The output folder does not exists, creating it")
        os.makedirs(outputfolder)

    if longname and shortname:
        logger.error("longname and shortname are mutually exclusive")
        raise RinexModInputArgsError

    ###########################################################################
    ########## Open the rinex file as an object
    rnxobj = rimo_rnx.RinexFile(rinexfile, force_rnx_load=force_rnx_load)

    if rnxobj.status:
        logger.error("{:110s} - {}".format(rnxobj.status, rinexfile))
        raise RinexFileError

    logger.debug("RINEX Origin Metadata :\n" + rnxobj.get_header()[0])

    # apply tolerant / strict (per default) file period
    if filename_style == "basic":
        rnxobj.mod_file_period_basic()

    # Check that the provided marker is a 4-char site name
    if marker and (len(marker) != 4 and len(marker) != 9):
        logger.error("The site name provided is not 4 or 9-char valid: " + marker)
        raise RinexModInputArgsError

    # Get the 4 char > 9 char dictionnary from the input list
    nine_char_dict = dict()  # in any case, nine_char_dict is initialized
    if ninecharfile:
        if not os.path.isfile(ninecharfile):
            logger.error(
                "The specified 9-chars. list file does not exists: " + ninecharfile
            )
            raise RinexModInputArgsError

        nine_char_dict = read_ninecharfile(ninecharfile)

    # set the marker as Rinex site, if any
    # This preliminary set_site is for th research of the right sitelog
    # a second set_site will take place a just after with more details
    if marker:
        # We store the old site name to add a comment in rinex file's header
        ## modif_marker = rnxobj.get_site(True,False) ### Useless...
        rnxobj.set_site(marker)

    ## warning if no metadata at all is not provided
    if not sitelog and not modif_kw and (not station_info or not lfile_apriori):
        logger.warning(
            "No sitelog nor keywords nor station.info+lfile provided. "
            "Per default rec.'s header will remain & no new "
            "metdata will be written!"
        )

    # initialize the metadata object list (to avoid linter warning)
    mdaobjs_lis = []
    ## sitelogs
    if sitelog:
        mdaobjs_lis = metadata_input_manage(sitelog, force=force_sitelog)
    ## GAMIT files
    # We read the GAMIT files only if no input 'sitelog' variable is given.
    # Indeed, the GAMIT files might have been read outside this function
    # (most likely actually). The already read GAMIT files are then stored
    # in the 'sitelog' variable as a list of MetaData objects

    if (station_info and not lfile_apriori) or (not station_info and lfile_apriori):
        logger.critical("station_info and lfile_apriori must be provided together")
        raise RinexModInputArgsError

    ### load the metadata from sitelog or GAMIT files if any
    if (station_info and lfile_apriori) and not sitelog:
        mdaobjs_lis = gamit2mda_objs(
            station_info, lfile_apriori, force_fake_coords=force_fake_coords
        )

    ### find the right MetaData object corresponding to the RINEX
    if sitelog or (station_info and lfile_apriori):
        mdaobj = find_mda4site(rnxobj, mdaobjs_lis, force=force_sitelog)
        logger.debug("metadata used: %s", mdaobj)
    else:
        mdaobj = None

    ###########################################################################
    ########## Handle the similar options to set the site code
    ### Priority for the Country source
    # 0) if --country is given it overrides everything,
    #    but at the end of the tests
    # 1) the marker option if 9 char are given
    # 2) the nine_char_dict from the ninecharfile option
    # 3) the MetaData object (most useful actually),
    #    but we maintain a fallback mechanism here if the sitelog is wrong
    # 4) last chance: test if the country code we get from the input 9-char
    #    code is not XXX. If so, we keep it
    # Finally, set default value for the monument & country codes
    #
    rnx_4char = rnxobj.get_site(True, True)
    rnx_9char = rnxobj.get_site(False, False)

    if marker and len(marker) == 9:
        monum = marker[4:6]
        cntry = marker[6:]
    elif ninecharfile:
        if not rnx_4char in nine_char_dict:
            logger.warning(
                "32 - Site's missing in the input 9-char. file: %s", rinexfile
            )
            monum = "00"
            cntry = "XXX"
        else:
            monum = nine_char_dict[rnx_4char].upper()[4:6]
            cntry = nine_char_dict[rnx_4char].upper()[6:]
    elif mdaobj:
        monum = "00"
        cntry = mdaobj.get_country()
    elif rnx_9char[6:] != "XXX":
        monum = rnx_9char[4:6]
        cntry = rnx_9char[6:]
    else:
        monum = "00"
        cntry = "XXX"

    if country:
        if len(country) == 3:
            cntry = country
        else:
            logger.warning(
                "39 - Input country code is not 3 chars. RINEX will not be properly renamed: %s",
                rinexfile,
            )

    if cntry == "XXX":
        logger.warning(
            "32 - Site's country not retrieved. RINEX will not be properly renamed: %s",
            rinexfile,
        )

    rnxobj.set_site(rnx_4char, monum, cntry)

    ###########################################################################
    ########## Remove previous comments
    if mdaobj or modif_kw or (station_info and lfile_apriori):
        rnxobj.clean_rinexmod_comments(clean_history=True)

    ###########################################################################
    ########## Apply the MetaData object on the RinexFile object
    if mdaobj:
        rnxobj = apply_mda2rnxobj(
            rnxobj, mdaobj, ignore=ignore, keep_rnx_rec=keep_rnx_rec
        )
        logger.debug("RINEX Sitelog-Modified Metadata :\n" + rnxobj.get_header()[0])
        modif_source_metadata = mdaobj.filename
    else:
        modif_source_metadata = ""

    ###########################################################################
    ########## Apply the modif_kw dictionnary on the RinexFile object
    if modif_kw:
        # Checking input keyword modification arguments
        _modif_kw_check(modif_kw)

        modif_source_kw = "keywords:" + " ".join(modif_kw.keys())
        rnxobj = apply_modifkw2rnxobj(rnxobj, modif_kw)
        logger.debug(
            "RINEX Manual Keywords-Modified Metadata:\n" + rnxobj.get_header()[0]
        )
    else:
        modif_source_kw = ""

    ###########################################################################
    ########## Apply the site as the MARKER NAME within the RINEX
    # Must be after apply_mda2rnxobj and apply_modifkw2rnxobj
    # apply only is modif_kw does not overrides it (it is the overwhelming case)
    if "marker_name" not in modif_kw.keys():
        rnxobj.mod_marker(rnxobj.get_site(False, False, True))

    ###########################################################################
    ########## Correct the first and last time obs
    rnxobj.mod_time_obs(rnxobj.start_date, rnxobj.end_date)

    ###########################################################################
    ########## Add comment in the header
    githash = get_git_hash()
    vers_num = rimo.__version__ + " " + githash[-3:]
    # rnxobj.add_comment(("RinexMod (IPGP)","METADATA UPDATE"),add_pgm_cmt=True)
    rnxobj.add_prg_run_date_comment("RinexMod " + vers_num, "METADATA UPDATE")
    rnxobj.add_comment("RinexMod / IPGP-OVS (github.com/IPGP/rinexmod)")
    rnxobj.add_comment(
        "rinexmoded on {}".format(datetime.strftime(now, "%Y-%m-%d %H:%M%z"))
    )
    if mdaobj:
        rnxobj.add_comment("rinexmoded with {}".format(modif_source_metadata))
    if modif_kw:
        rnxobj.add_comment("rinexmoded with {}".format(modif_source_kw))
    # if marker: ##### Useless...
    #    rnxobj.add_comment('filename assigned from {}'.format(modif_marker))

    ###########################################################################
    ########## Write the station history in the header
    if mdaobj and full_history:
        title = ["- - - - - - - - - - - -", "SITE FULL HISTORY"]
        rnxobj.add_comments(title + mdaobj.rinex_full_history_lines())

    ###########################################################################
    ########## Sort the header
    rnxobj.sort_header()

    ###########################################################################
    ########## we regenerate the filenames
    if shortname or (rnxobj.name_conv == "SHORT" and not longname):
        apply_longname = False
    elif longname or (rnxobj.name_conv == "LONG" and not shortname):
        apply_longname = True
    else:
        apply_longname = True

    if apply_longname:
        rnxobj.get_longname(
            inplace_set=True,
            compression="",
            filename_style=filename_style,
            data_source=rnxobj.data_source,
        )
    else:
        rnxobj.get_shortname(
            inplace_set=True, compression="", filename_style=filename_style
        )

    # NB: here the compression type must be forced to ''
    #     it will be added in the next step in write_to_path

    ###########################################################################
    ########## We convert the file back to Hatanaka Compressed Rinex

    # NB: this test is complcated, ambiguous and not very useful => disabled 2025-01-05

    # if apply_longname and not compression:
    #     # If not specified, we set compression to gz when file changed to longname
    #     output_compression = "gz"
    # elif not compression:
    #     output_compression = rnxobj.compression
    # else:
    #     output_compression = compression

    output_compression = compression

    ###########################################################################
    ########## Writing output file
    try:
        outputfile = rnxobj.write_to_path(
            myoutputfolder, compression=output_compression, no_hatanaka=no_hatanaka
        )
        logger.info("# Out. file: " + outputfile)
    except hatanaka.hatanaka.HatanakaException as e:
        logger.error(
            "{:110s} - {}".format(
                "06 - File could not be written - hatanaka exception", rinexfile
            )
        )
        outputfile = None
        raise e

    if remove and os.path.isfile(outputfile):
        logger.info("Input file removed: %s", rinexfile)
        os.remove(rinexfile)

    ###########################################################################
    # Construct return dict by adding key if doesn't exists
    # and appending file to corresponding list
    if type(return_lists) is dict:
        return_lists = _return_lists_maker(rnxobj, return_lists)
        final_return = return_lists
    else:
        ###########################################################################
        # if no return dict given, return simply the path of the outputfile
        final_return = outputfile

    return final_return


# *****************************************************************************
# Upper level rinexmod for a Console run


def rinexmod_cli(
    rinexinput,
    outputfolder,
    sitelog=None,
    modif_kw=dict(),
    marker="",
    country="",
    longname=False,
    shortname=False,
    force_sitelog=False,
    force_rnx_load=False,
    ignore=False,
    ninecharfile=None,
    no_hatanaka=False,
    compression="gz",
    relative="",
    verbose=True,
    alone=False,
    output_logs=None,
    write=False,
    sort=False,
    full_history=False,
    filename_style="basic",
    multi_process=1,
    debug=False,
    station_info=None,
    lfile_apriori=None,
    force_fake_coords=False,
    remove=False,
    keep_rnx_rec=False,
):
    """
    Main function for reading a Rinex list file. It processes the list, and apply
    file name modification, command line based header modification, or sitelog-based
    header modification.

    Optimized for a CLI (in a Terminal usage) but can be used also in a
    stand-alone API mode.

    For a detailed description, check the help of the lower level
    `rinexmod` function or the help of the frontend CLI function in a Terminal
    """

    # If no longname, modif_kw and sitelog, return
    if (
        not sitelog
        and not modif_kw
        and not marker
        and not longname
        and not shortname
        and not station_info
        and not lfile_apriori
    ):
        logger.critical(
            "No action asked, provide at least one of the following args:"
            "--sitelog, --modif_kw, --marker, --longname, --shortname, --station_info, --lfile_apriori"
        )
        return None

    # If force option provided, check if sitelog option too, if not, not relevant.
    if force_sitelog and not sitelog:
        logger.critical(
            "--force option is relevant only when --sitelog option with a **single** sitelog is also provided"
        )
        return None

    # If ignore option provided, check if sitelog option too, if not, not relevant.
    if ignore and not sitelog:
        logger.critical(
            "--ignore option is relevant only when using also --sitelog option"
        )
        return None

    if ninecharfile and not longname:
        logger.critical(
            "--ninecharfile option is relevant only when using also --longname option"
        )
        return None

    if (station_info and not lfile_apriori) or (not station_info and lfile_apriori):
        logger.critical("--station_info and --lfile_apriori must be provided together")
        return None

    if station_info and lfile_apriori and sitelog:
        logger.critical(
            "both sitelogs and GAMIT files given as metadata input. Managing both is not implemented yet"
        )
        return None

    # If inputfile doesn't exists, return
    if len(rinexinput) == 1 and not os.path.isfile(rinexinput[0]):
        logger.critical("The input file doesn't exist: %s", rinexinput)
        return None

    if len(rinexinput) > 1 and alone:
        logger.critical("several inputs are given while -a/--alone option is set")
        return None

    if output_logs and not os.path.isdir(output_logs):
        logger.critical(
            "The specified output folder for logs doesn't exist : " + output_logs
        )
        return None

    outputfolder = os.path.abspath(outputfolder)
    if not os.path.isdir(outputfolder):
        # mkdirs ???
        os.makedirs(outputfolder)

    # Creating log file
    now = datetime.now()
    nowstr = datetime.strftime(now, "%Y%m%d%H%M%S")

    if output_logs:
        logfolder = output_logs
    else:
        logfolder = outputfolder

    logfile = os.path.join(logfolder, nowstr + "_" + "rinexmod_errors.log")
    if verbose:
        _ = rimo_log.logger_define("DEBUG", logfile, "DEBUG")
    else:
        _ = rimo_log.logger_define("INFO", logfile, "INFO")

    ### the refactor of 2024-03 make this obsolete
    ## now rinexinput is ALWAYS a list
    # if isinstance(rinexinput, list):
    #     pass
    # elif alone:
    #     rinexinput = [rinexinput]
    ### the refactor of 2024-03 make this obsolete

    # Opening and reading lines of the file containing list of rinex to proceed
    if len(rinexinput) == 1 and not alone:
        try:
            rinexinput_use = [line.strip() for line in open(rinexinput[0]).readlines()]
        except:
            logger.error("Something went wrong while reading: %s", str(rinexinput[0]))
            logger.error("Did you forget -a/--alone option?")
            return RinexModInputArgsError
    else:
        rinexinput_use = rinexinput

    if not rinexinput_use:
        logger.error("The input file is empty: %s", str(rinexinput))
        return RinexModInputArgsError

    if rinexinput_use[0].endswith("RINEX VERSION / TYPE"):
        logger.error(
            "The input file is not a file list but a RINEX: %s", str(rinexinput[0])
        )
        logger.error("Did you forget -a/--alone option?")
        return RinexModInputArgsError

    # sort the RINEX list
    if sort:
        rinexinput_use.sort()

    ### load the sitelogs/GAMIT-files as a **list of MetaData objects**
    # from sitelogs
    if sitelog:
        sitelogs_list_use = metadata_input_manage(sitelog, force_sitelog)
    # from GAMIT files
    elif station_info and lfile_apriori:
        sitelogs_list_use = gamit2mda_objs(
            station_info, lfile_apriori, force_fake_coords=force_fake_coords
        )
    else:
        sitelogs_list_use = None

    ### Looping in file list ###
    return_lists = dict()
    ####### Iterate over each RINEX
    rnxmod_kwargs_lis = []
    for rnx in rinexinput_use:
        rnxmod_kwargs = {
            "rinexfile": rnx,
            "outputfolder": outputfolder,
            "sitelog": sitelogs_list_use,
            "modif_kw": modif_kw,
            "marker": marker,
            "country": country,
            "longname": longname,
            "shortname": shortname,
            "force_rnx_load": force_rnx_load,
            "force_sitelog": force_sitelog,
            "ignore": ignore,
            "ninecharfile": ninecharfile,
            "no_hatanaka": no_hatanaka,
            "compression": compression,
            "relative": relative,
            "verbose": verbose,
            "return_lists": return_lists,
            "full_history": full_history,
            "filename_style": filename_style,
            "station_info": station_info,
            "lfile_apriori": lfile_apriori,
            "force_fake_coords": force_fake_coords,
            "remove": remove,
            "keep_rnx_rec": keep_rnx_rec,
        }

        rnxmod_kwargs_lis.append(rnxmod_kwargs)

    global rinexmod_mpwrap

    def rinexmod_mpwrap(rnxmod_kwargs_inp):
        try:
            return_lists_out = rinexmod(**rnxmod_kwargs_inp)
            return return_lists_out
        except Exception as e:
            if debug:  ### set as True for debug mode
                raise e
            else:
                logger.error(
                    "%s raised, RINEX is skiped: %s. Use -d/--debug option for more details",
                    type(e).__name__,
                    rnxmod_kwargs_inp["rinexfile"],
                )
                return None

    # number of parallel processing
    if multi_process > 1:
        logger.info("multiprocessing: %d cores used", multi_process)
    pool = mp.Pool(processes=multi_process)
    res_raw = [pool.apply_async(rinexmod_mpwrap, args=(x,)) for x in rnxmod_kwargs_lis]
    results = [e.get() for e in res_raw]

    for return_lists_mono in results:
        try:
            _return_lists_maker(return_lists_mono, return_lists)
        except ReturnListError:
            logger.warning(
                "one file has been skipped because of an odd individual return list"
            )
            continue

    #########################################
    logger.handlers.clear()

    if write:
        _return_lists_write(return_lists, logfolder, now)

    return return_lists


##### Class for --modif_kw
class ParseKwargs(argparse.Action):
    # source:
    # https://sumit-ghosh.com/posts/parsing-dictionary-key-value-pairs-kwargs-argparse-python/
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, dict())
        icmt = 0
        for value in values:
            try:
                key, value = value.split("=")

                if key == "comment":
                    getattr(namespace, self.dest)[key + "_" + str(icmt)] = value
                    icmt += 1
                else:
                    getattr(namespace, self.dest)[key] = value

            except Exception as e:

                def _print_kw_tips(values_inp):
                    logger.critical("********************************************")
                    logger.critical("TIP1: be sure you have respected the syntax:")
                    logger.critical("      -k keyword1='value1' keyword2='value2'")
                    logger.critical("********************************************")
                    logger.critical(values_inp)
                    return None

                _print_kw_tips(values)
                raise e


# *****************************************************************************
