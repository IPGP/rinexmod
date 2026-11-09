#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on 2026-08-02

@author: psakic

Low-level functions to import IGS sitelog metadata as dictionary
and extract instrumentation and site metadata.

"""

import configparser
import os
import re
from datetime import datetime

import rinexmod.logger as rimo_log

logger = rimo_log.logger_define("INFO")


def _tryparsedate(date):
    """
    Parse a date string with multiple format support.
    
    Different date format to test on the string in case of bad standard compliance.
    If the date cannot be parsed, returns 'infinity' date (9999-01-01).
    """
    formats = [
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%dT%H:%MZ",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M",
        "%Y/%m/%dT%H:%MZ",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%dT%H:%M:%SZ",
        "%d/%m/%YT%H:%MZ",
        "%d/%m/%Y %H:%M",
        "%d/%m/%YT%H:%M",
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d/%m/%Y",
    ]
    if date:
        # Parse to date trying different formats
        for fmt in formats:
            try:
                date = datetime.strptime(date, fmt)
                break
            except:
                pass
    if not isinstance(date, datetime):
        # We set the date to 'infinity' date. If not a date, it's because it's an open border.
        date = datetime.strptime("9999-01-01", "%Y-%m-%d")

    return date


def slg_file2raw(sitelogfile, keys_float=False):
    """
    First function for reading a Sitelog file.
    From the sitelog file, returns a dict with all readed values.
    
    Parameters
    ----------
    sitelogfile : str
        Path to the sitelog file
    keys_float : bool, optional
        If True, use float keys for contact sections. Default is False.
        
    Returns
    -------
    dict
        Dictionary containing all parsed values from the sitelog file
    """
    ###### Input and output file tests #######

    # Checking if inexisting file
    if not os.path.isfile(sitelogfile):
        return None

    ####### Reading Sitelog File #########

    # Reading the sitelog file
    try:
        with open(sitelogfile, "r", encoding="utf-8") as datafile:
            sitelog = datafile.read()
    except UnicodeDecodeError:  # OVPF sitelogs are in iso-8859-1
        try:
            with open(sitelogfile, "r", encoding="iso-8859-1") as datafile:
                sitelog = datafile.read()
        except:
            raise

    # We delete all initial space.
    pattern = re.compile(r"\n +")
    sitelog = re.sub(pattern, r"\n", sitelog)

    # We rearrange multiline content to be complient with .ini format.
    pattern = re.compile(r"(\n *): *")
    sitelog = re.sub(pattern, " ", sitelog)

    # We transform  multiple contacts into sub blocs
    pattern = re.compile(r"((?:Secondary|Primary) [Cc]ontact):{0,1}")
    sitelog = re.sub(pattern, r"[\1]", sitelog)

    # We remove the final graphic if exists
    antennagraphic = re.search(r"Antenna Graphics with Dimensions", sitelog)
    if antennagraphic:
        sitelog = sitelog[: antennagraphic.start(0)]

    # List of formated blocs
    formatedblocs = []
    # Final dict to store values
    slgdic = {}

    # We split the file into major blocs (reading the '4.'' type pattern)
    itr = re.finditer(r"\d{1,2}\. +.+\n", sitelog)
    indices = [m.start(0) for m in itr]

    blocs = [sitelog[i:j] for i, j in zip(indices, indices[1:] + [None])]

    if len(blocs) == 0:
        return None

    # We loop into those blocs, after a test that permits keeping only blocs
    # beginning with patterns like '6.'. This permits removing the title bloc.
    for bloc in [bloc for bloc in blocs if re.match(r"\d.", bloc[:2])]:

        # We search for '4.3', '4.3.', '4.2.3' patterns for subbloc detection
        itr = re.finditer(r"\n\d{1,2}\.\d{0,2}\.{0,1}\w{0,2}\.{0,1}", bloc)
        indices = [m.start(0) + 1 for m in itr]

        if len(indices) > 0:  # If subblocs
            subblocs = [bloc[i:j] for i, j in zip(indices, indices[1:] + [None])]

            for subbloc in subblocs:
                # We separate index (the first line) from values
                index, subbloc = subbloc.split("\n", 1)
                # If available, the data contained in the first line (now stored in index)
                # is pushed back in the subbloc varaible in a new 'type' entry.
                try:
                    index, title = index.split(" ", 1)
                    if ":" not in title:
                        title = "type : " + title
                    subbloc = title.lstrip() + "\n" + subbloc
                except Exception:
                    pass
                # We append the subbloc to the list of blocs to read
                formatedblocs.append([index, subbloc])

        elif re.search(r"\n", bloc):
            # Get index and bloc content
            index, bloc = bloc.split("\n", 1)
            index = re.match(r"\d{1,2}\.", index).group(0)

            # We append it to the list of blocs to read
            formatedblocs.append([index, bloc])

        else:
            pass

    # Now that blocs are formated, we read them with configparser
    for [index, bloc] in formatedblocs:

        if "x" in index[0:5]:
            pass  # If it's a model section (like 3.x), we don't proceed it
        else:
            # We add a section header to work on it with ConfigParser
            bloc = "[dummy_section]\n" + bloc

            cfgparser = configparser.RawConfigParser(allow_no_value=True)
            cfgparser.optionxform = str  # Respect case
            cfgparser.read_string(bloc)

            # We construct the bloc dict
            blocdict = {}
            for section_name in cfgparser.sections():
                # For 'dummy_section' section, we quit the section_name
                if section_name == "dummy_section":
                    blocdict.update(dict(cfgparser[section_name]))
                # For other sections (Primary & Secondary contact, added earlier), we keep the section_name
                else:
                    blocdict.update({section_name: dict(cfgparser[section_name])})

            # We append the bloc dict to the global dict
            if keys_float:
                keys_contact = [11.0, 12.0]
                slgdic[float(index)] = blocdict
            else:
                keys_contact = ["11.", "12."]
                slgdic[index] = blocdict

    # Contact corrections - putting the field 'Additional Information' in the right level dict
    # and removing network information
    for key in [key for key in slgdic.keys() if key in keys_contact]:
        if "network" in slgdic[key]["Agency"].lower():
            index_network = slgdic[key]["Agency"].lower().index("network")
            slgdic[key]["Agency"] = slgdic[key]["Agency"][:index_network]
        # Removing extra spaces
        slgdic[key]["Agency"] = slgdic[key]["Agency"].strip()
        slgdic[key]["Agency"] = " ".join(slgdic[key]["Agency"].split())
        if slgdic[key]["Secondary Contact"]["Additional Information"]:
            # Putting the 'Additional Information' in the lower level dict
            slgdic[key]["Additional Information"] = slgdic[key][
                "Secondary Contact"
            ]["Additional Information"]
            # Removing it from the incorrect dict level
            slgdic[key]["Secondary Contact"].pop("Additional Information", None)

    return slgdic


def slg_raw2instrus(raw_content):
    """
    This function identifies the different complete installations from the
    antenna and receiver change dates, then returns a list of dictionnaries
    with only instrumented periods.

    The output is a list containing one or several dictionaries with 3 keys
    'dates' 'receiver' 'antenna' and the following structure:

    Parameters
    ----------
    raw_content : dict
        Dictionary generated with slg_file2raw method

    Returns
    -------
    instrus : list
        List of installation dictionaries
    """

    ##### Constructing a list of date intervals from all changes dates #####

    listdates = []

    # We extract dates for blocs 3. and 4. (reveiver, antenna)
    keys = [
        k
        for k in raw_content.keys()
        if k.startswith("3.") or k.startswith("4.")
    ]

    for key in keys:
        # Formating parsed dates - set empty to 'infinity' date. If not a date, it's because it's an open border.
        raw_content[key]["Date Installed"] = _tryparsedate(
            raw_content[key]["Date Installed"]
        )
        raw_content[key]["Date Removed"] = _tryparsedate(
            raw_content[key]["Date Removed"]
        )
        # Adding dates to listdate
        listdates += (
            raw_content[key]["Date Installed"],
            raw_content[key]["Date Removed"],
        )

    # Quitting null values
    listdates = [date for date in listdates if date]
    # Quitting duplicates
    listdates = list(set(listdates))
    # Sorting
    listdates.sort()

    # List of installations. An installation is a date interval, a receiver and an antena
    instrus = []

    # Constructing the installations list - date intervals
    for i in range(0, len(listdates) - 1):
        # Construct interval from listdates
        dates = [listdates[i], listdates[i + 1]]
        # Setting date interval in Dict of installation
        ins = dict(dates=dates, receiver=None, antenna=None, metpack=None)
        # Append it to list of installations
        instrus.append(ins)

    ##### Getting Receiver info for each interval #####

    receivers = [
        raw_content[key]
        for key in raw_content.keys()
        if key.startswith("3.")
    ]

    # Constructing the installations list - Receivers
    for ins in instrus:
        # We get the receiver corresponding to the date interval
        for receiver in receivers:
            if (receiver["Date Installed"] <= ins["dates"][0]) and (
                receiver["Date Removed"] >= ins["dates"][1]
            ):
                ins["receiver"] = receiver
                # Once found, we quit the loop
                break

    ##### Getting Antenna info for each interval #####

    antennas = [
        raw_content[key]
        for key in raw_content.keys()
        if key.startswith("4.")
    ]

    # Constructing the installations list - Antennas
    for ins in instrus:
        # We get the antenna corresponding to the date interval
        for antenna in antennas:
            if (antenna["Date Installed"] <= ins["dates"][0]) and (
                antenna["Date Removed"] >= ins["dates"][1]
            ):
                ins["antenna"] = antenna
                # Once found, we quit the loop
                break

    ##### Removing from installation list periods without antenna or receiver

    instrus = [i for i in instrus if i["receiver"] and i["antenna"]]

    return instrus


def slg_raw2misc_meta(raw_content, site_id_getter=None):
    """
    This function generates the "misc meta" dictionary, i.e. a
    dictionary containing all the useful metadata information which are not
    stored in the instrumentation dictionary.

    Consistent with [IGSMAIL-8458] (2024-06-01)

    Parameters
    ----------
    raw_content : dict
        Dictionary generated with slg_file2raw method
    site_id_getter : callable, optional
        Function to extract site_id. If not provided, extracted from raw_content

    Returns
    -------
    dict : misc meta dictionary with keys: ID, IERS DOMES Number, operator, agency, X/Y/Z coordinates, date prepared, Country
    """

    if (
        "Nine Character ID" in raw_content["1."].keys()
    ):  # now consistent with [IGSMAIL-8458]
        site_id = raw_content["1."]["Nine Character ID"]
    else:
        site_id = raw_content["1."]["Four Character ID"]

    domes = raw_content["1."]["IERS DOMES Number"]

    operator = raw_content["11."]["Preferred Abbreviation"]
    agency = raw_content["12."]["Preferred Abbreviation"]

    x = raw_content["2."]["X coordinate (m)"]
    y = raw_content["2."]["Y coordinate (m)"]
    z = raw_content["2."]["Z coordinate (m)"]

    date_prepared = datetime.strptime(
        raw_content["0."]["Date Prepared"], "%Y-%m-%d"
    )

    if (
        "Country/Region" in raw_content["2."].keys()
    ):  # now consistent with [IGSMAIL-8458]
        country = raw_content["2."]["Country/Region"]
    elif (
        "Country or Region" in raw_content["2."].keys()
    ):  # now consistent with [IGSMAIL-8458]
        country = raw_content["2."]["Country or Region"]
    else:
        country = raw_content["2."]["Country"]

    misc_meta = dict(
        ID=site_id,
        **{"IERS DOMES Number": domes},
        operator=operator,
        agency=agency,
        **{"X coordinate (m)": float(x)},
        **{"Y coordinate (m)": float(y)},
        **{"Z coordinate (m)": float(z)},
        **{"date prepared": date_prepared},
        Country=country,
    )

    return misc_meta

