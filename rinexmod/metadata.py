#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Class
v1 - 2021-02-07 Félix Léger - felixleger@gmail.com
v2 - 2024-02-26 Pierre Sakic - sakic@ipgp.fr
"""

import configparser
import copy
import json
import os
import re
from datetime import datetime
import pycountry

import pandas as pd

import rinexmod.gamit_meta as rimo_gmm
import rinexmod.logger as rimo_log
import rinexmod.rinexfile
import rinexmod.rinexmod_api as rimo_api

logger = rimo_log.logger_define("INFO")


class MetaData:
    """
    Parses and stores in a dict information from an IGS sitelog or GAMIT-like files.
    Requires one parameter, the sitelog path.
    At instantiation, will parse the sitelog and store in a dict all parsed values.
    Dict accessible via MetaData.raw_content
    Will also create a tab, stored in MetaData.instrus, containing all
    the different instrumentation periods, tab containing a start and an end date,
    and for each line a dict of antenna instrumentation an receiver instrumentation.

    New 20240225: MetaData object can also be initialized as an empty one.
    (for GAMIT's station.info/apr/L-File import)
    thus sitelogfile can now be None

    4 available methods:
    * find_instru takes a start and an end date and returns the instrumentation
    corresponding to the period, if found. Option to ignore firmware version inconsistency.
    * teqcargs also takes a start and an end date and returns a string of args to
    pass to teqc so that it will modify a rinex file's header.
    * rinex_metadata_lines will return a dict with all header metadatas that is
    compatible with RinexFile header modifications methods.
    * write_json will write the dict of the parsed values from the sitelog to a
    json file.
    """

    def __init__(self, sitelogfile=None):
        if sitelogfile:
            ### usual case. read from a sitelog file
            self.set_from_sitelog(sitelogfile)
        else:
            ### more generic and flexible case. empty object
            self.path = None
            self.filename = None
            self._site_id = None
            # self.site4char = None
            # site9char is a more complex property bellow
            self.raw_content = None
            self.instrus = []
            self.misc_meta = {}
            self.raw_content_apr = None

    ### site
    @property
    def site_id(self):
        return self._site_id

    @site_id.setter
    def site_id(self, value):
        self._site_id = value

    @property
    def site_id4(self):
        return self._site_id[:4].lower()

    @property
    def site_id9(self):
        return rimo_api.make_site_id9(self.site_id)

    def __repr__(self):
        return "{} metadata, from {}".format(self.site_id, self.filename)

    def set_from_sitelog(self, sitelogfile):
        """
        initialization method for metadata import from sitelog
        """
        self.path = sitelogfile
        self.filename = os.path.basename(self.path)
        self.raw_content = self.slg_file2raw()

        if self.raw_content:
            self.instrus = self.slg_raw2instrus()
            self.misc_meta = self.slg_raw2misc_meta()
            self.site_id = self.misc_meta["ID"]

        else:
            self.instrus = None
            self.misc_meta = None
            self.site_id = self.filename[:4].lower()

        return None

    def set_from_gamit(
        self,
        site,
        station_info,
        lfile,
        force_fake_coords=False,
        station_info_name="station.info",
    ):
        """
        initialization method for metadata import from GAMIT files

        site can be 4 char or 9 char
        """

        ##### This site_id management is very strange, must be clarified
        self.site_id = site[:4].lower()
        if len(site) == 9:
            self.misc_meta["ID"] = site.upper()
            self.misc_meta["Country"] = site[-3:].upper()

        if isinstance(station_info, pd.DataFrame):
            self.raw_content = station_info
            self.path = None
            self.filename = station_info_name
        else:
            self.raw_content = rimo_gmm.read_gamit_station_info(self.path)
            self.path = station_info
            self.filename = os.path.basename(self.path)

        if isinstance(lfile, pd.DataFrame):
            self.raw_content_apr = lfile
        else:
            self.raw_content_apr = rimo_gmm.read_gamit_apr_lfile(lfile)

        if self.raw_content is not None:
            self.instrus, self.misc_meta = rimo_gmm.gamit_df2instru_miscmeta(
                site=self.site_id4,
                stinfo_df_inp=self.raw_content,
                apr_df_inp=self.raw_content_apr,
                force_fake_coords=force_fake_coords,
            )
        else:
            self.instrus, self.misc_meta = None, None

        return None

    def set_meta(
        self, site_id, domes, operator, agency, x, y, z, date_prepared, country
    ):
        """
        Exemple of misc meta dict:

        {
         'ID': 'PMZI00MYT',
         'IERS DOMES Number': '90109M001',
         'operator': 'OVPF-IPGP',
         'agency': 'IPGP',
         'X coordinate (m)': 4377557.000,
         'Y coordinate (m)': 4419689.300,
         'Z coordinate (m)': -1403760.500,
         'date prepared': datetime.datetime(2024, 9, 13, 0, 0),
         'Country': 'Mayotte'
        }
        """

        self.site_id = site_id

        self.misc_meta["ID"] = site_id
        self.misc_meta["IERS DOMES Number"] = domes
        self.misc_meta["operator"] = operator
        self.misc_meta["agency"] = agency
        self.misc_meta["X coordinate (m)"] = float(x)
        self.misc_meta["Y coordinate (m)"] = float(y)
        self.misc_meta["Z coordinate (m)"] = float(z)
        self.misc_meta["date prepared"] = date_prepared
        self.misc_meta["Country"] = country

        return self.misc_meta

    def set_from_rinex(self, rnxfile):
        """
        initialization method for metadata import from rinex header
        """
        self.path = rnxfile
        self.filename = os.path.basename(self.path)

        rnxobj = rinexmod.rinexfile.RinexFile(self.path)
        head_str, head_dic = rnxobj.get_header()

        self.site_id = head_dic["Marker name"]

        self.raw_content = head_str

        inst_dic = dict()
        ##### receiver
        rec_dic = dict()
        rec_dic["Receiver Type"] = head_dic["Receiver type"]
        rec_dic["Satellite System"] = "GPS+GLO+GAL+BDS+QZSS+SBAS"
        rec_dic["Serial Number"] = head_dic["Receiver serial"]
        rec_dic["Firmware Version"] = head_dic["Receiver firmware version"]
        rec_dic["Elevation Cutoff Setting"] = "0"
        rec_dic["Date Installed"] = head_dic["Start date and time"]
        rec_dic["Date Removed"] = head_dic["Final date and time"]
        rec_dic["Temperature Stabiliz."] = "none"
        rec_dic["Additional Information"] = "none"

        inst_dic["receiver"] = rec_dic

        ##### antenna
        ant_dic = dict()
        ecc = head_dic["Antenna delta (H/E/N)"].split()
        ant_dic["Antenna Type"] = head_dic["Antenna type"].strip()[:-4]
        ant_dic["Serial Number"] = head_dic["Antenna serial"]
        ant_dic["Antenna Reference Point"] = "none"
        ant_dic["Marker->ARP Up Ecc. (m)"] = float(ecc[0])
        ant_dic["Marker->ARP North Ecc(m)"] = float(ecc[1])
        ant_dic["Marker->ARP East Ecc(m)"] = float(ecc[2])
        ant_dic["Alignment from True N"] = 0.0
        ant_dic["Antenna Radome Type"] = head_dic["Antenna type"].strip()[-4:]
        ant_dic["Radome Serial Number"] = "none"
        ant_dic["Antenna Cable Type"] = "none"
        ant_dic["Antenna Cable Length"] = "0"
        ant_dic["Date Installed"] = head_dic["Start date and time"]
        ant_dic["Date Removed"] = head_dic["Final date and time"]
        ant_dic["Additional Information"] = "none"
        ant_dic["metpack"] = "none"

        inst_dic["antenna"] = ant_dic

        inst_dic["dates"] = [
            head_dic["Start date and time"],
            head_dic["Final date and time"],
        ]

        self.instrus = [inst_dic]

        xyz = head_dic["Antenna position (XYZ)"].split()
        self.set_meta(
            site_id=head_dic["Marker name"],
            domes=head_dic["Marker number"],
            operator=head_dic["Operator"],
            agency=head_dic["Agency"],
            x=float(xyz[0]),
            y=float(xyz[1]),
            z=float(xyz[2]),
            date_prepared=head_dic["Start date and time"],
            country="XXX",
        )

        return None

    def add_instru(self, rec_dic: dict, ant_dic: dict, date_srt=None, date_end=None):
        """
        Add an instrumentation period to instrus attribute the metadata object.

        Example of an instru dict:

         {
        'dates': [datetime.datetime(2008, 7, 8, 4, 48),
                  datetime.datetime(2009, 1, 1, 0, 0)],

        'receiver': {'Receiver Type': 'TPS GB-1000',
                     'Satellite System': 'GPS+GLO',
                     'Serial Number': 'T225373',
                     'Firmware Version': '3.32',
                     'Elevation Cutoff Setting': '15 deg',
                     'Date Installed': datetime.datetime(2008, 7, 8, 4, 48),
                     'Date Removed': datetime.datetime(2010, 3, 16, 5, 0),
                     'Temperature Stabiliz.': 'none',
                     'Additional Information': '(multiple lines)'},

          'antenna': {'Antenna Type': 'ASH701975.01A   NONE',
                      'Serial Number': '8279',
                      'Antenna Reference Point': 'TOP',
                      'Marker->ARP Up Ecc. (m)': '0.0000',
                      'Marker->ARP North Ecc(m)': '0.0000',
                      'Marker->ARP East Ecc(m)': '0.0000',
                      'Alignment from True N': '0 deg',
                      'Antenna Radome Type': 'NONE',
                      'Radome Serial Number': '',
                      'Antenna Cable Type': 'TNC',
                      'Antenna Cable Length': '4 m',
                      'Date Installed': datetime.datetime(2008, 3, 14, 0, 0),
                      'Date Removed': datetime.datetime(2009, 1, 1, 0, 0),
                      'Additional Information': 'La date de desinstallation est inconnue'},
                      'metpack': None
          }
        """

        date_srt = date_srt or datetime(1980, 1, 1)
        date_end = date_end or datetime(2099, 1, 1)

        instru_dic = dict()

        ### dates
        instru_dic["dates"] = [date_srt, date_end]
        ### receiver
        instru_dic["receiver"] = rec_dic
        instru_dic["receiver"]["Date Installed"] = date_srt
        instru_dic["receiver"]["Date Removed"] = date_end
        ### antenna
        instru_dic["antenna"] = ant_dic
        if (
            "Antenna Type" in ant_dic.keys()
            and not "Antenna Radome Type" in ant_dic.keys()
        ):
            ant_dic["Antenna Radome Type"] = ant_dic["Antenna Radome Type"][-4:]
        instru_dic["antenna"]["Date Installed"] = date_srt
        instru_dic["antenna"]["Date Removed"] = date_end
        ### append to instrus
        self.instrus.append(instru_dic)
        return instru_dic

    def sort_instrus(self):
        """
        Sort the instrumentation periods in the instrus attribute
        """

        self.instrus = sorted(self.instrus, key=lambda x: x["dates"][0])

        return self.instrus

    def merge_instrus(self):
        """
        Merge overlapping instrumentation periods in the `instrus` attribute.

        This method processes the `instrus` attribute, which is a list of instrumentation
        periods, and merges periods that overlap or are considered equal based on the
        `equal_instru` function. The merged periods are stored in the `instrus` attribute.

        Returns
        -------
        list
            A list of merged instrumentation periods.
        """

        instrus_out = []
        # Sort the instrumentation periods
        self.sort_instrus()
        instru_use = copy.deepcopy(self.instrus[0])

        for instru in self.instrus[1:]:
            # If the dates are overlapping, we merge the two periods
            if equal_instru(instru_use, instru):
                # Merge the two periods
                instru_use["dates"][0] = min(instru_use["dates"][0], instru["dates"][0])
                instru_use["dates"][1] = max(instru_use["dates"][1], instru["dates"][1])

                # Merge the receiver and antenna dictionaries
                for key in ["receiver", "antenna"]:
                    instru_use[key].update(instru[key])
            else:
                instrus_out.append(instru_use)
                instru_use = copy.deepcopy(instru)

        instrus_out.append(instru_use)

        self.instrus = instrus_out
        self.instrus_dates2recant_install()

        return self.instrus

    def instrus_recant_install2dates(self, date_source="receiver"):
        """
        Update the `dates` key in each instrumentation period based on the installation
        and removal dates of either the receiver or the antenna.

        This method processes the `instrus` attribute, which is a list of instrumentation
        periods, and updates the `dates` key for each period using the installation and
        removal dates from either the receiver or the antenna, depending on the specified
        `date_source`.

        Parameters
        ----------
        date_source : str, optional
            Specifies whether to use the receiver or antenna dates to update the `dates` key.
            Must be either "receiver" or "antenna". Default is "receiver".

        Returns
        -------
        list
            The updated list of instrumentation periods with the `dates` key set based on
            the specified `date_source`.

        Raises
        ------
        ValueError
            If `date_source` is not "receiver" or "antenna".
        """
        for instru in self.instrus:
            if date_source == "receiver":
                instru["dates"] = [
                    instru["receiver"]["Date Installed"],
                    instru["receiver"]["Date Removed"],
                ]
            elif date_source == "antenna":
                instru["dates"] = [
                    instru["antenna"]["Date Installed"],
                    instru["antenna"]["Date Removed"],
                ]
            else:
                raise ValueError("date_source must be 'receiver' or 'antenna'")
        return self.instrus

    def instrus_dates2recant_install(self):
        """
        Update the receiver and antenna installation dates in the `instrus` attribute
        based on the dates stored in the `dates` key of each instrumentation period.

        This method processes the `instrus` attribute, which is a list of instrumentation
        periods, and updates the installation dates for both the receiver and antenna
        based on the dates stored in the `dates` key.

        Returns
        -------
        list
            A list of instrumentation periods with updated installation dates.
        """

        for instru in self.instrus:
            instru["receiver"]["Date Installed"] = instru["dates"][0]
            instru["receiver"]["Date Removed"] = instru["dates"][1]
            instru["antenna"]["Date Installed"] = instru["dates"][0]
            instru["antenna"]["Date Removed"] = instru["dates"][1]

        return self.instrus

    #  _____               _                __                  _   _
    # |  __ \             (_)              / _|                | | (_)
    # | |__) |_ _ _ __ ___ _ _ __   __ _  | |_ _   _ _ __   ___| |_ _  ___  _ __  ___
    # |  ___/ _` | '__/ __| | '_ \ / _` | |  _| | | | '_ \ / __| __| |/ _ \| '_ \/ __|
    # | |  | (_| | |  \__ \ | | | | (_| | | | | |_| | | | | (__| |_| | (_) | | | \__ \
    # |_|   \__,_|_|  |___/_|_| |_|\__, | |_|  \__,_|_| |_|\___|\__|_|\___/|_| |_|___/
    #                               __/ |
    #                              |___/

    def slg_file2raw(self, keys_float=False):
        """
        First function for reading a Sitelog file.
        From the sitelog file,
        returns a dict with all readed values.
        """
        ###### Input and output file tests #######

        # Checking if inexisting file
        if not os.path.isfile(self.path):
            # print('The provided Sitelog is not valid : ' + self.path)
            return None, 2

        # Getting filename and basename for output purposes
        # filename = (os.path.splitext(os.path.basename(self.path))[0])
        # dirname = os.path.dirname(self.path)

        ####### Reading Sitelog File #########

        # Reading the sitelog file
        try:
            with open(self.path, "r", encoding="utf-8") as datafile:
                sitelog = datafile.read()
        except UnicodeDecodeError:  # OVPF sitelogs are in iso-8859-1
            try:
                with open(self.path, "r", encoding="iso-8859-1") as datafile:
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
            # print('The provided Sitelog is not correct : ' + self.path)
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

    def slg_raw2instrus(self):
        """
        This function identifies the different complete installations from the
        antenna and receiver change dates, then returns a list of dictionnaries
         with only instrumented periods.

        It uses the raw_content attribute (dictionary), generated with
        gen_raw_content_dict method.

        The output is a list containing one or several dictionaries with 3 keys
        'dates' 'receiver' 'antenna' and the following structure:

        Example of an instru dict:

         {
        'dates': [datetime.datetime(2008, 7, 8, 4, 48),
                  datetime.datetime(2009, 1, 1, 0, 0)],

        'receiver': {'Receiver Type': 'TPS GB-1000',
                     'Satellite System': 'GPS+GLO',
                     'Serial Number': 'T225373',
                     'Firmware Version': '3.32',
                     'Elevation Cutoff Setting': '15 deg',
                     'Date Installed': datetime.datetime(2008, 7, 8, 4, 48),
                     'Date Removed': datetime.datetime(2010, 3, 16, 5, 0),
                     'Temperature Stabiliz.': 'none',
                     'Additional Information': '(multiple lines)'},

          'antenna': {'Antenna Type': 'ASH701975.01A   NONE',
                      'Serial Number': '8279',
                      'Antenna Reference Point': 'TOP',
                      'Marker->ARP Up Ecc. (m)': '0.0000',
                      'Marker->ARP North Ecc(m)': '0.0000',
                      'Marker->ARP East Ecc(m)': '0.0000',
                      'Alignment from True N': '0 deg',
                      'Antenna Radome Type': 'NONE',
                      'Radome Serial Number': '',
                      'Antenna Cable Type': 'TNC',
                      'Antenna Cable Length': '4 m',
                      'Date Installed': datetime.datetime(2008, 3, 14, 0, 0),
                      'Date Removed': datetime.datetime(2009, 1, 1, 0, 0),
                      'Additional Information': 'La date de desinstallation est inconnue'},
                      'metpack': None
          }

        Returns
        -------
        instrus : list
        """

        ##### Constructing a list of date intervals from all changes dates #####

        listdates = []

        # We extract dates for blocs 3. and 4. (reveiver, antenna)
        keys = [
            k
            for k in self.raw_content.keys()
            if k.startswith("3.") or k.startswith("4.")
        ]

        for key in keys:
            # Formating parsed dates - set empty to 'infinity' date. If not a date, it's because it's an open border.
            self.raw_content[key]["Date Installed"] = self._tryparsedate(
                self.raw_content[key]["Date Installed"]
            )
            self.raw_content[key]["Date Removed"] = self._tryparsedate(
                self.raw_content[key]["Date Removed"]
            )
            # Adding dates to listdate
            listdates += (
                self.raw_content[key]["Date Installed"],
                self.raw_content[key]["Date Removed"],
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
            instru = dict(dates=dates, receiver=None, antenna=None, metpack=None)
            # Append it to list of installations
            instrus.append(instru)

        ##### Getting Receiver info for each interval #####

        receivers = [
            self.raw_content[key]
            for key in self.raw_content.keys()
            if key.startswith("3.")
        ]

        # Constructing the installations list - Receivers
        for instru in instrus:
            # We get the receiver corresponding to the date interval
            for receiver in receivers:
                if (receiver["Date Installed"] <= instru["dates"][0]) and (
                    receiver["Date Removed"] >= instru["dates"][1]
                ):
                    instru["receiver"] = receiver
                    # Once found, we quit the loop
                    break

        ##### Getting Antenna info for each interval #####

        antennas = [
            self.raw_content[key]
            for key in self.raw_content.keys()
            if key.startswith("4.")
        ]

        # Constructing the installations list - Antennas
        for instru in instrus:
            # We get the antenna corresponding to the date interval
            for antenna in antennas:
                if (antenna["Date Installed"] <= instru["dates"][0]) and (
                    antenna["Date Removed"] >= instru["dates"][1]
                ):
                    instru["antenna"] = antenna
                    # Once found, we quit the loop
                    break

        ##### Removing from installation list periods without antenna or receiver

        instrus = [i for i in instrus if i["receiver"] and i["antenna"]]

        return instrus

    @staticmethod
    def _tryparsedate(date):
        # Different date format to test on the string in case of bad standard compliance
        formats = [
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%dT%H:%MZ",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%dT%H:%M",
            "%Y/%m/%dT%H:%MZ",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%dT%H:%M",
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

    def slg_raw2misc_meta(self):
        """
        This function generates the "misc meta" dictionary, i.e. a
        dictionary containing all the useful metadata information which are not
        stored in the instrumentation dictionary
        (see slg_raw2instrus )

        Consistent with [IGSMAIL-8458] (2024-06-01)

        Exemple of misc meta dict:
        {
         'ID': 'PMZI00MYT',
         'IERS DOMES Number': '90109M001',
         'operator': 'OVPF-IPGP',
         'agency': 'IPGP',
         'X coordinate (m)': '4377557.000',
         'Y coordinate (m)': '4419689.300',
         'Z coordinate (m)': '-1403760.500',
         'date prepared': datetime.datetime(2024, 9, 13, 0, 0),
         'Country': 'Mayotte'
        }
        """

        if (
            "Nine Character ID" in self.raw_content["1."].keys()
        ):  # now consistent with [IGSMAIL-8458]
            site_id = self.raw_content["1."]["Nine Character ID"]
        else:
            site_id = self.raw_content["1."]["Four Character ID"]

        domes = self.raw_content["1."]["IERS DOMES Number"]

        operator = self.raw_content["11."]["Preferred Abbreviation"]
        agency = self.raw_content["12."]["Preferred Abbreviation"]

        x = self.raw_content["2."]["X coordinate (m)"]
        y = self.raw_content["2."]["Y coordinate (m)"]
        z = self.raw_content["2."]["Z coordinate (m)"]

        date_prepared = datetime.strptime(
            self.raw_content["0."]["Date Prepared"], "%Y-%m-%d"
        )

        if (
            "Country/Region" in self.raw_content["2."].keys()
        ):  # now consistent with [IGSMAIL-8458]
            country = self.raw_content["2."]["Country/Region"]
        elif (
            "Country or Region" in self.raw_content["2."].keys()
        ):  # now consistent with [IGSMAIL-8458]
            country = self.raw_content["2."]["Country or Region"]
        else:
            country = self.raw_content["2."]["Country"]

        self.misc_meta = dict()
        # We must initialize the misc_meta here
        # not initialized before (we are in the sitelog case)
        mm_dic = self.set_meta(
            site_id=site_id,
            domes=domes,
            operator=operator,
            agency=agency,
            x=x,
            y=y,
            z=z,
            date_prepared=date_prepared,
            country=country,
        )

        return mm_dic

    #  ______                         _   _   _                __                  _   _
    # |  ____|                       | | | | (_)              / _|                | | (_)
    # | |__ ___  _ __ _ __ ___   __ _| |_| |_ _ _ __   __ _  | |_ _   _ _ __   ___| |_ _  ___  _ __  ___
    # |  __/ _ \| '__| '_ ` _ \ / _` | __| __| | '_ \ / _` | |  _| | | | '_ \ / __| __| |/ _ \| '_ \/ __|
    # | | | (_) | |  | | | | | | (_| | |_| |_| | | | | (_| | | | | |_| | | | | (__| |_| | (_) | | | \__ \
    # |_|  \___/|_|  |_| |_| |_|\__,_|\__|\__|_|_| |_|\__, | |_|  \__,_|_| |_|\___|\__|_|\___/|_| |_|___/
    #                                                  __/ |
    #                                                 |___/

    def find_instru(self, starttime, endtime, ignore=False):
        """
        We get the instrumentation corresponding to the starttime and endtime.
        If ignore option set to True, we will force ignoring the firmware version
        modification between two periods and consider only the other parameters.
        """

        # We get the installation corresponding to the starttime and endtime
        found_install = None
        ignored = False

        # REGULAR CASE
        for install in self.instrus:
            if install["dates"][0] <= starttime and install["dates"][1] >= endtime:
                found_install = install
                break

        # BACKUP CASE
        # If we can't find a corresponding installation period and we use the force
        # option, we will force ignoring the firmware version modification and
        # consider only the other parameters
        if not found_install and ignore:
            # We work with consecutive instrumentation periods
            for i in range(0, len(self.instrus) - 1):
                if (
                    self.instrus[i]["dates"][0] <= starttime
                    and self.instrus[i + 1]["dates"][1] >= endtime
                ):

                    # we copy the two instrumentation periods dictionnary to remove firmware info
                    nofirmware_instru_i = copy.deepcopy(self.instrus[i])
                    nofirmware_instru_i1 = copy.deepcopy(self.instrus[i + 1])

                    # We remove date infos
                    nofirmware_instru_i.pop("dates")
                    nofirmware_instru_i1.pop("dates")
                    for e in [
                        "Date Removed",
                        "Date Installed",
                        "Additional Information",
                    ]:
                        nofirmware_instru_i["antenna"].pop(e)
                        nofirmware_instru_i["receiver"].pop(e)
                        nofirmware_instru_i1["antenna"].pop(e)
                        nofirmware_instru_i1["receiver"].pop(e)

                    # We remove Firmware info
                    nofirmware_instru_i["receiver"].pop("Firmware Version")
                    nofirmware_instru_i1["receiver"].pop("Firmware Version")

                    # If, except dates and firmware version, the dicts are equls, we set
                    # instrumentation to the first one of the two.
                    if nofirmware_instru_i == nofirmware_instru_i1:
                        found_install = self.instrus[i]
                        ignored = True

        return found_install, ignored

    def get_country(self, iso_code=True):
        """
        Return the ISO country code based on the Sitelog's Country field.
        Requires pycountry module

        Consistent with [IGSMAIL-8458] (2024-06-01)
        """

        raw_country = self.misc_meta["Country"]

        #### The raw input is a 3-letter ISO code, now consistent with [IGSMAIL-8458]
        if len(raw_country) == 3:
            iso_country = raw_country
            try:
                full_country = pycountry.countries.get(alpha_3=iso_country).name
            except:
                full_country = "Somewhere"

        #### The raw input is a full country name
        else:
            full_country = raw_country
            full_country2 = full_country.split("(the)")[0].strip()
            try:
                iso_country = pycountry.countries.get(name=full_country2).alpha_3
            except:
                iso_country = "XXX"

        if iso_code:
            return iso_country
        else:
            return full_country

    def teqcargs(self, starttime, endtime, ignore=False):
        """
        Will return a string of teqc args containing all infos from the sitelog,
        including instrumentation infos taking into account a start and an end date.
        If ignore option set to True, we will force ignoring the firmware version
        modification between two periods and consider only the other parameters.
        """

        instru, ignored = self.find_instru(starttime, endtime, ignore)

        if not instru:
            return "", ignored

        ########### GNSS one-letter codes ###########

        # From https://www.unavco.org/software/data-processing/teqc/tutorial/tutorial.html
        gnss_codes = dict(
            GPS="G", GLO="R", GAL="E", BDS="C", QZSS="J", IRNSS="I", SBAS="S"
        )

        # GNSS system. M if multiple, else, one letter code from gnss_codes dict.
        o_system = instru["receiver"]["Satellite System"]
        if "+" in o_system:
            o_system = "M"
        else:
            o_system = gnss_codes[o_system]

        # We construct the TEQC args line
        teqcargs = [
            "-O.mo[nument] '{}'".format(self.raw_content["1."]["ID"][:4]),
            "-M.mo[nument] '{}'".format(self.raw_content["1."]["ID"][:4]),
            "-O.mn '{}'".format(self.raw_content["1."]["ID"][:4]),
            "-O.px[WGS84xyz,m] {} {} {}".format(
                self.raw_content["2."]["X coordinate (m)"],
                self.raw_content["2."]["Y coordinate (m)"],
                self.raw_content["2."]["Z coordinate (m)"],
            ),
            "-O.s[ystem] {}".format(o_system),
            "-O.rt '{}'".format(instru["receiver"]["Receiver Type"]),
            "-O.rn '{}'".format(instru["receiver"]["Serial Number"]),
            "-O.rv '{}'".format(instru["receiver"]["Firmware Version"]),
            "-O.at '{}'".format(instru["antenna"]["Antenna Type"]),
            "-O.an '{}'".format(instru["antenna"]["Serial Number"]),
            "-O.pe[hEN,m] {} {} {}".format(
                instru["antenna"]["Marker->ARP Up Ecc. (m)"].zfill(8),
                instru["antenna"]["Marker->ARP East Ecc(m)"].zfill(8),
                instru["antenna"]["Marker->ARP North Ecc(m)"].zfill(8),
            ),
            "-O.o[perator] '{}'".format(
                self.raw_content["11."]["Preferred Abbreviation"]
            ),
            "-O.r[un_by] '{}'".format(
                self.raw_content["11."]["Preferred Abbreviation"]
            ),
            "-O.ag[ency] '{}'".format(
                self.raw_content["12."]["Preferred Abbreviation"]
            ),
        ]

        return teqcargs, ignored

    def rinex_metadata_lines(self, starttime, endtime, ignore=False):
        """
        Returns period's metadata in vars and dicts
        fitted for RinexFile modification methods.
        """

        instru, ignored = self.find_instru(starttime, endtime, ignore)

        if not instru:
            return None, ignored

        fourchar_id = self.site_id4
        domes_id = self.misc_meta["IERS DOMES Number"]

        observable_type = instru["receiver"]["Satellite System"]

        agencies = {
            "operator": self.misc_meta["operator"],
            "agency": self.misc_meta["agency"],
        }

        receiver = {
            "serial": instru["receiver"]["Serial Number"],
            "type": instru["receiver"]["Receiver Type"],
            "firmware": instru["receiver"]["Firmware Version"],
        }

        antenna = {
            "serial": instru["antenna"]["Serial Number"],
            "type": instru["antenna"]["Antenna Type"],
        }

        antenna_pos = {
            "X": self.misc_meta["X coordinate (m)"],
            "Y": self.misc_meta["Y coordinate (m)"],
            "Z": self.misc_meta["Z coordinate (m)"],
        }

        antenna_delta = {
            "H": instru["antenna"]["Marker->ARP Up Ecc. (m)"],
            "E": instru["antenna"]["Marker->ARP East Ecc(m)"],
            "N": instru["antenna"]["Marker->ARP North Ecc(m)"],
        }

        metadata_vars = (
            fourchar_id,
            domes_id,
            observable_type,
            agencies,
            receiver,
            antenna,
            antenna_pos,
            antenna_delta,
        )

        return metadata_vars, ignored

    def rinex_full_history_lines(self):
        """
        Get the sting lines to have the full site history in the RINEX header
        """
        rec_stk = []
        ant_stk = []

        for instru in self.instrus:
            rec_stk.append(instru["receiver"])
            ant_stk.append(instru["antenna"])

        def _stack_lines(instru_stk, instru_name="Receiver"):
            lines_instru_stk = []
            lastl1, lastl2, lastl3 = None, None, None

            for iins, ins in enumerate(instru_stk):
                l1 = " ".join(
                    (instru_name, ins[instru_name + " Type"], ins["Serial Number"])
                )
                l2 = "Installed on " + str(ins["Date Installed"])
                l3 = "Removed on " + str(ins["Date Removed"])

                if l1 == lastl1 and l2 == lastl2 and l3 == lastl3:
                    continue
                else:
                    lines_instru_stk.append(l1)
                    lines_instru_stk.append(l2)
                    lines_instru_stk.append(l3)
                    lastl1 = l1
                    lastl2 = l2
                    lastl3 = l3

            return lines_instru_stk

        return _stack_lines(rec_stk, "Receiver") + _stack_lines(ant_stk, "Antenna")

    def write_json(self, output=None):
        """
        Writes sitelog's dict to json. If no output provided, will write it in
        the same directory as the sitelog.
        """

        filename = os.path.splitext(os.path.basename(self.path))[0]
        if not output:
            output = os.path.dirname(self.path)
        elif not os.path.isdir(output):
            logger.error("error, output folder incorrect " + output)
            return None

        outputfilejson = os.path.join(output, filename + ".json")
        with open(outputfilejson, "w+") as j:
            json.dump(self.raw_content, j, default=str)

        return outputfilejson


def equal_instru(instru1, instru2, compare_dates=False):
    """
    Compare two instrumentation dict. and return True if they are equal
    """

    # Compare dates
    if compare_dates and (instru1["dates"] != instru2["dates"]):
        return False

    # Lambda function to filter out 'Date Installed' and 'Date Removed' keys
    filter_keys = lambda d: {
        k: v for k, v in d.items() if k not in ["Date Installed", "Date Removed"]
    }

    # Compare receiver
    if filter_keys(instru1["receiver"]) != filter_keys(instru2["receiver"]):
        return False

    # Compare antenna
    if filter_keys(instru1["antenna"]) != filter_keys(instru2["antenna"]):
        return False

    return True

    # def stationinfo(self, output = None):
    #     '''
    #     Attempt of writing a function that will write a stationinfo file from a
    #     list of sitelogs. This function writes a list of almost- stationinfo compatible
    #     entries, plus a header. To work, you have to write the XXX-marked lines that are
    #     not yet complient with stationinfo format, and make an external function to
    #     combine the lines from differetn sitelogs and add the header line.
    #     '''
    #
    #     if output:
    #         if not os.path.isdir(output):
    #             print("error, output folder incorrect " + output)
    #             return None
    #
    #     header = []
    #
    #     now = datetime.strftime(datetime.now(), '%Y-%m-%d %H%M')
    #
    #     header.append("# Station.raw_content written by Rinexmod user             on ".format(now))
    #     header.append("* Reference file : station.raw_content")
    #     header.append("*")
    #     header.append("*")
    #     header.append("*SITE  Station Name      Session Start      Session Stop       Ant Ht   HtCod  Ant N    Ant E    Receiver Type         Vers                  SwVer  Receiver SN           Antenna Type     Dome   Antenna SN")
    #
    #     stationinfo = []
    #
    #     SITE = self.raw_content['1.']['Four Character ID']
    #     Station_Name = self.raw_content['1.']['Site Name']
    #
    #     pattern = re.compile(r'[ 0](0+)[0-9]')
    #
    #     for installation in self.instrus:
    #
    #         Session_Start = installation['dates'][0]
    #         # print(type(Session_Start))
    #         Session_Start = datetime.strftime(Session_Start, '%Y %j %H %M %S')
    #         Session_Start = re.sub(pattern, ' ', Session_Start)
    #
    #         # Session_Start = Session_Start.replace(' 00', '   ')
    #         # Session_Start = Session_Start.replace(' 0', '  ')
    #         # Session_Start = Session_Start.replace('  00', '   0')
    #         # Session_Start = Session_Start.replace(' 00', '  0')
    #
    #         Session_Stop = installation['dates'][1]
    #         # print(type(Session_Stop))
    #
    #         # Session_Stop = Session_Stop - timedelta(seconds=1)
    #         Session_Stop = datetime.strftime(Session_Stop, '%Y %j %H %M %S')
    #         Session_Stop = re.sub(pattern, ' ', Session_Stop)
    #         # Session_Stop = Session_Stop.replace(' 0', '  ')
    #         #
    #         # Session_Start = Session_Start.replace('  00', '   0')
    #         # Session_Stop = Session_Stop.replace(' 00', '  0')
    #
    #         Ant_Ht = installation['antenna']['Marker->ARP Up Ecc. (m)']
    #         HtCod = None #installation['antenna'][''] #
    #         Ant_N = installation['antenna']['Marker->ARP North Ecc(m)']
    #         Ant_E = installation['antenna']['Marker->ARP East Ecc(m)']
    #         Receiver_Type = installation['receiver']['Receiver Type']
    #         Vers = None #installation['receiver'][''] #
    #         SwVer = installation['receiver']['Firmware Version']
    #         Receiver_SN = installation['receiver']['Serial Number']
    #         Antenna_Type = installation['antenna']['Antenna Type']
    #         Dome = installation['antenna']['Antenna Radome Type']
    #         Antenna_SN = installation['antenna']['Serial Number']
    #
    #         info_line = [SITE,
    #                      Station_Name,
    #                      Session_Start,
    #                      Session_Stop,
    #                      Ant_Ht,
    #                      HtCod,
    #                      Ant_N,
    #                      Ant_E,
    #                      Receiver_Type,
    #                      Vers,
    #                      SwVer,
    #                      Receiver_SN,
    #                      Antenna_Type,
    #                      Dome,
    #                      Antenna_SN]
    #
    #         stationinfo.append(info_line)
    #
    #     return stationinfo
