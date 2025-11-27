#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API functions of RinexMod

Created on Wed Mar  8 12:14:54 2023

@author: psakic
"""

import argparse
import os
import re
import subprocess
import string
import pandas as pd
from datetime import datetime, timedelta


import rinexmod as rimo
import rinexmod.common.gamit_meta as rimo_gmm
import rinexmod.classes.metadata as rimo_mda
import rinexmod.classes.rinexfile as rimo_rnx


import rinexmod.logger as rimo_log
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
# core functions


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


def apply_mda2rnxobj(rnxobj, mdaobj, ignore=False, keep_rnx_rec=False, round_instru_dates=False):
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
    mda_vars, ignored = mdaobj.find_instru4rnx(
        rnxobj.start_date, rnxobj.end_date, ignore, round_instru_dates
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


def modif_kw_check(modif_kw):
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

def rtun_lsts_make(rnxobj_or_dict, return_lists=dict()):
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


def rtun_lsts_write(return_lists, logfolder, now_dt=None):
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
# low level functions originaly from RinexFile class
def search_idx_val(data, field):
    """
    find the index (line number) of a researched field in the RINEX data
    return None if nothing has beeen found
    """
    idx = -1
    out_idx = None
    for e in data:
        idx += 1
        if field in e:
            out_idx = idx
            break
    return out_idx


def slice_list(seq, num):
    """make sublist of num elts of a list"""
    # http://stackoverflow.com/questions/4501636/creating-sublists
    return [seq[i : i + num] for i in range(0, len(seq), num)]


def round_time(dt=None, date_delta=timedelta(minutes=60), to="average"):
    """
    Round a datetime object to a multiple of a timedelta
    dt : datetime.datetime object, default now.
    dateDelta : timedelta object, we round to a multiple of this, default 1 minute.
    to : up / down / average
    from:  http://stackoverflow.com/questions/3463930/how-to-round-the-minute-of-a-datetime-object-python
    """
    round_to = date_delta.total_seconds()
    if dt is None:
        dt = datetime.now()
    seconds = (dt - dt.min).seconds

    if seconds % round_to == 0 and dt.microsecond == 0:
        rounding = (seconds + round_to / 2) // round_to * round_to
    else:
        if to == "up":
            # // is a floor division, not a comment on following line (like in javascript):
            rounding = (
                (seconds + dt.microsecond / 1000000 + round_to) // round_to * round_to
            )
        elif to == "down":
            rounding = seconds // round_to * round_to
        else:
            rounding = (seconds + round_to / 2) // round_to * round_to

    return dt + timedelta(0, rounding - seconds, -dt.microsecond)


def regex_pattern_rinex_filename():
    """
    return a dictionnary with the different REGEX patterns to describe a RIENX filename
    """
    pattern_dic = dict()
    # pattern_dic["shortname"] = "....[0-9]{3}(\d|\D)\.[0-9]{2}(o|d)(|\.(Z|gz))"
    pattern_dic["shortname"] = (
        r"....[0-9]{3}(\d|\D)([0-9]{2}\.|\.)[0-9]{2}(o|d)(|\.(Z|gz))"  ### add subhour starting min
    )
    pattern_dic["longname"] = (
        r".{4}[0-9]{2}.{3}_(R|S|U)_[0-9]{11}_([0-9]{2}\w)_[0-9]{2}\w_\w{2}\.\w{3}(\.gz|)"
    )
    pattern_dic["longname_gfz"] = (
        r".{4}[0-9]{2}.{3}_[0-9]{8}_.{3}_.{3}_.{2}_[0-9]{8}_[0-9]{6}_[0-9]{2}\w_[0-9]{2}\w_[A-Z]*\.\w{3}(\.gz)?"
    )

    return pattern_dic


def dates_from_rinex_filename(rnx_inp):
    """
    determine the start epoch, the end epoch and the period of a RINEX
    file based on its name only.
    The RINEX is not readed. This function is much faster but less reliable
    than the RinexFile.start_date and RinexFile.end_date attribute

    return the start epoch and end epoch as datetime
    and the period as timedelta
    """
    pattern_dic = regex_pattern_rinex_filename()

    pattern_shortname = re.compile(pattern_dic["shortname"])
    pattern_longname = re.compile(pattern_dic["longname"])
    pattern_longname_gfz = re.compile(pattern_dic["longname_gfz"])

    rinexname = os.path.basename(rnx_inp)

    def _period_to_timedelta(peri_inp):
        peri_val = int(peri_inp[0:2])
        peri_unit = str(peri_inp[2])

        if peri_unit == "M":
            unit_sec = 60
        elif peri_unit == "H":
            unit_sec = 3600
        elif peri_unit == "D":
            unit_sec = 86400
        else:
            logger.warn("odd RINEX period: %s, assume it as 01D", peri_inp)
            unit_sec = 86400

        return timedelta(seconds=peri_val * unit_sec)

    ##### LONG rinex name
    if re.search(pattern_longname, rinexname):
        date_str = rinexname.split("_")[2]
        period_str = rinexname.split("_")[3]

        yyyy = int(date_str[:4])
        doy = int(date_str[4:7])
        hh = int(date_str[7:9])
        mm = int(date_str[9:11])
        dt_srt = datetime(yyyy, 1, 1) + timedelta(
            days=doy - 1, seconds=hh * 3600 + mm * 60
        )
        period = _period_to_timedelta(period_str)
        dt_end = dt_srt + period

        return dt_srt, dt_end, period

    ##### LONG rinex name -- GFZ's GODC internal name
    elif re.search(pattern_longname_gfz, rinexname):
        date_str = rinexname.split("_")[5]
        time_str = rinexname.split("_")[6]
        period_str = rinexname.split("_")[7]

        yyyy = int(date_str[:4])
        mo = int(date_str[4:6])
        dd = int(date_str[6:8])

        hh = int(time_str[0:2])
        mm = int(time_str[2:4])
        ss = int(time_str[4:6])

        dt_srt = datetime(yyyy, mo, dd, hh, mm, ss)
        period = _period_to_timedelta(period_str)
        dt_end = dt_srt + period

        return dt_srt, dt_end, period

    ##### SHORT rinex name
    elif re.search(pattern_shortname, rinexname):
        alphabet = list(string.ascii_lowercase)

        doy = int(rinexname[4:7])
        yy = int(rinexname[9:11])

        if yy > 80:
            year = yy + 1900
        else:
            year = yy + 2000

        if rinexname[7] in alphabet:
            h = alphabet.index(rinexname[7])
            period = timedelta(seconds=3600)
        else:
            h = 0
            period = timedelta(seconds=86400)

        dt_srt = datetime(year, 1, 1) + timedelta(days=doy - 1, seconds=h * 3600)
        dt_end = dt_srt + period
        return dt_srt, dt_end, period

    else:
        logger.error("%s has not a RINEX name well formatted", rinexname)
        return None, None, None


def file_period_from_timedelta(start_date, end_date):
    """
    return the RINEX file period (01H, 01D, 15M...) based on a
    start and end date

    Parameters
    ----------

    Returns
    -------
    file_period : str
        file period (01H, 01D, 15M...)
    session : bool
        True if the timedelta refers to a session (<01D)
        False otherwise (01D).

    """
    rndtup = lambda x, t: round_time(x, timedelta(minutes=t), "up")
    rndtdown = lambda x, t: round_time(x, timedelta(minutes=t), "down")
    rndtaver = lambda x, t: round_time(x, timedelta(minutes=t), "average")
    # rounded at the hour
    # maximum and average delta between start and end date
    delta_max = rndtup(end_date, 60) - rndtdown(start_date, 60)
    delta_ave = rndtaver(end_date, 60) - rndtaver(start_date, 60)

    hours_ave = int(delta_ave.total_seconds() / 3600)
    delta_sec = (end_date - start_date).total_seconds()

    # first, the special case : N *full* hours
    if delta_max <= timedelta(seconds=86400 - 3600) and hours_ave > 0:  ## = 23h max
        # delta_ave is a more precise delta than delta_max (average)
        file_period = str(hours_ave).zfill(2) + "H"
        session = True
    # more regular cases : 01H, 01D, nnM, or Unknown
    elif delta_max <= timedelta(seconds=3600):
        # Here we consider sub hourly cases
        session = True
        file_period = None
        for m in [5, 10, 15, 20, 30]:
            if (m * 60 - 1) <= delta_sec <= (m * 60 + 1):
                file_period = str(m).zfill(2) + "M"
        if not file_period:
            # NB: this test is useless, it is treated by the previous test
            file_period = "01H"
    elif hours_ave == 0 and delta_max > timedelta(seconds=3600):  # Note 2
        hours_max = int(delta_max.total_seconds() / 3600)
        file_period = str(hours_max).zfill(2) + "H"
        session = True
    elif (
        timedelta(seconds=3600) < delta_max <= timedelta(seconds=86400 + 3600)
    ):  # Note1
        file_period = "01D"
        session = False
    else:
        file_period = "00U"
        session = False
    # Note1: a tolerance of +/- 1 hours is given because old ashtech RINEXs
    #        includes the epoch of the next hour/day
    #        and then the present delta_max value reach 25
    #        it justifies also the necessity of the delta_ave variable

    # Note 2: very rare (but possible) case --' :
    #         very short file, riding in between* two hours ("a cheval sur 2 heures")
    #         met e.g. for "2024-08-13 11:54:00" > "2024-08-13 12:04:00"
    #         then the delta_max is 2H and the delta_ave is 0
    #         and we must introduce hours_max rather than hours_ave

    return file_period, session
