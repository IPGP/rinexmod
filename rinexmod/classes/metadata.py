#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Class
v1 - 2021-02-07 Félix Léger - felixleger@gmail.com
v2 - 2024-02-26 Pierre Sakic - sakic@ipgp.fr
"""

import copy
import json
import os
from datetime import datetime, timedelta
import pycountry

import pandas as pd

import rinexmod.readers.gamit as rimo_gmm
import rinexmod.readers.rinexmod_info as rimo_rmo
import rinexmod.readers.sitelog as rimo_slm
import rinexmod.readers.geodesyml as rimo_gml
import rinexmod.classes as rimo_cls

import rinexmod.api as rimo_api

import rinexmod.logger as rimo_log

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
    * find_instru4rnx will return a dict with all header metadatas that is
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

    def set_misc_meta(
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

    def set_from_sitelog(self, sitelogfile):
        """
        initialization method for metadata import from sitelog
        """
        self.path = sitelogfile
        self.filename = os.path.basename(self.path)
        self.raw_content = rimo_slm.slg_file2raw(self.path)

        if self.raw_content:
            self.instrus = rimo_slm.slg_raw2instrus(self.raw_content)
            self.misc_meta = rimo_slm.slg_raw2misc_meta(self.raw_content)
            self.site_id = self.misc_meta["ID"]

        else:
            self.instrus = None
            self.misc_meta = None
            self.site_id = self.filename[:4].lower()

        return None
    
    def set_from_gml(self, gmlfile):
        """
        This method initializes the metadata object from a GeodesyML file. 
        It uses the gml_file2raw method to parse the GeodesyML file and extract the raw content, which is then processed to populate the instrus and misc_meta attributes of the metadata object. 
        The site_id is also set based on the extracted metadata.
        """
        self.path = gmlfile
        self.filename = os.path.basename(self.path)
        self.raw_content = rimo_gml.gml_file2raw(self.path)

        if self.raw_content:
            self.instrus = rimo_gml.gml_raw2instrus(self.raw_content)
            self.misc_meta = rimo_gml.gml_raw2misc_meta(self.raw_content, self.filename)
            self.site_id = self.misc_meta["ID"]
        else:
            self.instrus = None
            self.misc_meta = None
            self.site_id = self.filename[:9].upper()

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
        ##### It has been clarified (2026-02)
        if len(site) == 4:
            self.site_id = site[:4].lower()
        elif len(site) == 9:
            self.site_id = site[:9].upper()
            self.misc_meta["ID"] = site.upper()
            self.misc_meta["Country"] = site[-3:].upper()
        else:
            logger.error("site %s must be 4 or 9 char. long, bad things will occur", site)
            self.site_id = site


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
                site=self.site_id4, ### must remain site_id4
                stinfo_df_inp=self.raw_content,
                apr_df_inp=self.raw_content_apr,
                force_fake_coords=force_fake_coords,
            )
        else:
            self.instrus, self.misc_meta = None, None

        return None

    def set_from_rinexmod_info(
        self,
        site,
        rinexmod_info,
        force_fake_coords=False,
        rinexmod_info_name="rinexmod.info",
    ):
        """
        Initialization method for metadata import from rinexmod.info CSV file.

        site can be 4 char or 9 char
        """

        # Site ID management (same as for GAMIT)
        if len(site) == 4:
            self.site_id = site[:4].lower()
        elif len(site) == 9:
            self.site_id = site[:9].upper()
            self.misc_meta["ID"] = site.upper()
            self.misc_meta["Country"] = site[-3:].upper()
        else:
            logger.error("site %s must be 4 or 9 char. long, bad things will occur", site)
            self.site_id = site

        if isinstance(rinexmod_info, pd.DataFrame):
            self.raw_content = rinexmod_info
            self.path = None
            self.filename = rinexmod_info_name
        else:
            self.raw_content = rimo_rmo.read_rinexmod_info(rinexmod_info)
            self.path = rinexmod_info
            self.filename = os.path.basename(self.path)

        if self.raw_content is not None:
            self.instrus, self.misc_meta = rimo_rmo.rinexmod_df2instru_miscmeta(
                site=self.site_id4,  ### must remain site_id4
                rinexmod_df_inp=self.raw_content,
                force_fake_coords=force_fake_coords,
            )
        else:
            self.instrus, self.misc_meta = None, None

        return None

    def set_from_rinex(self, rnxfile):
        """
        initialization method for metadata import from rinex header
        """
        self.path = rnxfile
        self.filename = os.path.basename(self.path)

        rnxobj = rimo_cls.RinexFile(self.path)
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
        self.set_misc_meta(
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

        for ins in self.instrus[1:]:
            # If the dates are overlapping, we merge the two periods
            if equal_instru(instru_use, ins):
                # Merge the two periods
                instru_use["dates"][0] = min(instru_use["dates"][0], ins["dates"][0])
                instru_use["dates"][1] = max(instru_use["dates"][1], ins["dates"][1])

                # Merge the receiver and antenna dictionaries
                for key in ["receiver", "antenna"]:
                    instru_use[key].update(ins[key])
            else:
                instrus_out.append(instru_use)
                instru_use = copy.deepcopy(ins)

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
        for ins in self.instrus:
            if date_source == "receiver":
                ins["dates"] = [
                    ins["receiver"]["Date Installed"],
                    ins["receiver"]["Date Removed"],
                ]
            elif date_source == "antenna":
                ins["dates"] = [
                    ins["antenna"]["Date Installed"],
                    ins["antenna"]["Date Removed"],
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

        for ins in self.instrus:
            ins["receiver"]["Date Installed"] = ins["dates"][0]
            ins["receiver"]["Date Removed"] = ins["dates"][1]
            ins["antenna"]["Date Installed"] = ins["dates"][0]
            ins["antenna"]["Date Removed"] = ins["dates"][1]

        return self.instrus

    #  ______                         _   _   _                __                  _   _
    # |  ____|                       | | | | (_)              / _|                | | (_)
    # | |__ ___  _ __ _ __ ___   __ _| |_| |_ _ _ __   __ _  | |_ _   _ _ __   ___| |_ _  ___  _ __  ___
    # |  __/ _ \| '__| '_ ` _ \ / _` | __| __| | '_ \ / _` | |  _| | | | '_ \ / __| __| |/ _ \| '_ \/ __|
    # | | | (_) | |  | | | | | | (_| | |_| |_| | | | | (_| | | | | |_| | | | | (__| |_| | (_) | | | \__ \
    # |_|  \___/|_|  |_| |_| |_|\__,_|\__|\__|_|_| |_|\__, | |_|  \__,_|_| |_|\___|\__|_|\___/|_| |_|___/
    #                                                  __/ |
    #                                                 |___/

    def find_instru(self, starttime, endtime, ignore=False, round_instru_dates=False):
        """
        Get the instrumentation corresponding to starttime and endtime.
        If ignore=True, firmware version changes between periods are ignored.
        If round_instru_dates=True, instru dates are rounded to day boundaries.
        """

        # Try exact match first

        dt1d = timedelta(minutes=1440)

        for ins in self.instrus:

            if round_instru_dates:
                ins_srt = rimo_api.round_time(
                    ins["dates"][0], date_delta=dt1d, to="down"
                )
                ins_end = rimo_api.round_time(
                    ins["dates"][1], date_delta=dt1d, to="up"
                )
            else:
                ins_srt = ins["dates"][0]
                ins_end = ins["dates"][1]

            if ins_srt <= starttime and ins_end >= endtime:
                return ins, False

        # If not found and ignore=True, check consecutive periods ignoring firmware
        if not ignore:
            return None, False

        # BACKUP CASE
        # If we can't find a corresponding installation period and we use the force
        # option, we will force ignoring the firmware version modification and
        # consider only the other parameters
        def compare_instru_ignore_firmware(instru1, instru2):
            """Helper to compare two instru periods ignoring dates and firmware."""
            exclude_keys = [
                "Date Removed",
                "Date Installed",
                "Additional Information",
                "Firmware Version",
            ]

            for key in ["antenna", "receiver"]:
                dict1 = {k: v for k, v in instru1[key].items() if k not in exclude_keys}
                dict2 = {k: v for k, v in instru2[key].items() if k not in exclude_keys}
                if dict1 != dict2:
                    return False

            return True

        for i in range(len(self.instrus) - 1):
            if not (
                self.instrus[i]["dates"][0] <= starttime
                and self.instrus[i + 1]["dates"][1] >= endtime
            ):
                continue

            # Compare periods without dates, firmware, and additional info
            if compare_instru_ignore_firmware(self.instrus[i], self.instrus[i + 1]):
                return self.instrus[i], True

        return None, False

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

    def get_xyz(self):
        """
        Return the X, Y, Z coordinates of the site as floats.
        """

        x = float(self.misc_meta["X coordinate (m)"])
        y = float(self.misc_meta["Y coordinate (m)"])
        z = float(self.misc_meta["Z coordinate (m)"])

        return x, y, z

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

    def find_instru4rnx(self, starttime, endtime, ignore=False, round_instru_dates=False):
        """
        Returns period's metadata in vars and dicts
        fitted for RinexFile modification methods.

        formerly rinex_metadata_lines
        """

        ### searching for the instrumentation corresponding to the period
        instru, ignored = self.find_instru(starttime, endtime, ignore, round_instru_dates)

        ### if no instrumentation found, we return None
        if not instru:
            logger.warning(f"No instru. found for period {starttime}-{endtime}.")
            return None, ignored

        def key_chk_instru(dic_inp, keys_inp):
            """
            Check if all keys in keys_inp are present in dic_inp.
            If not, raise an error.
            """
            for k in keys_inp:
                if k not in dic_inp.keys():
                    errmsg = f"Missing '{k}' for instru. period {starttime}-{endtime} ({dic_inp})"
                    # logger.error(errmsg)
                    raise KeyError(errmsg)

        ### get useful values in misc_meta
        fourchar_id = self.site_id4

        misc_meta = self.misc_meta

        try:
            key_chk_instru(
                misc_meta,
                [
                    "IERS DOMES Number",
                    "X coordinate (m)",
                    "Y coordinate (m)",
                    "Z coordinate (m)",
                    "operator",
                    "agency",
                ],
            )
        except KeyError as e:
            logger.error(e)
            raise e

        domes_id = misc_meta["IERS DOMES Number"]

        antenna_pos = {
            "X": misc_meta["X coordinate (m)"],
            "Y": misc_meta["Y coordinate (m)"],
            "Z": misc_meta["Z coordinate (m)"],
        }

        agencies = {
            "operator": misc_meta["operator"],
            "agency": misc_meta["agency"],
        }

        ### get useful values in instru_rec
        instru_rec = instru["receiver"]

        try:
            key_chk_instru(
                instru_rec,
                ["Serial Number", "Receiver Type", "Firmware Version", "Satellite System"],
            )
        except KeyError as e:
            try:
                # try geodesyML keys
                key_chk_instru(
                    instru_rec,
                    ["manufacturerSerialNumber", "igsModelCode", "firmwareVersion", "satelliteSystem"],
                )
                # remap keys
                instru_rec["Serial Number"] = instru_rec["manufacturerSerialNumber"]
                instru_rec["Receiver Type"] = instru_rec["igsModelCode"]
                instru_rec["Firmware Version"] = instru_rec["firmwareVersion"]
                # originally a list, transform to string with '+' separator like in sitelogs
                if isinstance(instru_rec["satelliteSystem"], list):
                    instru_rec["Satellite System"] = '+'.join(instru_rec["satelliteSystem"])
                else:
                    instru_rec["Satellite System"] = instru_rec["satelliteSystem"]
            except KeyError as e2:
                logger.error(e2)
                raise e2

        receiver = {
            "serial": instru_rec["Serial Number"],
            "type": instru_rec["Receiver Type"],
            "firmware": instru_rec["Firmware Version"],
        }
        observable_type = instru_rec["Satellite System"]

        ### get useful values in instru_ant
        instru_ant = instru["antenna"]

        try:
            key_chk_instru(
                instru_ant,
                [
                    "Serial Number",
                    "Antenna Type",
                    "Marker->ARP Up Ecc. (m)",
                    "Marker->ARP East Ecc(m)",
                    "Marker->ARP North Ecc(m)",
                ],
            )
        except KeyError as e:
            try:
                # try geodesyML keys
                key_chk_instru(
                    instru_ant,
                    [
                        "manufacturerSerialNumber",
                        "igsModelCode",
                        "marker-arpUpEcc.",
                        "marker-arpEastEcc.",
                        "marker-arpNorthEcc.",
                    ],
                )
                # remap keys
                instru_ant["Serial Number"] = instru_ant["manufacturerSerialNumber"]
                instru_ant["Antenna Type"] = instru_ant["igsModelCode"]
                instru_ant["Marker->ARP Up Ecc. (m)"] = instru_ant["marker-arpUpEcc."]
                instru_ant["Marker->ARP East Ecc(m)"] = instru_ant["marker-arpEastEcc."]
                instru_ant["Marker->ARP North Ecc(m)"] = instru_ant["marker-arpNorthEcc."]
            except KeyError as e2:
                logger.error(e2)
                raise e2

        antenna = {
            "serial": instru_ant["Serial Number"],
            "type": instru_ant["Antenna Type"],
        }

        antenna_delta = {
            "H": instru_ant["Marker->ARP Up Ecc. (m)"],
            "E": instru_ant["Marker->ARP East Ecc(m)"],
            "N": instru_ant["Marker->ARP North Ecc(m)"],
        }

        ### final output tuple
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

        for ins in self.instrus:
            rec_stk.append(ins["receiver"])
            ant_stk.append(ins["antenna"])

        def _stack_lines(instru_stk, instru_name="Receiver"):
            lines_instru_stk = []
            lastl1, lastl2, lastl3 = None, None, None

            inam = instru_name

            for _, inss in enumerate(instru_stk):
                l1 = " ".join((inam, inss[inam + " Type"], str(inss["Serial Number"])))
                l2 = "Installed on " + str(inss["Date Installed"])
                l3 = "Removed on " + str(inss["Date Removed"])

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