#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Feb  5 17:30:30 2024

@author: psakic

Low-level functions to import GAMIT metadata file as pandas DataFrame

"""

import datetime as dt
import re

import numpy as np
import pandas as pd

from rinexmod import logger as rimo_log
from rinexmod import rinexmod_api as rimo_api

logger = rimo_log.logger_define("INFO")


def read_gamit_apr_lfile(aprfile_inp):
    """
    read a GAMIT's apr/L-File (GNSS stations coordinates and DOMES)
    and store the data in a DataFrame

    Parameters
    ----------
    aprfile_inp : str
        path of the input apr/L-File

    Returns
    -------
    df : pandas DataFrame
        the apr/lfile info data

    Note
    ----
    If no DOMES is provided in the last 'Note' column,
    a dummy DOMES 00000X000 is returned

    site codes are given in lower case

    """
    lines_stk = []

    for l in open(aprfile_inp):

        if not l[0] == " " or l.strip().startswith("#") or l.strip().startswith("*"):
            continue

        # x, y, z = np.nan, np.nan, np.nan
        # vx,vy,vz = 0.,0.,0.
        # t = pd.NaT

        f = l[1:].split()

        site = l[1:5]
        try:
            site_full = f[0]
        except Exception as e:
            logger.error("unable to read the GAMIT's lfile")
            raise e

        x = float(f[1])
        y = float(f[2])
        z = float(f[3])
        if len(f) >= 8:
            ttmp = float(f[7])
        else:
            ttmp = 1980.0

        # if np.isclose(ttmp , 0.):
        #     t = conv.year_decimal2dt(2000.)
        # else:
        #     t = conv.year_decimal2dt(ttmp)
        t = ttmp

        # if len(l) > 225: # if velocities are given (125 is arbitrary)
        #     vX = float(f[8])
        #     vY = float(f[9])
        #     vZ = float(f[10])
        # else: # if no velocityis given
        #     vX = 0.
        #     vY = 0.
        #     vZ = 0.

        domes_re = re.search("[0-9]{5}[A-Z][0-9]{3}", l)
        if domes_re:
            domes = domes_re.group()
        else:
            domes = "00000X000"

        lines_stk.append((site, site_full, t, x, y, z, domes))

    df = pd.DataFrame(lines_stk)
    df.columns = ["site", "site_full", "epoch", "x", "y", "z", "domes"]

    df["site"] = df["site"].str.lower()

    return df


def read_gamit_station_info(station_info_inp, sort=True):
    """
    read a GAMIT's station.info (GNSS stations metadata)
    and store the data in a DataFrame

    Odd rows in station.info will be skipped

    Parameters
    ----------
    station_info_inp : str
        path of the input station.info.
    sort : bool, optional
        sort the DataFrame by site and start time.
        The default is True.

    Returns
    -------
    df : pandas DataFrame
        the station info data

    Note
    ----
    site codes are given in lower case
    """

    ### from gamit/lib/rstnfo.f
    #
    # c Label         Token  Format   Default      Description
    # c ------        -----  -----    ----------  ----------------------------------------------
    # c *SITE         sitcod  a4                  4-char station code
    # c Station Name  sname   a16                 16-char station name
    # c Session Start  start  2i4,3i3  0 0 0 0 0  start time (yr doy hr min sec)
    # c Session Stop  stop    2i4,3i3  0 0 0 0 0  stop time (yr doy hr min sec)
    # c Sessn         sessn   i1       0          session number
    # c Ant Ht        anth    f7.4     0.0        height of antenna ARP above the monument
    # c Ant N         antn    f7.4     0.0        N offset of ant ARP from the center of the monument
    # c Ant E         ante    f7.4     0.0        E offset of ant ARP from the center of the monument
    # c RcvCod        rcvcod  a6                  6-char/acter GAMIT receiver code
    # c Receiver Type rctype  a20                 IGS (RINEX) receiver name
    # c Receiver SN   rcvrsn  a20                 receiver serial number
    # c SwVer         swver   f5.2     0.0        GAMIT firmware code (real)
    # c Vers          rcvers  a20                 receiver firmware version from RINEX
    # c AntCod        antcod   a6                 6-charr GAMIT antenna code
    # c Antenna SN    antsn   a20                 20-char antenna serial number
    # c Antenna Type  anttyp  a15                 IGS antenna name, 1st 15 chars of RINEX antenna field
    # c Dome          radome   a5                 IGS radome name, last 5 chars of RINEX antenna field
    # c HtCod         htcod    a5     DHARP       5-char GAMIT code for type of height measurement
    # c AntDAZ	antdaz  f5.0     0.0        Alignment from True N (deg).  TAH 2020203.

    # colsize = np.array([4,16,4,4,3,3,3,4,4,3,3,3,1,7,7,7,6,20,20,5,20,6,20,15,5,5,5])
    colsize = np.array(
        [
            5,
            20,
            4 + 1,
            3 + 1,
            2 + 1,
            2 + 1,
            2 + 1,  # start
            4 + 1,
            3 + 1,
            2 + 1,
            2 + 1,
            2 + 1,  # end
            7 + 2,
            7 + 2,
            7 + 2,
            6 + 2,  # antenna high
            20 + 2,
            20 + 2,
            5 + 2,  # rec (2 version fields ...)
            20 + 2,  # rec SN
            15 + 2,
            5 + 2,
            20 + 2,
            1,  # Antenna
        ]
    )

    # colsize_use = colsize+1
    colsize_use = colsize
    # colsize = [e+1  for e in colsize]
    # colsize_use = colsize+2

    col = [
        "site",
        "station name",
        "start year",
        "start doy",
        "start hh",
        "start mm",
        "start ss",
        "stop year",
        "stop doy",
        "stop hh",
        "stop mm",
        "stop ss",
        "ant ht",
        "htcod",
        "ant n",
        "ant e",
        # 'rcvcod',
        "receiver type",
        "vers",
        "swver",
        "receiver sn",
        "antenna type",
        "dome",
        "antenna sn",
        "antdaz",
    ]

    bad_lines = []
    with open(station_info_inp, encoding="iso8859_1") as f:
        for il, l in enumerate(f.readlines()):
            if l[0] != " ":
                bad_lines.append(il)

    df = pd.read_fwf(
        station_info_inp,
        skiprows=bad_lines,
        widths=colsize_use,
        encoding="iso8859_1",
        header=None,
    )

    df.columns = col

    ##### clean df
    ### remove empty rows
    try:
        bool_empty_rows = df["site"].apply(len) == 1
    except Exception as e:
        logger.error("unable to read the GAMIT's station.info")
        raise e

    df = df[np.logical_not(bool_empty_rows)]
    ### do a second NaN cleaning, but the previous should have cleaned everything
    df.dropna(inplace=True, how="all")
    df.reset_index(inplace=True, drop=True)

    ##### create datetime start/end columns
    df["start year"] = df["start year"].replace(9999, 2099)
    df["start doy"] = df["start doy"].replace(999, 365)
    df["start hh"] = df["start hh"].replace(99, 00)
    df["start mm"] = df["start mm"].replace(99, 00)
    df["start ss"] = df["start ss"].replace(99, 00)

    df["stop year"] = df["stop year"].replace(9999, 2099)
    df["stop doy"] = df["stop doy"].replace(999, 365)
    df["stop hh"] = df["stop hh"].replace(99, 00)
    df["stop mm"] = df["stop mm"].replace(99, 00)
    df["stop ss"] = df["stop ss"].replace(99, 00)

    df_start = doy2dt(
        df["start year"],
        df["start doy"],
        df["start hh"],
        df["start mm"],
        df["start ss"],
    )

    df["start"] = df_start

    df_end = doy2dt(
        df["stop year"],
        df["stop doy"],
        df["stop hh"],
        df["stop mm"],
        df["stop ss"]
    )

    df["end"] = df_end

    df["site"] = df["site"].str.lower()

    df["start"] = pd.to_datetime(df["start"])
    df["end"] = pd.to_datetime(df["end"])

    if sort:
        df.sort_values(by=["site", "start"], inplace=True)

    return df


def gamit_df2instru_miscmeta(site, stinfo_df_inp, apr_df_inp, force_fake_coords=False):
    """
    read GAMIT files to get the RinexMod internal
    "instrus" and "misc_meta" dictionaries,
    necessary for the MetaData objects

    Here the site codes must remain as close as
    possible from the GAMIT input files
    i.e. 4 char.

    Parameters
    ----------
    site : str
        native site *4 char.* code which will be extracted from the
        station_info and apriori DataFrame.
    stinfo_df_inp : DataFrame
        station.info-like DataFrame.
    apr_df_inp : DataFrame
        lfile-like DataFrame.
    force_fake_coords : bool, optional
        if True, the coordinates will be set to (0,0,0) and
        the domes number to 00000X000. The default is False.

    Returns
    -------
    installations : dict
        "installations" list i.e. list of "instrus" dict.
    mm_dic : dict
        "misc meta" dict.

    """
    #########################################################
    #### INSTRUMENTATION PART
    stinfo_df_site = stinfo_df_inp[stinfo_df_inp["site"] == site]
    installations = []

    for irow, row in stinfo_df_site.iterrows():
        inst_dic = dict()

        ##### dates
        inst_dic["dates"] = [row["start"].to_pydatetime(), row["end"].to_pydatetime()]

        ##### receiver
        rec_dic = dict()
        rec_dic["Receiver Type"] = str(row["receiver type"])
        rec_dic["Satellite System"] = "GPS+GLO+GAL+BDS+QZSS+SBAS"
        rec_dic["Serial Number"] = str(row["receiver sn"])
        rec_dic["Firmware Version"] = str(row["vers"])
        rec_dic["Elevation Cutoff Setting"] = "0"
        rec_dic["Date Installed"] = row["start"].to_pydatetime()
        rec_dic["Date Removed"] = row["end"].to_pydatetime()
        rec_dic["Temperature Stabiliz."] = "none"
        rec_dic["Additional Information"] = "none"

        inst_dic["receiver"] = rec_dic

        ##### antenna
        ant_dic = dict()
        ant_dic["Antenna Type"] = str(row["antenna type"])
        ant_dic["Serial Number"] = str(row["antenna sn"])
        ant_dic["Antenna Reference Point"] = "none"
        ant_dic["Marker->ARP Up Ecc. (m)"] = row["ant ht"]
        ant_dic["Marker->ARP North Ecc(m)"] = row["ant n"]
        ant_dic["Marker->ARP East Ecc(m)"] = row["ant e"]
        ant_dic["Alignment from True N"] = row["antdaz"]
        ant_dic["Antenna Radome Type"] = str(row["dome"])
        ant_dic["Radome Serial Number"] = "none"
        ant_dic["Antenna Cable Type"] = "none"
        ant_dic["Antenna Cable Length"] = "0"
        ant_dic["Date Installed"] = row["start"].to_pydatetime()
        ant_dic["Date Removed"] = row["end"].to_pydatetime()
        ant_dic["Additional Information"] = "none"
        ant_dic["metpack"] = "none"

        inst_dic["antenna"] = ant_dic

        installations.append(inst_dic)

    #########################################################
    #### MISC META PART
    apr_df_site = apr_df_inp[apr_df_inp["site"] == site]
    if len(apr_df_site) == 0 and not force_fake_coords:
        logger.error(
            "no coords in apr/lfile for %s, abort (you can force fake coords with -fc)",
            site,
        )
        raise rimo_api.RinexModError

    elif len(apr_df_site) == 0 and force_fake_coords:
        # logger.warning("no coords in apr/lfile for %s, fake coords at (0°,0°) used",site)
        apr_df_site = pd.Series(
            {"x": 6378137.000, "y": 0, "z": 0, "domes": "00000X000"}
        )
    else:
        apr_df_site = apr_df_site.iloc[-1]
        apr_df_site.squeeze()

    mm_dic = dict()

    mm_dic["IERS DOMES Number"] = apr_df_site["domes"]

    mm_dic["operator"] = "OPERATOR"
    mm_dic["agency"] = "AGENCY"

    mm_dic["X coordinate (m)"] = apr_df_site["x"]
    mm_dic["Y coordinate (m)"] = apr_df_site["y"]
    mm_dic["Z coordinate (m)"] = apr_df_site["z"]

    mm_dic["ID"] = site
    mm_dic["Country"] = "XXX"

    return installations, mm_dic


def doy2dt(year, days, hours=0, minutes=0, seconds=0):
    """
    Time representation conversion

    Day of Year Time => Python's datetime

    Parameters
    ----------
    year, days : float or list/numpy.array of floats.
        year, days of year
    hours, minutes, seconds : float or list/numpy.array of floats, optional
        hours, minutes, seconds

    Returns
    -------
    L : datetime or list/numpy.array of datetime.
        Datetime(s)

    Note
    ----
    extracted from the GeodeZYX toolbox
    https://github.com/IPGP/geodezyx-toolbox
    """
    if not is_iterable(year):
        # All this because Python cant handle int with a starting with 0 (like 08)
        # => SyntaxError: invalid token

        if np.any(np.isnan([year, days, hours, minutes, seconds])):
            logger.error(
                "one input is NaN, abort: %s,%s,%s,%s,%s",
                year,
                days,
                hours,
                minutes,
                seconds,
            )
            raise Exception

        try:
            year = int(float(str(year)))
            days = int(float(str(days)))
            hours = int(float(str(hours)))
            minutes = int(float(str(minutes)))
            seconds = int(float(str(seconds)))
        except Exception as e:
            logger.error(
                "error with conversion of %s,%s,%s,%s,%s",
                year,
                days,
                hours,
                minutes,
                seconds,
            )
            raise e

        tempsecs = seconds + 60 * minutes + 3600 * hours
        # finalsecs = np.floor(tempsecs)
        finalmicrosec = int(np.round(tempsecs * 10 ** 6))

        return (
                dt.datetime(year, 1, 1)
                + dt.timedelta(days - 1)
                + dt.timedelta(microseconds=finalmicrosec)
        )

    else:
        if not is_iterable(hours):
            hours = [0] * len(year)
        if not is_iterable(minutes):
            minutes = [0] * len(year)
        if not is_iterable(seconds):
            seconds = [0] * len(year)

        outlis = []
        typ = get_type_smart(year)
        for y, d, h, m, s in zip(year, days, hours, minutes, seconds):
            outlis.append(doy2dt(y, d, h, m, s))
        return typ(outlis)


def is_iterable(inp, consider_str_as_iterable=False):
    """
    Test if the input is an iterable like a list or a numpy array or not

    Parameters
    ----------
    inp : list, numpy.array, ...

    consider_str_as_iterable : bool
        string are considered as iterable by Python per default
        This boolean will avoid True as return if you test a string

    Returns
    -------
    out : bool
        True if inp is iterable, False either

    Note
    ----
    extracted from the GeodeZYX toolbox
    https://github.com/IPGP/geodezyx-toolbox
    """
    if not consider_str_as_iterable and type(inp) is str:
        return False

    try:
        iter(inp)
    except TypeError:
        out = False
    else:
        out = True
    return out


def get_type_smart(obj_in):
    """
    get type of an object, to convert easily another one to this type
    for instance type(np.array(A)) doesn't return a constructor

    Note
    ----
    extracted from the GeodeZYX toolbox
    https://github.com/IPGP/geodezyx-toolbox
    """
    typ = type(obj_in)
    if typ is np.ndarray:
        return np.array
    else:
        return typ
