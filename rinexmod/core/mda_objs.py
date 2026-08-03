import os
import re

import pandas as pd
from datetime import datetime

import rinexmod.readers.gamit as rimo_gmm
import rinexmod.readers.rinexmod_info as rimo_rmo
import rinexmod.classes.metadata as rimo_mda
import rinexmod.core as rimo_cor
import rinexmod.exceptions as rimo_exc

import rinexmod.logger as rimo_log

logger = rimo_log.logger_define("INFO")

# *****************************************************************************
# Metadata import


def _list_files(directory, extension, recursive=True):
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


def _is_geodesyml_file(file_path):
    r"""
    Check if a file is a GeodesyML file based on extension and naming pattern.

    Parameters
    ----------
    file_path : str
        Path to the file to check.

    Returns
    -------
    bool
        True if file matches GeodesyML pattern (^\w{4}.*\.xml$), False otherwise.
    """
    if not file_path.lower().endswith(".xml"):
        return False
    gml_pattern = re.compile(r"^\w{4}.*\.xml$")
    return bool(gml_pattern.match(os.path.basename(file_path)))


def _load_from_dir(dir_path, force=False):
    """
    Load metadata from a directory, auto-detecting whether it contains
    GeodesyML files or sitelog files.

    Parameters
    ----------
    dir_path : str
        Path to the directory.
    force : bool
        Force a single sitelog file path (only used for sitelogs).

    Returns
    -------
    list of MetaData objects.
    """
    # Check if directory contains GeodesyML files
    xml_files = _list_files(dir_path, ".xml", recursive=False)
    gml_pattern = re.compile(r"^\w{4}.*\.xml$")
    gml_files = [f for f in xml_files if gml_pattern.match(os.path.basename(f))]

    if gml_files:
        # Directory contains GeodesyML files, use geodesyml2mda_objs
        return gymls2mda_objs(dir_path, return_list_even_if_single_input=True)
    else:
        # Directory contains sitelogs, use sitlgs2mda_objs
        return sitlgs2mda_objs(
            dir_path, force=force, return_list_even_if_single_input=True
        )


def load_metadata(mda_inp, force=False):
    """
    Manage multiple types of metadata inputs and return a list of MetaData objects.

    Handles both sitelog and GeodesyML formats transparently.

    Possible inputs are:
     * list of string (sitelog/GeodesyML file paths),
     * single string (file path OR directory containing files)
     * single string (rinexmod_info with .csv extension)
     * list of MetaData objects
     * single MetaData object

    Parameters
    ----------
    mda_inp : list of str, str, list of MetaData, MetaData
        Various input types.
    force : bool
        Force a single sitelog file path (for sitelog processing).

    Returns
    -------
    list of MetaData objects.
        (can be a singleton)

    """
    # single MetaData object
    if isinstance(mda_inp, rimo_mda.MetaData):
        return [mda_inp]

    # list of MetaData objects
    if (
        isinstance(mda_inp, list)
        and mda_inp
        and isinstance(mda_inp[0], rimo_mda.MetaData)
    ):
        return mda_inp

    # CSV file (rinexmod_info format)
    if isinstance(mda_inp, str) and os.path.basename(mda_inp).endswith(".csv"):
        return rinexmod_info2mda_objs(mda_inp)

    # Directory
    if isinstance(mda_inp, str) and os.path.isdir(mda_inp):
        return _load_from_dir(mda_inp, force=force)

    # Single file (GeodesyML or sitelog)
    if isinstance(mda_inp, str) and os.path.isfile(mda_inp):
        if _is_geodesyml_file(mda_inp):
            return gymls2mda_objs(mda_inp, return_list_even_if_single_input=True)
        else:
            return sitlgs2mda_objs(
                mda_inp, force=force, return_list_even_if_single_input=True
            )

    # List of strings (file paths)
    if isinstance(mda_inp, list):
        # Separate GeodesyML and sitelog files
        gml_files = [f for f in mda_inp if isinstance(f, str) and _is_geodesyml_file(f)]
        sitelog_files = [
            f for f in mda_inp if isinstance(f, str) and not _is_geodesyml_file(f)
        ]

        mdaobjs_lis = []

        # Process GeodesyML files
        if gml_files:
            mdaobjs_lis.extend(
                gymls2mda_objs(gml_files, return_list_even_if_single_input=True)
            )

        # Process sitelog files
        if sitelog_files:
            mdaobjs_lis.extend(
                sitlgs2mda_objs(
                    sitelog_files, force=force, return_list_even_if_single_input=True
                )
            )

        return mdaobjs_lis

    logger.error(
        "Wrong Input, must be a list of paths, a single path (file/directory), "
        "a MetaData object, or a list of MetaData objects. Input given: %s, %s",
        mda_inp,
        type(mda_inp),
    )
    raise rimo_exc.RinexModInputArgsError


def load_metadata_gml(gml_inp):
    """
    DEPRECATED: Use load_metadata() instead.

    load_metadata() now handles both sitelog and GeodesyML formats automatically.
    This function is kept for backward compatibility.

    Parameters
    ----------
    gml_inp : str, list of MetaData, MetaData
        GeodesyML file path, list of MetaData objects, or single MetaData object.

    Returns
    -------
    list of MetaData objects.
    """
    logger.warning(
        "load_metadata_gml() is deprecated. Use load_metadata() instead, "
        "which now handles both sitelog and GeodesyML formats automatically."
    )
    return load_metadata(gml_inp)


def sitlgs2mda_objs(sitelog_path, force=False, return_list_even_if_single_input=True):
    """
    Read a set of sitelog files and convert them to MetaData objects

    Parameters
    ----------
    sitelog_path : str or list of str
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
    if type(sitelog_path) is list:
        slgs_all = sitelog_path
        sitelog_path = "input sitelog list"
    # Case of one single sitelog
    elif os.path.isfile(sitelog_path):
        slgs_all = [sitelog_path]
    # Case of a folder
    elif os.path.isdir(sitelog_path):
        sitelog_extension = ".log"
        slgs_all = _list_files(sitelog_path, sitelog_extension)

        sitelog_pattern = re.compile(r"\w{4,9}_\d{8}.log")
        slgs_all = [f for f in slgs_all if sitelog_pattern.match(os.path.basename(f))]
    ### case of no file nor folder
    else:
        logger.error(
            "unable to handle file/directory. Does it exists?: %s", sitelog_path
        )
        raise rimo_exc.RinexModInputArgsError

    #### Read the sitelogs
    logger.info("**** %i sitelogs detected (in %s)", len(slgs_all), sitelog_path)
    for sl in slgs_all:
        logger.debug(sl)
    # Get last version of sitelogs if multiple available
    # (1st gross search based on date in filename)
    slgs_latest = _slg_find_latest_name(slgs_all)
    # load the sitelogs as metadata objects
    mdaobjs_lis, slgs_bad_lis = _load_sitelogs(slgs_latest, force)
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


def gymls2mda_objs(gml_path, return_list_even_if_single_input=True):
    r"""
    Read GeodesyML file(s) and convert their content to MetaData objects.

    Supports reading single files, multiple files, or directories (recursive search).

    Parameters
    ----------
    gml_path : str or list of str
        Path of a single GeodesyML file, a list of GeodesyML file paths,
        or a directory containing GeodesyML files.
    return_list_even_if_single_input : bool, optional
        If a single file is given, return the corresponding MetaData object
        into a list (singleton). The default is True.

    Returns
    -------
    mdaobjs_lis : list
        List of MetaData objects.

    """
    # Case of a list of GeodesyML files
    if isinstance(gml_path, list):
        gml_files = gml_path
        gml_path_display = "input GeodesyML list"
    # Case of one single file
    elif os.path.isfile(gml_path):
        gml_files = [gml_path]
        gml_path_display = gml_path
    # Case of a folder
    elif os.path.isdir(gml_path):
        gml_extension = ".xml"
        gml_files = _list_files(gml_path, gml_extension)

        # Filter by GeodesyML naming pattern
        gml_pattern = re.compile(r"^\w{4}.*\.xml$")
        gml_files = [f for f in gml_files if gml_pattern.match(os.path.basename(f))]

        gml_path_display = gml_path
    else:
        logger.error("unable to handle file/directory. Does it exists?: %s", gml_path)
        raise rimo_exc.RinexModInputArgsError

    logger.info(
        "**** %i GeodesyML files detected (in %s)", len(gml_files), gml_path_display
    )
    for gf in gml_files:
        logger.debug(gf)

    mdaobjs_lis = []
    for gml_file in gml_files:
        logger.info("Processing GeodesyML file: %s", gml_file)
        mdaobj = rimo_mda.MetaData(sitelogfile=None)
        mdaobj.set_from_gml(gml_file)
        mdaobjs_lis.append(mdaobj)

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


def gamit2mda_objs(
    station_info_path,
    lfile_path=None,
    force_fake_coords=False,
    ninecharfile_path=None,
    rev=False,
):
    """
    Read a GAMIT files and convert their content to MetaData objects

    Parameters
    ----------
    station_info_path : str or pd.DataFrame
        Path of a GAMIT station.info file to obtain
        GNSS site metadata information.
    lfile_path : str or pd.DataFrame
        Path of a GAMIT apriori apr/L-File to obtain
        GNSS site position and DOMES information.
    force_fake_coords : bool, optional
        hen using GAMIT station.info metadata without apriori coordinates in
        the L-File, gives fake coordinates at (0°,0°) to the site.
        The default is False.
    ninecharfile_path : str, optional
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
    if isinstance(station_info_path, pd.DataFrame):
        df_stinfo_raw = station_info_path
        stinfo_name = "station.info"
    else:
        df_stinfo_raw = rimo_gmm.read_gamit_station_info(
            station_info_path, sort=False
        )  # sort = not rev if rev, no sort
        stinfo_name = os.path.basename(station_info_path)

    if not lfile_path:
        df_apr = pd.DataFrame(columns=["site"])
        logger.warning(
            "No L-File provided, fake coordinates will be used! "
            "(force_fake_coords forced to True)"
        )
        force_fake_coords = True
    elif isinstance(lfile_path, pd.DataFrame):
        df_apr = lfile_path
    else:
        df_apr = rimo_gmm.read_gamit_apr_lfile(lfile_path)

    if not ninecharfile_path is None:
        nine_char_dict = rimo_cor.read_ninecharfile(ninecharfile_path)
    else:
        nine_char_dict = dict()

    sites_isin = df_stinfo_raw["site"].isin(df_apr["site"])
    ### for the stats only
    sites_uniq = pd.Series(df_stinfo_raw["site"].unique())
    sites_isin_uniq = sites_uniq.isin(df_apr["site"].unique())
    n_sites_notin = len(sites_uniq) - sum(sites_isin_uniq)

    if n_sites_notin > 0 and not force_fake_coords:
        warnmsg = "%i/%i sites in %s are not in apr/lfile. They are skipped (you can force fake coords with -fc)"
        logger.warning(warnmsg, n_sites_notin, len(sites_uniq), stinfo_name)
        df_stinfo = df_stinfo_raw[sites_isin]
    elif n_sites_notin > 0 and force_fake_coords:
        warnmsg = "%i/%i sites in %s are not in apr/lfile. Fake coords at (0°,0°) used"
        logger.warning(warnmsg, n_sites_notin, len(sites_uniq), stinfo_name)
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


def rinexmod_info2mda_objs(
    rinexmod_info_path,
    force_fake_coords=False,
    ninecharfile_path=None,
    rev=False,
):
    """
    Read a rinexmod_info CSV file and convert its content to MetaData objects.

    Parameters
    ----------
    rinexmod_info_path : str or pd.DataFrame
        Path of a rinexmod_info CSV file to obtain GNSS site metadata information.
    force_fake_coords : bool, optional
        If True, coordinates will be set to (0,0,0) and DOMES to 00000X000.
        The default is False.
    ninecharfile_path : str, optional
        Path of a file that contains 9-char. site names.
        The default is None.
    rev : bool, optional
        Reverse order of inputs for instrumental changes
        (from newest to oldest).
        The default is False.

    Returns
    -------
    mdaobjs_lis : list
        List of MetaData objects.
    """

    if isinstance(rinexmod_info_path, pd.DataFrame):
        df_rinexmod_raw = rinexmod_info_path
        rinexmod_info_name = "rinexmod_info"
    else:
        df_rinexmod_raw = rimo_rmo.read_rinexmod_info(rinexmod_info_path, sort=False)
        rinexmod_info_name = os.path.basename(rinexmod_info_path)

    if ninecharfile_path is not None:
        nine_char_dict = rimo_cor.read_ninecharfile(ninecharfile_path)
    else:
        nine_char_dict = dict()

    # Filter for sites that have coordinates (if not force_fake_coords)
    if not force_fake_coords:
        has_coords = (
            df_rinexmod_raw[["x_coord", "y_coord", "z_coord"]].notna().all(axis=1)
        )
        sites_with_coords = df_rinexmod_raw.loc[has_coords, "site"].unique()
        sites_uniq = pd.Series(df_rinexmod_raw["site"].unique())
        sites_missing_coords = ~sites_uniq.isin(sites_with_coords)
        n_sites_nocoords = sites_missing_coords.sum()

        if n_sites_nocoords > 0:
            logger.warning(
                "%i/%i sites in %s are missing coordinates. They are skipped "
                "(you can force fake coords with -fc)",
                n_sites_nocoords,
                len(sites_uniq),
                rinexmod_info_name,
            )
            df_rinexmod = df_rinexmod_raw[
                df_rinexmod_raw["site"].isin(sites_with_coords)
            ]
        else:
            df_rinexmod = df_rinexmod_raw
    else:
        df_rinexmod = df_rinexmod_raw

    df_rinexmod_grp = df_rinexmod.groupby("site")

    mdaobjs_lis = []

    logger.info(
        "%i sites will be extracted from %s", len(df_rinexmod_grp), rinexmod_info_name
    )

    for site, site_info in df_rinexmod_grp:
        logger.debug("extract %s from %s", site, rinexmod_info_name)

        # Search in ninecharfile
        if site in nine_char_dict.keys():
            site_use = nine_char_dict[site]
            logger.debug("4 > 9 char. conversion: %s > %s", site, site_use)
        else:
            site_use = site

        mdaobj = rimo_mda.MetaData(sitelogfile=None)
        mdaobj.set_from_rinexmod_info(
            site_use,
            df_rinexmod,
            force_fake_coords=force_fake_coords,
            rinexmod_info_name=rinexmod_info_name,
        )
        if rev:
            mdaobj.instrus.reverse()
            logger.info("Reversing order of instrumental changes")
        mdaobjs_lis.append(mdaobj)

    logger.info(
        "%i sites have been extracted from %s", len(mdaobjs_lis), rinexmod_info_name
    )

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
    mdaobj_dic = (
        dict()
    )  # Initialize an empty dictionary to store grouped MetaData objects.
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


def _load_sitelogs(sitelogs_inp, force=False):
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

    def _load_slg_mono(sitelog_filepath, force_load):
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
                raise rimo_exc.MetaDataError
            else:
                mdaobj_load = None

        return mdaobj_load

    mdaobjs_lis = []
    bad_sitelogs_lis = []
    for sta_sitelog in sitelogs_inp:
        mdaobj = _load_slg_mono(sta_sitelog, force)
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
    if isinstance(rnxobj_or_site4char, str):
        rnx_4char = rnxobj_or_site4char[:4]
        err_label = rnxobj_or_site4char
    else:
        rnx_4char = rnxobj_or_site4char.get_site(True, True)
        err_label = rnxobj_or_site4char.filename

    logger.debug(f"Searching corresponding metadata for site: {rnx_4char}")

    if not mdaobjs_lis:
        logger.warning("The metadata list provided is empty!")

    mdaobjs_site = [md for md in mdaobjs_lis if md.site_id4 == rnx_4char]

    if not mdaobjs_site:
        if len(mdaobjs_lis) == 1 and force:
            errmsg = "34 - RINEX name's site does not correspond to provided metadata, forced processing anyway"
            logger.warning(f"{errmsg:110s} - {err_label}")
            return None

        errmsg = (
            "33 - No metadata found for this RINEX"
            if len(mdaobjs_lis) > 1
            else "33 - RINEX name's site does not correspond to provided metadata, use -f option to force"
        )
        logger.error(f"{errmsg:110s} - {err_label}")
        raise rimo_exc.RinexModInputArgsError

    return (
        mdaobjs_site[0]
        if len(mdaobjs_site) == 1
        else _mda_find_latest_prep(mdaobjs_site)[0]
    )


def apply_mda2rnxobj(
    rnxobj, mdaobj, ignore=False, keep_rnx_rec=False, round_instru_dates=False
):
    """
    apply a MetaData object on a RinexFile object
    to modify this RinexFile with the rights metadata
    """

    ### do this check with 9 chars at one point
    rnx_4char = rnxobj.get_site(True, True)
    # Site name from the sitelog
    mda_4char = mdaobj.site_id4  # misc_meta["ID"].lower()[:4]

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
        raise rimo_exc.MetaDataError

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
