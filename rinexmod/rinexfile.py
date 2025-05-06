#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Class
2022-02-01 Félix Léger - felixleger@gmail.com & sakic@ipgp.fr
"""

import os
import re
import string
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path

import hatanaka

# import matplotlib.pyplot as plt
import numpy as np

import rinexmod.logger as rimo_log

logger = rimo_log.logger_define("INFO")


# logger = logging.getLogger("rinexmod_api")

# from rinexmod import rinexmod_api as rimo_api
# logger = rimo_api.logger_define('INFO')


# *****************************************************************************
# class definition
class RinexFile:
    """
    Will store a compressed rinex file content in a file-like list of strings
    using the hatanaka library.
    Will then provide methods to modifiy the file's header.
    The method to get the sample rate will read the whole file and will set as
    unknow sample rate files that have more than 10% of non-nominal sample rate.
    The method to get the file duration is based on reading the file name and
    not the data.
    A method to write the file in selected compression is also available.
    The get_header method permits to have a printable string of all file's metadata.
    """

    def __init__(self, rinex_input, force_rnx_load=False):

        ##### the RINEX input is a file, thus a string or a Path is given
        if type(rinex_input) in (str, Path):
            self.source_from_file = True
            self.path = rinex_input.strip()
            self.path_output = ""
            self.content_input = self.path
        ##### the RINEX input is directely data, in a StringIO
        elif type(rinex_input) is StringIO:
            self.source_from_file = False
            self.path = ""
            self.path_output = ""
            self.content_input = bytes(
                rinex_input.read(), "utf-8"
            )  ## ready-to-read for hatanaka
        else:
            logger.error("input rinex_input is not str, Path, or StringIO")

        self.rinex_data, self.status = self._load_rinexdata(
            force_rnx_load=force_rnx_load
        )
        self.size = self.get_size()
        self.name_conv = self.get_naming_convention()
        self.compression, self.hatanka_input = self.get_compression()
        self.filename = self.get_filename()
        self.data_source = self.get_data_source()

        #### site is an internal attribute, always 9char
        # (filled with 00XXX in nothing else is provided)
        # it is accessible wit get_site()
        self._site = self.get_site_from_filename(lower_case=False, only_4char=False)

        self.version, self.version_float = self.get_version()
        self.start_date, self.end_date = self.get_dates()
        self.sample_rate_string, self.sample_rate_numeric = self.get_sample_rate(
            plot=False
        )
        # self.file_period, self.session = self.get_file_period_from_filename()
        self.file_period, self.session = self.get_file_period_from_data(
            inplace_set=False
        )
        ### NB: here, when we load the RINEX, we remain tolerant for the file period!!

    def __repr__(self):
        """
        Defines a representation method for the rinex file object. Will print the
        filename, the site, the start and end date, the sample rate, the file period,
        the rinex version, the data source, the compression type, the size of the file,
        and the status of the file.
        """
        if not self.rinex_data:
            return ""

        return (
            f"RinexFile: {self.filename}\n"
            f"Site: {self.get_site()}\n"
            f"Start date: {self.start_date}\n"
            f"End date: {self.end_date}\n"
            f"Sample rate: {self.sample_rate_string}\n"
            f"File period: {self.file_period}\n"
            f"Rinex version: {self.version}\n"
            f"Data source: {self.data_source}\n"
            f"Compression: {self.compression}\n"
            f"Size: {self.size} bytes\n"
            f"Status: {self.status}"
        )

    def __str__(self):
        """
        Defines a print method for the rinex file object. Will print all the
        header, plus 20 lines of data, plus the number of not printed lines.
        """
        if not self.rinex_data:
            return ""

        # We get header
        end_of_header_idx = search_idx_value(self.rinex_data, "END OF HEADER") + 1
        str_rinex_file = self.rinex_data[0:end_of_header_idx]
        # We add 20 lines of data
        str_rinex_file.extend(
            self.rinex_data[end_of_header_idx : end_of_header_idx + 20]
        )
        # We add a line that contains the number of lines not to be printed
        length = len(self.rinex_data) - len(str_rinex_file) - 20
        cut_lines_rep = (
            " " * 20
            + "["
            + "{} lines hidden".format(length).center(40, ".")
            + "]"
            + " " * 20
        )
        str_rinex_file.append(cut_lines_rep)

        return "\n".join(str_rinex_file)

    # *****************************************************************************
    #### Main methods

    def get_header(self):
        """
        Returns a printable, with carriage-return, string of metadata lines from
        the header, and a python dict of the same information.
        """

        # if self.status not in [0, 2]:
        #    return None

        if self.status:
            return None

        metadata = {}

        metadata_lines = [
            "RINEX VERSION / TYPE",
            "MARKER NAME",
            "MARKER NUMBER",
            "OBSERVER / AGENCY",
            "REC # / TYPE / VERS",
            "ANT # / TYPE",
            "APPROX POSITION XYZ",
            "ANTENNA: DELTA H/E/N",
            "TIME OF FIRST OBS",
        ]

        missing_metadata_lines = []
        for kw in metadata_lines:
            for line in self.rinex_data:
                if kw in line:
                    metadata[kw] = line
                    break
                if "END OF HEADER" in line:
                    missing_metadata_lines.append(kw)
                    break

        for miss_kw in missing_metadata_lines:
            logger.warning("%s field is missing in %s header", miss_kw, self.filename)
            metadata[miss_kw] = ""

        ### previous case with just 'MARKER NUMBER', too weak hardcoded solution
        # if not 'MARKER NUMBER' in metadata:
        #    metadata['MARKER NUMBER'] = ''

        header_parsed = {
            "File": self.path,
            "File size (bytes)": self.size,
            "Rinex version": metadata["RINEX VERSION / TYPE"][0:9].strip(),
            "Sample rate": self.sample_rate_string,
            "File period": self.file_period,
            "Observable type": metadata["RINEX VERSION / TYPE"][40:60].strip(),
            "Marker name": metadata["MARKER NAME"][0:60].strip(),
            "Marker number": metadata["MARKER NUMBER"][0:60].strip(),
            "Operator": metadata["OBSERVER / AGENCY"][0:20].strip(),
            "Agency": metadata["OBSERVER / AGENCY"][20:40].strip(),
            "Receiver serial": metadata["REC # / TYPE / VERS"][0:20].strip(),
            "Receiver type": metadata["REC # / TYPE / VERS"][20:40].strip(),
            "Receiver firmware version": metadata["REC # / TYPE / VERS"][40:60].strip(),
            "Antenna serial": metadata["ANT # / TYPE"][0:20].strip(),
            "Antenna type": metadata["ANT # / TYPE"][20:40].strip(),
            "Antenna position (XYZ)": "{:14} {:14} {:14}".format(
                metadata["APPROX POSITION XYZ"][0:14].strip(),
                metadata["APPROX POSITION XYZ"][14:28].strip(),
                metadata["APPROX POSITION XYZ"][28:42].strip(),
            ),
            "Antenna delta (H/E/N)": "{:14} {:14} {:14}".format(
                metadata["ANTENNA: DELTA H/E/N"][0:14].strip(),
                metadata["ANTENNA: DELTA H/E/N"][14:28].strip(),
                metadata["ANTENNA: DELTA H/E/N"][28:42].strip(),
            ),
            "Start date and time": self.start_date,
            "Final date and time": self.end_date,
        }

        header_string = "\n".join(
            ["{:29} : {}".format(key, value) for key, value in header_parsed.items()]
        )

        header_string = "\n" + header_string + "\n"

        return header_string, header_parsed


    def get_site(self, lower_case=True, only_4char=False, no_country_then_4char=False):
        """
        Get the site of the Rinex Object
        if no_country_then_4char = True, the return site code
        falls back to a 4-char code, if no monum/country is provided
        (i.e. the 9char code ends with 00XXX)
        if no_country_then_4char = False, 00XXX will remain
        """

        site_out = self._site

        if lower_case:
            site_out = site_out.lower()
        else:
            site_out = site_out.upper()

        if only_4char or (no_country_then_4char and site_out[-3:] == "XXX"):
            site_out = site_out[0:4]

        return site_out

    def set_site(self, site_4or9char, monum=None, country=None):
        """
        set site for a Rinex Object
        monum and country overrides the ones given if site_4or9char
        is 9 char. long
        """

        if len(site_4or9char) not in (4, 9):
            logger.error("given site is not 4 nor 9 char. long!")
            return None

        if len(site_4or9char) == 4:
            if not monum:
                monum = "00"
            if not country:
                country = "XXX"
            self._site = site_4or9char + monum + country
        else:
            if not monum:
                monum = site_4or9char[4:6]
            if not country:
                country = site_4or9char[6:]
            self._site = site_4or9char + monum + country

        return None

    def get_longname(
        self,
        data_source="R",
        obs_type="O",
        ext="auto",
        compression="auto",
        filename_style="basic",
        inplace_set=False,
    ):
        """
        Generate the long RINEX filename.
        Can be stored directly as filename attribute with inplace=True.

        Parameters
        ----------
        data_source : str, optional
            The data source identifier. Default is 'R'.
        obs_type : str, optional
            The observation type. Default is 'O'.
        ext : str, optional
            The file extension. 'auto' to determine based on the RinexFile attribute,
            or manually specify 'rnx' or 'crx'. Default is 'auto'.
        compression : str, optional
            The compression type. 'auto' to determine based on the RinexFile attribute,
            or manually specify 'Z', 'gz', etc. Default is 'auto'.
        filename_style : str, optional
            The style of the filename.
             Possible values are 'basic', 'flex', 'exact'.
             See the rinexmod main function's docstring/help for more details.
             Default is 'basic'.
        inplace_set : bool, optional
            If True, stores the generated filename directly as the filename attribute.
            Default is False.

        Returns
        -------
        str
            The generated long RINEX filename.
        """

        # +++++ set extension
        if ext == "auto" and self.hatanka_input:
            ext = "crx"
        elif ext == "auto" and not self.hatanka_input:
            ext = "rnx"
        else:
            ext = "rnx"

        ext = "." + ext

        # +++++ set compression
        if compression == "auto" and self.compression:
            compression = "." + self.compression
        elif compression == "auto" and not self.compression:
            compression = ""
        elif (
            compression != ""
        ):  # when a manual compression arg is given, and is not void
            compression = "." + compression
        else:
            compression = ""

        # +++++ set file period and session
        self.mod_file_period(filename_style=filename_style)
        file_period_name = self.file_period
        session_name = self.session

        # +++++ set time format
        # default time format
        timeformat = "%Y%j%H%M"

        if file_period_name == "01D":  ## Daily case
            if session_name:
                timeformat = "%Y%j%H%M"
            else:
                timeformat = "%Y%j0000"  # Start of the day
        elif file_period_name[-1] == "M":  ### Subhourly case
            timeformat = "%Y%j%H%M"
        elif (
            file_period_name == "00U"
        ):  ## Unknown case: the filename deserves a full description to identify potential bug
            timeformat = "%Y%j%H%M"
        else:  ## Hourly case
            if filename_style in ("basic", "flex"):
                timeformat = "%Y%j%H00"  # Start of the hour
            elif filename_style == "exact":
                timeformat = "%Y%j%H%M"  # start of the minute

        longname = "_".join(
            (
                self.get_site(False, False),
                data_source,
                self.start_date.strftime(timeformat),
                file_period_name,
                self.sample_rate_string,
                self.get_sat_system() + obs_type + ext + compression,
            )
        )

        if inplace_set:
            self.filename = longname
            self.name_conv = "LONG"

        return longname

    def get_shortname(
        self,
        file_type="auto",
        compression="auto",
        filename_style="basic",
        inplace_set=False,
    ):
        """
        Generate the short RINEX filename.
        Can be stored directly as filename attribute with inplace=True.

        Parameters
        ----------
        file_type : str, optional
            'auto' (based on the RinexFile attribute) or manual: 'o', 'd', etc. Default is 'auto'.
        compression : str, optional
            'auto' (based on the RinexFile attribute) or manual: 'Z', 'gz', etc. Default is 'auto'.
            The value is given without a dot as the first character.
        filename_style : str, optional
            The style of the filename.
             Possible values are 'basic', 'flex', 'exact'.
             See the rinexmod main function's docstring/help for more details.
             Default is 'basic'.
        inplace_set : bool, optional
            If True, stores the generated filename directly as the filename attribute. Default is False.

        Returns
        -------
        str
            The generated short RINEX filename.
        """

        if file_type == "auto" and self.hatanka_input:
            file_type = "d"
        elif file_type == "auto" and not self.hatanka_input:
            file_type = "o"

        if compression == "auto":
            compression = self.compression

        if compression != "":
            compression = "." + compression

        self.mod_file_period(filename_style=filename_style)
        file_period_name = self.file_period
        session_name = self.session

        alphabet = list(map(chr, range(97, 123)))
        if file_period_name[-1] == "H":
            timeformat = (
                "%j" + alphabet[self.start_date.hour] + ".%y" + file_type + compression
            )
            start_date_use = self.start_date

        elif file_period_name[-1] == "M":
            timeformat = (
                "%j"
                + alphabet[self.start_date.hour]
                + "%M"
                + ".%y"
                + file_type
                + compression
            )
            start_date_use = round_time(
                self.start_date, timedelta(minutes=5), to="down"
            )

        else:  # regular case file_period_name == "01D"
            timeformat = "%j0.%y" + file_type + compression
            start_date_use = self.start_date

        shortname = self.get_site(True, True) + start_date_use.strftime(timeformat)

        if inplace_set:
            self.filename = shortname
            self.name_conv = "SHORT"

        return shortname

    def get_header_body(self, return_index_end=False):
        """
        Get the RINEX's header and body as a list of lines,
        and the index of the END OF HEADER line if asked
        """
        i_end = None
        i_end = search_idx_value(self.rinex_data, "END OF HEADER")

        head = self.rinex_data[: i_end + 1]
        body = self.rinex_data[i_end + 1 :]

        if return_index_end:
            return head, body, i_end
        else:
            return head, body

    # *****************************************************************************
    ### internal methods

    def _load_rinexdata(self, force_rnx_load=False):
        """
        Load the uncompressed rinex data into a list var using hatanaka library.
        Will return a table of lines of the uncompressed file, a 'name_conv' var
        that indicates if the file is named with the SHORT NAME convention or the
        LONG NAME convetion, and a status. Status 0 is OK. The other ones
        corresponds to the errors codes raised by rinexarchive and by rinexmod.
        01 - The specified file does not exists
        02 - Not an observation Rinex file
        03 - Invalid  or empty Zip file
        04 - Invalid Compressed Rinex file
        """

        ##### IF input is a file, checking if file exists
        if self.source_from_file and not os.path.isfile(self.path):
            rinex_data = None
            status = "01 - The specified file does not exists"
        ##### The input is a file
        else:
            try:
                rinex_data = hatanaka.decompress(self.content_input).decode("utf-8")
                rinex_data = rinex_data.split("\n")
                status = None

            except ValueError:
                rinex_data = None
                status = "03 - Invalid or empty compressed file"

            except hatanaka.hatanaka.HatanakaException:
                rinex_data = None
                status = "04 - Invalid Compressed RINEX file"

            if status:
                logger.error(status)

            if rinex_data:
                bool_l1_obs = "OBSERVATION DATA" in rinex_data[0]
                bool_l1_crx = "COMPACT RINEX FORMAT" in rinex_data[0]
            else:
                bool_l1_obs = False
                bool_l1_crx = False

            if not force_rnx_load and not (bool_l1_obs or bool_l1_crx):
                logger.error(
                    "File's 1st line does not match an Observation RINEX: "
                    + os.path.join(self.path)
                )
                logger.error("try to force the loading with force_rnx_load = True")
                rinex_data = None
                status = "02 - Not an observation RINEX file"

        if status:
            logger.error(status)

        return rinex_data, status
 #   _____      _     __  __      _   _               _
 #  / ____|    | |   |  \/  |    | | | |             | |
 # | |  __  ___| |_  | \  / | ___| |_| |__   ___   __| |___
 # | | |_ |/ _ \ __| | |\/| |/ _ \ __| '_ \ / _ \ / _` / __|
 # | |__| |  __/ |_  | |  | |  __/ |_| | | | (_) | (_| \__ \
 #  \_____|\___|\__| |_|  |_|\___|\__|_| |_|\___/ \__,_|___/
 #

    def get_naming_convention(self):
        """
        Get the naming convention based on a regular expression test
        """
        # Daily or hourly, hatanaka or not, gz or Z compressed file
        pattern_dic = regex_pattern_rinex_filename()

        pattern_shortname = re.compile(pattern_dic["shortname"])
        pattern_longname = re.compile(pattern_dic["longname"])
        # GFZ's DataCenter internal naming convention (here it is equivalent to a longname)
        pattern_longname_gfz = re.compile(pattern_dic["longname_gfz"])

        if pattern_shortname.match(os.path.basename(self.path)):
            name_conv = "SHORT"
        elif pattern_longname.match(os.path.basename(self.path)):
            name_conv = "LONG"
        elif pattern_longname_gfz.match(os.path.basename(self.path)):
            name_conv = "LONGGFZ"
        else:
            name_conv = "UNKNOWN"

        return name_conv

    def get_size(self):
        """
        Get RINEX file size
        """

        if self.status:
            return 0

        if self.source_from_file:
            size = os.path.getsize(self.path)
        else:
            size = 0

        return size

    def get_compression(self):
        """
        get the compression type in a 2-tuple: (compress,hatanaka)
        compress is None or a string: gz, Z, 7z
        hatanaka is a bool
        """

        basename = os.path.basename(self.path)

        # find compress value
        if basename.lower().endswith("z"):
            compress = os.path.splitext(basename)[1][1:]
        else:
            compress = None

        # find hatanaka value
        if self.name_conv == "SHORT":

            if compress:
                type_letter = basename.split(".")[-2][-1]
            else:
                type_letter = basename[-1]

            if type_letter == "d":
                hatanaka_bool = True
            else:
                hatanaka_bool = False

        else:  # LONG name
            if compress:
                type_ext = basename.split(".")[-2][-3:]
            else:
                type_ext = basename[-3:]

            if type_ext == "crx":
                hatanaka_bool = True
            else:
                hatanaka_bool = False

        return compress, hatanaka_bool

    def get_filename(self):
        """
        Get filename WITHOUT its compression extension
        """

        if self.status:
            return None

        if not self.compression:
            filename = os.path.basename(self.path)
        else:
            basename = os.path.splitext(os.path.basename(self.path))
            filename = basename[0]

        return filename

    def get_version(self):
        """
        Get RINEX version
        """

        if self.status:
            return ""

        version_header_idx = search_idx_value(self.rinex_data, "RINEX VERSION / TYPE")
        version_header = self.rinex_data[version_header_idx]
        # Parse line
        rinex_ver_head_str = str(version_header[0:9].strip())
        rinex_ver_head_flt = float(
            re.search(r"[+-]?([0-9]+([.][0-9]*)?|[.][0-9]+)", rinex_ver_head_str)[0]
        )
        # must fit a regex pattern of a float, because nasty hidder characters can be present

        return rinex_ver_head_str, rinex_ver_head_flt

    def get_data_source(self):
        """
        Get data source: R, S, U from LONG filename, R per default
        """

        if self.status:
            return None

        if not "LONG" in self.name_conv:
            src = "R"
        else:
            src = self.filename[10]

        return src

    def _get_date_patterns(self):
        """
        Internal function to get the correct epoch pattern depending
        on the RINEX version

        Returns
        -------
        date_pattern : str
            a regex matching the epoch pattern.
        year_prefix : str
            for RINEX2, the year prefix.
        """
        # Date lines pattern
        if self.version_float >= 3.0:
            # Pattern of an observation line containing a date - RINEX 3
            # date_pattern = re.compile('> (\d{4}) (\d{2}) (\d{2}) (\d{2}) (\d{2}) ((?: |\d)\d.\d{4})')
            date_pattern = re.compile(
                r"> (\d{4}) (\d{2}| \d) (\d{2}| \d) (\d{2}| \d) (\d{2}| \d) ((?: |\d)\d.\d{4})"
            )
            year_prefix = ""  # Prefix of year for date formatting

        elif self.version_float < 3:
            # Pattern of an observation line containing a date - RINEX 2
            date_pattern = re.compile(
                r" (\d{2}) ((?: |\d)\d{1}) ((?: |\d)\d{1}) ((?: |\d)\d{1}) ((?: |\d)\d{1}) ((?: |\d)\d{1}.\d{4})"
            )
            year_prefix = "20"  # Prefix of year for date formatting
            ### !!!!!!!!! before 2000 must be implemented !!!!!!
        else:
            logger.warning("unable to find right RINEX version")
            date_pattern = None
            year_prefix = None

        return date_pattern, year_prefix

    def get_dates(self):
        """
        Get start and end date from rinex file.
        we search for the date of the first and last observation directly in
        the data.
        if you want the values in the header, use get_dates_in_header
        """

        if self.status:
            return None, None

        def _find_first_last_epoch_line(rnxobj, last_epoch=False):

            date_pattern, year_pattern = rnxobj._get_date_patterns()

            if last_epoch:
                datause = reversed(rnxobj.rinex_data)
            else:
                datause = rnxobj.rinex_data

            # Searching the last one of the file
            m = None
            for line in datause:
                m = re.search(date_pattern, line)
                if m:
                    break
            if m:
                year = year_pattern + m.group(1)

                # Building a date string
                epoc = (
                    year
                    + " "
                    + m.group(2)
                    + " "
                    + m.group(3)
                    + " "
                    + m.group(4)
                    + " "
                    + m.group(5)
                    + " "
                    + m.group(6)
                )

                epoc = datetime.strptime(epoc, "%Y %m %d %H %M %S.%f")
            else:
                epoc = None

            return epoc

        start_epoch = _find_first_last_epoch_line(self)
        end_epoch = _find_first_last_epoch_line(self, last_epoch=True)

        return start_epoch, end_epoch

    def get_dates_in_header(self):
        """
        Get start and end date from rinex file.
        Start date cames from TIME OF FIRST OBS file's header.
        In RINEX3, there's a TIME OF LAST OBS in the header but it's not available
        in RINEX2, so we search for the date of the last observation directly in
        the data.
        """

        if self.status:
            return None, None

        def _find_meta_label(meta_label_in):
            line = None
            line_found = None
            for line in self.rinex_data:
                if re.search(meta_label_in, line):
                    line_found = line
                    break
            # If not found
            if not line_found:
                date_out = None
            else:
                date_out = line.split()
                date_out = datetime.strptime(
                    " ".join(date_out[0:6]), "%Y %m %d %H %M %S.%f0"
                )
            return date_out

        start_head = _find_meta_label("TIME OF FIRST OBS")
        end_head = _find_meta_label("TIME OF LAST OBS")

        return start_head, end_head

    def get_dates_all(self):
        """
        Returns all the epochs in the RINEX
        """
        if self.status:
            return None, None

        samples_stack = []

        date_pattern, _ = self._get_date_patterns()

        for line in self.rinex_data:  # We get all the epochs dates
            if re.search(date_pattern, line):
                samples_stack.append(re.search(date_pattern, line))

        return samples_stack

    def get_sample_rate(self, plot=False):
        """
        Get sample rate from rinex file.
        The method returns 2 outputs: a str sample rate for the RINEX filenames, and the float value
        We get all the samples dates and get intervals. We then remove 0 ones (due to potential double samples).
        Then, we set the most frequent value as sample rate, and if more than 10% of the intervals are different
        from this sample rate, we set the sample rate as unknown (XXU).
        If there is not enought samples to compute an interval (less than two samples), we raise an error
        with error code 5. If there is only two samples, i.e. one interval, we set the sample rate to
        unknown because we can not compute a most frequent interval.
        We then round the obtained value and translate it to a rinex 3 longname compliant format.
        If plot is set to True, will plot the samples intervals.
        """

        if self.status:
            return None, None

        samples_stack = self.get_dates_all()
        date_pattern, year_prefix = self._get_date_patterns()

        # If less than 2 samples, can't get a sample rate
        if len(samples_stack) < 2:
            self.status = "05 - Less than two epochs in the file"
            logger.error(
                "less than 2 samples found, can't get a sample rate %s",
                samples_stack,
            )
            return None, None

        # Building a date string
        def _date_conv(sample):
            date = (
                year_prefix
                + sample.group(1)
                + " "
                + sample.group(2)
                + " "
                + sample.group(3)
                + " "
                + sample.group(4)
                + " "
                + sample.group(5)
                + " "
                + sample.group(6)
            )

            date = datetime.strptime(date, "%Y %m %d %H %M %S.%f")
            return date

        # Format dates to datetime
        samples_stack = [_date_conv(d) for d in samples_stack]
        samples_rate_diff = np.diff(np.array(samples_stack))  # Getting intervals
        # Converting timedelta to seconds and removing 0 values (potential doubles in epochs)
        samples_rate_diff = [
            diff.total_seconds()
            for diff in samples_rate_diff
            if diff != timedelta(seconds=0)
        ]

        # If less than one interval after removing 0 values, can't get a sample rate
        if len(samples_rate_diff) < 1:
            self.status = "05 - Less than two epochs in the file"
            logger.error(
                "less than one interval after removing 0 values %s",
                samples_rate_diff,
            )
            return None, None

        # If less than 2 intervals, can't compare intervals
        if len(samples_rate_diff) < 2:
            return "00U", 0.0

        # Most frequent
        sample_rate_num = max(set(samples_rate_diff), key=samples_rate_diff.count)

        # Counting the intervals that are not equal to the most frequent
        num_bad_sp = len(
            [diff for diff in samples_rate_diff if diff != sample_rate_num]
        )

        non_nominal_interval_percent = num_bad_sp / len(samples_rate_diff)

        plot = False
        if plot:
            import matplotlib.pyplot as plt

            print(
                "{:29} : {}".format(
                    "Sample intervals not nominals",
                    str(non_nominal_interval_percent * 100) + " %",
                )
            )
            plt.plot(samples_rate_diff)
            plt.show()

        non_nominal_trigger = 0.45
        if (
            non_nominal_interval_percent > non_nominal_trigger
        ):  # Don't set sample rate to files
            # That have more that 45% of non nominal sample rate
            logger.error(
                "non nominal sample rate >%d%%: %d%% (# epochs: %d)",
                non_nominal_trigger * 100,
                non_nominal_interval_percent * 100,
                len(samples_stack),
            )
            return "00U", 0.0

        # Format of sample rate from RINEX3 specs : RINEX Long Filenames
        # We round samples rates to avoid leap-seconds related problems
        if sample_rate_num <= 0.0001:
            # XXU – Unspecified
            sample_rate_str = "00U"
        elif sample_rate_num <= 0.01:
            # XXC – 100 Hertz
            sample_rate_num = round(sample_rate_num, 4)
            sample_rate_str = (str(int(1 / (100 * sample_rate_num))) + "C").rjust(
                3, "0"
            )
        elif sample_rate_num < 1:
            # XXZ – Hertz
            sample_rate_num = round(sample_rate_num, 2)
            sample_rate_str = (str(int(1 / sample_rate_num)) + "Z").rjust(3, "0")
        elif sample_rate_num < 60:
            # XXS – Seconds
            sample_rate_num = round(sample_rate_num, 0)
            sample_rate_str = (str(int(sample_rate_num)) + "S").rjust(3, "0")
        ##### NB: a sample rate at the minute level or even above is very unlikely
        elif sample_rate_num < 3600:
            # XXM – Minutes
            sample_rate_num = round(sample_rate_num, 0)
            sample_rate_str = (str(int(sample_rate_num / 60)) + "M").rjust(3, "0")
        elif sample_rate_num < 86400:
            # XXH – Hours
            sample_rate_num = round(sample_rate_num, 0)
            sample_rate_str = (str(int(sample_rate_num / 3600)) + "H").rjust(3, "0")
        elif sample_rate_num <= 8553600:
            # XXD – Days
            sample_rate_num = round(sample_rate_num, 0)
            sample_rate_str = (str(int(sample_rate_num / 86400)) + "D").rjust(3, "0")
        else:
            # XXU – Unspecified
            sample_rate_str = "00U"

        return sample_rate_str, sample_rate_num

    def get_file_period_from_filename(self):
        """
        Get the file period from the file's name.
        In long name convention, gets it striaght from the file name.
        In short name convention, traduces digit to '01H' and '0' to 01D
        """

        if self.status:
            return None, None

        session = False

        if self.name_conv == "SHORT":
            file_period = self.filename[7:8]
            if file_period.isdigit():
                if file_period != "0":
                    session = True
                # 01D–1 Day
                file_period = "01D"
            elif file_period.isalpha():
                # 01H–1 Hour
                file_period = "01H"
            else:
                # 00U-Unspecified
                file_period = "00U"

        elif self.name_conv == "LONG":
            file_period = self.filename[24:27]

        elif self.name_conv == "LONGGFZ":
            file_period = self.filename[46:49]
        else:
            # 00U-Unspecified
            file_period = "00U"

        return file_period, session

    #         the RINEX file period is tolerant and stick to the actual data content,
    #         but then can be odd (e.g. 07H, 14H...). A strict file period is applied
    #         per default (01H or 01D), being compatible with the IGS conventions

    def get_file_period_from_data(self, inplace_set=False):
        """
        Get the file period from the data themselves.

        see also mod_file_period_basic()
        to round this value to a conventional one

        Parameters
        ----------
        inplace_set : bool, optional
            change the values in the RinexFile object. The default is False.

        Returns
        -------
        file_period : str
            the file period: '01H', '01D', '00U'...
        session : bool
            RINEX is a hourly session or not.

        """

        file_period, session = file_period_from_timedelta(
            self.start_date, self.end_date
        )

        if inplace_set:
            self.file_period = file_period
            self.session = session

        return file_period, session

    def mod_file_period(self, filename_style="basic"):

        self.get_file_period_from_data(inplace_set=True)

        if filename_style == "basic":
            self.mod_file_period_basic()
        elif filename_style in ("flex", "exact"):
            pass  ## it is the same as get_file_period_from_data()
        else:
            logger.error(
                "style %s not recognized. Accepts only 'basic', 'flex', 'exact'",
                filename_style,
            )

        return self.file_period, self.session

    def mod_file_period_basic(self):
        """
        Round the RINEX file period to a basic conventional value: 01D, 01H

        NB: this method aims to respect the IGS convention and thus uses NOMINAL
        period

        For the time beeing, it does not handle the subhourly case

        Returns
        -------
        file_period_rnd : str
            the file period: '01H', '01D', '00U'...
        session_rnd : bool or None
            the RINEX is an hourly session or not.

        """

        if self.file_period[2] == "H" and int(self.file_period[:2]) > 1:
            file_period_rnd = "01D"
            session_rnd = False
        else:
            file_period_rnd = self.file_period
            session_rnd = self.session

        self.file_period = file_period_rnd
        self.session = session_rnd

        return file_period_rnd, session_rnd

    def get_sat_system(self):
        """
        Parse RINEX VERSION / TYPE line to get observable type
        """

        if self.status:
            return None

        # Identify line that contains RINEX VERSION / TYPE
        sat_system_header_idx = search_idx_value(
            self.rinex_data, "RINEX VERSION / TYPE"
        )
        sat_system_head = self.rinex_data[sat_system_header_idx]
        # Parse line
        sat_system = sat_system_head[40:41]

        return sat_system

    def get_site_from_filename(self, lower_case=True, only_4char=False):
        """
        Get site name from the filename
        """

        if self.status:
            return None

        if self.name_conv in ("LONG", "LONGGFZ"):
            site_out = self.filename[:9]
        else:
            site_out = self.filename[:4] + "00" + "XXX"

        if only_4char:
            site_out = site_out[:9]

        if lower_case:
            return site_out.lower()
        else:
            return site_out.upper()

    def get_site_from_header(self):
        """
        Get site name from the MARKER NAME line in rinex file's header
        """

        if self.status:
            return ""

        site_head = "MARKER NAME"

        for line in self.rinex_data:
            if re.search(site_head, line):
                site_head = line
                break

        if site_head == "MARKER NAME":
            return None

        site_head = site_head.split(" ")[0].upper()

        return site_head

    def get_sys_obs_types(self):
        """
        Get the systems/observables values from the
        ``SYS / # / OBS TYPES`` lines

        for RINEX 3/4 only

        Returns
        -------
        dict_sys_obs : dict
            a dictionary of lists describing the observables per system, e.g.:
            ``{"G" : ["C1C","C1W","C2W","L1C","L2W","S1C",S2W"]}``.

        dict_sys_nobs : dict
            a dictionary of integer describing the number of observables per system, e.g.:
            ``{'C': 8, 'E': 16, 'G': 16, 'I': 4, 'R': 12, 'S': 4}``.

        """

        if self.status:
            return

        if self.version_float < 3:
            logger.warn("get_sys_obs_types is only compatible with RINEX3/4")
            return

        # Identify line that contains SYS / # / OBS TYPES
        sys_obs_idx0 = search_idx_value(self.rinex_data, "SYS / # / OBS TYPES")

        sys_obs_idx_fin = sys_obs_idx0
        while "SYS / # / OBS TYPES" in self.rinex_data[sys_obs_idx_fin]:
            sys_obs_idx_fin += 1

        #### get the systems and observations
        lines_sys = self.rinex_data[sys_obs_idx0:sys_obs_idx_fin]

        ## clean SYS / # / OBS TYPES
        lines_sys = [l[:60] for l in lines_sys]

        ## manage the 2 lines systems => they are stacked in one
        for il, l in enumerate(lines_sys):
            if l[0] == " ":
                lines_sys[il - 1] = lines_sys[il - 1] + l
                lines_sys.remove(l)

        #### store system and observables in a dictionnary
        dict_sys_obs = dict()
        dict_sys_nobs = dict()

        for il, l in enumerate(lines_sys):
            sysobs = l.split()
            sys = sysobs[0]
            dict_sys_obs[sys] = sysobs[2:]
            dict_sys_nobs[sys] = int(sysobs[1])
            ## adds the LLI and SSI indicators
            if len(sysobs[2:]) != int(sysobs[1]):
                logger.warn(
                    "difference between theorectical (%d) and actual (%d) obs nbr for sys (%s)",
                    len(sysobs[2:]),
                    int(sysobs[1]),
                    sys,
                )

        return dict_sys_obs, dict_sys_nobs

     #  __  __           _   __  __      _   _               _
     # |  \/  |         | | |  \/  |    | | | |             | |
     # | \  / | ___   __| | | \  / | ___| |_| |__   ___   __| |___
     # | |\/| |/ _ \ / _` | | |\/| |/ _ \ __| '_ \ / _ \ / _` / __|
     # | |  | | (_) | (_| | | |  | |  __/ |_| | | | (_) | (_| \__ \
     # |_|  |_|\___/ \__,_| |_|  |_|\___|\__|_| |_|\___/ \__,_|___/


    ### ***************************************************************************
    ### mod methods. change the content of the RINEX header

    def mod_marker(self, marker_inp=None, number_inp=None):
        """
        Modify within the RINEX header the marker
        (``MARKER NAME`` line)

        Parameters
        ----------
        marker_inp : str, optional
            site marker ID a.k.a. station code (4 or 9 characters).
            The default is None.
        number_inp : str, optional
            DOMES number. The default is None.

        Returns
        -------
        None.
        """

        if self.status:
            return

        ###marker_inp is a mandatory arguement, no None!
        if not marker_inp and not number_inp:
            return

        marker_name_header_idx = search_idx_value(self.rinex_data, "MARKER NAME")
        # Identify line that contains MARKER NAME
        if marker_inp:
            # Edit line
            new_line = "{}".format(marker_inp.ljust(60)) + "MARKER NAME"
            if marker_name_header_idx:
                # marker_name_meta = self.rinex_data[marker_name_header_idx]
                # Set line
                self.rinex_data[marker_name_header_idx] = new_line
            else:
                pgm_header_idx = search_idx_value(self.rinex_data, "PGM / RUN BY / DATE")
                self.rinex_data.insert(pgm_header_idx, new_line)

        if number_inp:
            # Identify line that contains MARKER NUMBER
            ## marker_number_header_idx = next((i for i, e in enumerate(self.rinex_data) if 'MARKER NUMBER' in e), None)
            marker_number_header_idx = search_idx_value(
                self.rinex_data, "MARKER NUMBER"
            )
            # Edit line
            new_line = "{}".format(number_inp.ljust(60)) + "MARKER NUMBER"
            if marker_number_header_idx:  # The line exsits
                # Set line
                self.rinex_data[marker_number_header_idx] = new_line
            else:  # The line does not exsits
                # Set line
                self.rinex_data.insert(marker_name_header_idx + 1, new_line)

        return

    def mod_receiver(self, serial=None, type=None, firmware=None, keep_rnx_rec=False):
        """
        Modify within the RINEX header the receiver information
        (``REC # / TYPE / VERS`` line)

        Parameters
        ----------
        serial : str, optional
            Receiver Serial Number. The default is None.
        type : str, optional
            Receiver model. The default is None.
        firmware : str, optional
            Firmware version. The default is None.
        keep_rnx_rec : bool, optional
            Keep the RINEX receiver header record in the output RINEX.
            Metadata from the external source (e.g. sitelogs) will not be modded.

        Returns
        -------
        None.

        """

        if self.status:
            return

        if not any([serial, type, firmware]):
            return

        # Identify line that contains REC # / TYPE / VERS
        receiver_header_idx = search_idx_value(self.rinex_data, "REC # / TYPE / VERS")
        receiver_head = self.rinex_data[receiver_header_idx]
        # Parse line
        serial_head = receiver_head[0:20]
        type_head = receiver_head[20:40]
        firmware_head = receiver_head[40:60]
        label_head = receiver_head[60:]

        # warning: for the receiver, info in te input RINEX might be the correct ones
        def _mod_rec_check(field_type, rinex_val, metadata_val):
            if metadata_val and rinex_val.strip() != metadata_val.strip():
                logger.warning(
                    "%s rec. %s in RINEX (%s) & in metadata (%s) are different.",
                    self.get_site(lower_case=False),
                    field_type,
                    rinex_val.strip(),
                    metadata_val.strip(),
                )
                logger.warning(
                    "The RINEX value might be the correct one, double-check your metadata source."
                )
                return True
                # True if the check fails: counter-intuitive, but makes sense for the test below
            else:
                return False

        rec_chk_sn = _mod_rec_check("serial number", rinex_val=serial_head, metadata_val=serial)
        rec_chk_mt = _mod_rec_check("model type", rinex_val=type_head, metadata_val=type)
        rec_chk_fw = _mod_rec_check(
            "firmware version", rinex_val=firmware_head, metadata_val=firmware
        )

        if keep_rnx_rec and (rec_chk_sn or rec_chk_fw or rec_chk_fw):
            logger.info("RINEX & metadata are different, but receiver values are kept (keep_rnx_rec = True)")
            return

        # Edit line
        if serial:
            serial_head = str(serial)[:20].ljust(20)
        if type:
            type_head = str(type)[:20].ljust(20)
        if firmware:
            firmware_head = str(firmware)[:20].ljust(20)
        new_line = serial_head + type_head + firmware_head + label_head
        # Set line
        self.rinex_data[receiver_header_idx] = new_line

        return

    def mod_antenna(self, serial=None, type=None):
        """
        Modify within the RINEX header the antenna information
        (``ANT # / TYPE`` line)

        Parameters
        ----------
        serial : str, optional
            Antenne Serial Number. The default is None.
        type : str, optional
            Antenna model. The default is None.

        Returns
        -------
        None.

        """

        if self.status:
            return

        if not any([serial, type]):
            return

        # Identify line that contains ANT # / TYPE
        antenna_header_idx = search_idx_value(self.rinex_data, "ANT # / TYPE")
        antenna_head = self.rinex_data[antenna_header_idx]
        # Parse line
        serial_head = antenna_head[0:20]
        type_head = antenna_head[20:40]
        label_head = antenna_head[60:]
        # Edit line
        if serial:
            serial_head = str(serial)[:20].ljust(20)
        if type:
            type_head = str(type)[:20].ljust(20)
        new_line = serial_head + type_head + " " * 20 + label_head
        # Set line
        self.rinex_data[antenna_header_idx] = new_line

        return

    def mod_interval(self, sample_rate_input=None):
        """
        Modify within the RINEX header the data sample rate
        (``INTERVAL`` line)

        Parameters
        ----------
        sample_rate_input : TYPE, optional
            Data sample rate. The default is None.

        Returns
        -------
        None.

        """

        if self.status:
            return

        if not any([sample_rate_input]):
            return

        # Identify line that contains INTERVAL
        line_exists = False
        idx = -1
        interval_idx = None

        for e in self.rinex_data:
            idx += 1
            if "INTERVAL" in e:
                line_exists = True
                interval_idx = idx
                break
            elif "TIME OF FIRST OBS" in e:
                interval_idx = idx
            elif "END OF HEADER" in e:
                break
            else:
                continue

        if line_exists:
            # interval_idx = next(i for i, e in enumerate(self.rinex_data) if 'INTERVAL' in e)
            interval_head = self.rinex_data[interval_idx]
            label_head = interval_head[60:]
        else:
            # interval_idx = next(i for i, e in enumerate(self.rinex_data) if 'TIME OF FIRST OBS' in e)
            label_head = "INTERVAL"

        # Parse line
        sample_rate_head = "{:10.3f}".format(float(sample_rate_input))

        new_line = sample_rate_head + " " * 50 + label_head

        # Set line
        if line_exists:
            self.rinex_data[interval_idx] = new_line
        else:
            self.rinex_data.insert(interval_idx, new_line)

        return

    def mod_antenna_pos(self, X=None, Y=None, Z=None):
        """
        Modify within the RINEX header the X Y Z RINEX's approximative position.
        (``APPROX POSITION XYZ`` line)

        Parameters
        ----------
        X,Y,Z : float, optional
            X Y Z position. The default is None.

        Returns
        -------
        None.

        """

        if self.status:
            return

        if (X is None) and (Y is None) and (X is None):
            return

        # Identify line that contains APPROX POSITION XYZ
        antenna_pos_header_idx = search_idx_value(
            self.rinex_data, "APPROX POSITION XYZ"
        )
        antenna_pos_head = self.rinex_data[antenna_pos_header_idx]
        # Parse line
        x_head = antenna_pos_head[0:14]
        y_head = antenna_pos_head[14:28]
        z_head = antenna_pos_head[28:42]
        label = antenna_pos_head[60:]
        # Edit line
        if (
            X is not None
        ):  # Format as 14.4 float. Set to zero if too large but should not happen
            x_head = "{:14.4f}".format(float(X))
            if len(x_head) > 14:
                x_head = "{:14.4f}".format(float("0"))
        if Y is not None:
            y_head = "{:14.4f}".format(float(Y))
            if len(y_head) > 14:
                y_head = "{:14.4f}".format(float("0"))
        if Z is not None:
            z_head = "{:14.4f}".format(float(Z))
            if len(z_head) > 14:
                z_head = "{:14.4f}".format(float("0"))
        new_line = x_head + y_head + z_head + " " * 18 + label
        # Set line
        self.rinex_data[antenna_pos_header_idx] = new_line

        return

    def mod_antenna_delta(self, H=None, E=None, N=None):
        """
        Modify within the RINEX header the H E N antenna's excentricity
        (``ANTENNA: DELTA H/E/N`` line).

        Parameters
        ----------
        H, E, N: float, optional
            H E N position. The default is None.

        Returns
        -------
        None.

        """

        if self.status:
            return

        if (H is None) and (E is None) and (N is None):
            return

        # Identify line that contains ANTENNA: DELTA H/E/N
        antenna_delta_header_idx = search_idx_value(
            self.rinex_data, "ANTENNA: DELTA H/E/N"
        )
        antenna_delta_head = self.rinex_data[antenna_delta_header_idx]
        # Parse line
        h_head = antenna_delta_head[0:14]
        e_head = antenna_delta_head[14:28]
        n_head = antenna_delta_head[28:42]
        label = antenna_delta_head[60:]
        # Edit line
        if (
            H is not None
        ):  # Format as 14.4 float. Set to zero if too large but should not happen
            h_head = "{:14.4f}".format(float(H))
            if len(h_head) > 14:
                h_head = "{:14.4f}".format(float("0"))
        if E is not None:
            e_head = "{:14.4f}".format(float(E))
            if len(e_head) > 14:
                e_head = "{:14.4f}".format(float("0"))
        if N is not None:
            n_head = "{:14.4f}".format(float(N))
            if len(n_head) > 14:
                n_head = "{:14.4f}".format(float("0"))
        new_line = h_head + e_head + n_head + " " * 18 + label
        # Set line
        self.rinex_data[antenna_delta_header_idx] = new_line

        return

    def mod_agencies(self, operator=None, agency=None):
        """
        Modify within the RINEX header the ``OBSERVER / AGENCY`` line

        Parameters
        ----------
        operator : str, optional
            Operator. The default is None.
        agency : str, optional
            Agency. The default is None.

        Returns
        -------
        None.

        """

        if self.status:
            return

        if not any([operator, agency]):
            return

        # Identify line that contains OBSERVER / AGENCY
        agencies_header_idx = search_idx_value(self.rinex_data, "OBSERVER / AGENCY")

        if not agencies_header_idx:  ##### THIS TEST SHOULD BE IN ALL MOD METHODS !!!!
            logger.warning(
                "no %s field has been found in %s, unable to mod it",
                "OBSERVER / AGENCY",
                self.filename,
            )
            return

        agencies_head = self.rinex_data[agencies_header_idx]
        # Parse line
        operator_head = agencies_head[0:20]
        agency_head = agencies_head[20:40]
        label_head = agencies_head[60:]
        # Edit line
        if operator:  # Format as 14.4 float. Cut if too large but will not happen
            operator_head = operator[:20].ljust(20)
        if agency:
            agency_head = agency[:40].ljust(40)
        new_line = operator_head + agency_head + label_head
        # Set line
        self.rinex_data[agencies_header_idx] = new_line

        return

    def mod_sat_system(self, sat_system):
        """
        Modify within the RINEX header the *type* of the
        ``RINEX VERSION / TYPE`` line


        Parameters
        ----------
        sat_system :
            Satellite system.

        Returns
        -------
        None.

        """

        if self.status:
            return

        if not sat_system:
            return

        if "+" in sat_system: ### case MIXED system
            sat_system = "MIXED"
            sat_system_code = "M"
        else: ### case single system
            gnss_codes = {
                "GPS": "G",
                "GLO": "R",
                "GAL": "E",
                "BDS": "C",
                "QZSS": "J",
                "IRNSS": "I",
                "SBAS": "S",
                "MIXED": "M",
            }
            sat_system_code = gnss_codes.get(sat_system)

            if not sat_system_code:
                sat_system_code = sat_system
                sat_system = ""

        ### rewrite the RINEX header line

        # Identify line that contains RINEX VERSION / TYPE
        sat_system_header_idx = search_idx_value(
            self.rinex_data, "RINEX VERSION / TYPE"
        )
        sat_system_head = self.rinex_data[sat_system_header_idx]
        # Parse line
        rinex_ver_head = sat_system_head[0:9]
        type_of_rinex_file_head = sat_system_head[20:40]
        # sat_system_head = sat_system_head[40:60]
        label = sat_system_head[60:]

        sat_system_head = sat_system_code[0] + " : " + sat_system[:16].ljust(16)
        new_line = (
            rinex_ver_head
            + " " * 11
            + type_of_rinex_file_head
            + sat_system_head
            + label
        )
        # Set line
        self.rinex_data[sat_system_header_idx] = new_line

        return

    def mod_time_obs(self, first_obs=None, last_obs=None):
        """
        Modify within the RINEX header the ``TIME OF FIRST OBS``
        and ``TIME OF LAST OBS``


        Parameters
        ----------
        first_obs : datetime, optional
            epoch of first observation. The default is None.
        last_obs : datetime, optional
            epoch of last observation. The default is None.

        Returns
        -------
        None

        """

        if self.status:
            return

        if not first_obs:
            first_obs = self.start_date

        if not last_obs:
            last_obs = self.end_date

        # Identify line that contains TIME OF FIRST OBS
        first_obs_idx = search_idx_value(self.rinex_data, "TIME OF FIRST OBS")
        last_obs_idx = search_idx_value(self.rinex_data, "TIME OF LAST OBS")

        first_obs_head = self.rinex_data[first_obs_idx]

        # Parse line
        def _time_line_make(time, sys="GPS"):
            timel = "{:6d}{:6d}{:6d}{:6d}{:6d}{:13.7f}     {:3s}        "

            timelout = timel.format(
                time.year,
                time.month,
                time.day,
                time.hour,
                time.minute,
                time.second + time.microsecond * 10**-6,
                sys,
            )

            return timelout

        sysuse = first_obs_head[48:52]
        line_firstobs = _time_line_make(first_obs, sysuse) + "TIME OF FIRST OBS"
        line_lastobs = _time_line_make(last_obs, sysuse) + "TIME OF LAST OBS"

        self.rinex_data[first_obs_idx] = line_firstobs
        if last_obs_idx:
            self.rinex_data[last_obs_idx] = line_lastobs
        else:
            self.rinex_data.insert(first_obs_idx + 1, line_lastobs)

        return

    def mod_sys_obs_types(self, dict_sys_obs):
        """
        Modify within the RINEX header the systems/observables
        of the ``SYS / # / OBS TYPES`` lines

        for RINEX 3/4 only

        Parameters
        ----------
        dict_sys_obs : dict
            a dictionary of lists describing the observables per system, e.g.:
            ``{"G" : ["C1C","C1W","C2W","L1C","L2W","S1C",S2W"]}``
        """

        if self.status:
            return

        if not any([dict_sys_obs]):
            return

        if self.version_float < 3:
            logger.warn("mod_sys_obs_types is only compatible with RINEX3/4")
            return

        # Identify line that contains SYS / # / OBS TYPES
        sys_obs_idx0 = search_idx_value(self.rinex_data, "SYS / # / OBS TYPES")

        sys_obs_idx_fin = sys_obs_idx0
        while "SYS / # / OBS TYPES" in self.rinex_data[sys_obs_idx_fin]:
            sys_obs_idx_fin += 1

        ### parse the dict
        lfmt_stk = []
        for sys, obs in dict_sys_obs.items():
            ### make slice of 13 elements, i.e. the number of obervable max in
            ### one line
            obs_slice = slice_list(obs, 13)

            for iobss, obss in enumerate(obs_slice):
                nobss = len(obss)
                if iobss == 0:
                    l = "{:1s}  {:3d}" + " {:3s}" * nobss + "    " * (13 - nobss)
                    fmt_tup = tuple([sys, nobss] + obss)
                    lfmt = l.format(*fmt_tup)
                else:
                    l = "      " + " {:3s}" * nobss + "   " * (13 - nobss)
                    lfmt = l.format(*obss)
                lfmt = lfmt + "  SYS / # / OBS TYPES"
                lfmt_stk.append(lfmt)

        self.rinex_data = (
            self.rinex_data[:sys_obs_idx0]
            + lfmt_stk
            + self.rinex_data[sys_obs_idx_fin:]
        )

        return

    def mod_filename_data_freq(self, data_freq_inp=None):
        """
        Modify within the RINEX filename the data freqency
        (``30S``, ``01S``...)
        """

        if not data_freq_inp:
            return

        self.sample_rate_str = data_freq_inp
        return

    def mod_filename_file_period(self, file_period_inp=None):
        """
        Modify within the RINEX filename the period
        (``01D``, ``01H``, ``15M``...)
        """

        if not file_period_inp:
            return

        self.file_period = file_period_inp
        return

    def mod_filename_data_source(self, data_source_inp=None):
        """
        Modify within the RINEX filename the data source
        (``R``, ``S``, ``U``)
        """
        if not data_source_inp:
            return

        self.data_source = data_source_inp
        return

    #############################################################################
    ### misc methods. change the content of the RINEX header

    def get_as_string(self, encode="utf-8"):
        """
        get the RINEX data (header and body) as a string
        """
        return "\n".join(self.rinex_data).encode(encode)

    def write_to_path(self, output_directory, compression="gz", no_hatanaka=True):
        """
        Will turn rinex_data from list to string, utf-8, then compress as hatanaka
        and zip to the 'compression' format, then write to file. The 'compression' param
        will be used as an argument to hatanaka.compress and for naming the output file.
        Available compressions are those of hatanaka compress function :

        Parameters
        ----------
        output_directory : str
            The output directory.

        compression : str, optional
            'gz' (default), 'bz2', 'Z',
            'none' (string, compliant with hatanaka module) or
            None (NoneType, compliant with the rinex object initialisation).
            The default is 'gz'.

        no_hatanaka : bool, optional
            If True, the Hatanaka compression is not performed.
            (Hatanaka compression is applied per default.)
            The default is False.

        Returns
        -------
        outputfile : str
            The output RINEX file path.

        """

        if self.status:
            return

        # make the compression compliant with hatanaka module
        # (accept only 'none' as string)
        if not compression:
            comp_htnk_inp = "none"
        else:
            comp_htnk_inp = compression

        output_data = self.get_as_string()

        if not no_hatanaka:  ## regular case, Hatanaka-compression of the RINEX
            output_data = hatanaka.compress(output_data, compression=comp_htnk_inp)

        ### The data source is an actual RINEX file
        if self.source_from_file:
            if not no_hatanaka:
                # manage hatanaka compression extension
                # RNX3
                if "rnx" in self.filename:
                    filename_out = self.filename.replace("rnx", "crx")
                # RNX2
                elif self.filename[-1] in "o":
                    filename_out = self.filename[:-1] + "d"
                else:
                    filename_out = self.filename
            else:  ### NO Hatanaka-compression of the RINEX, the extension must be changed
                # RNX3
                if "crx" in self.filename:
                    filename_out = self.filename.replace("crx", "rnx")
                # RNX2
                elif self.filename[-1] in "d":
                    filename_out = self.filename[:-1] + "o"
                else:
                    filename_out = self.filename

            # manage low-level compression extension
            if compression in ("none", None):
                outputfile = os.path.join(output_directory, filename_out)
            else:
                outputfile = os.path.join(
                    output_directory, filename_out + "." + compression
                )
        ### the data source is a StringIO
        else:
            outputfile = output_directory

        Path(outputfile).write_bytes(output_data)

        self.path_output = outputfile

        return outputfile

    def add_comment(self, comment=None, add_as_first=False):
        """
        Add a comment line to the end of the RINEX header.

        Parameters
        ----------
        comment : str, optional
            The comment to be added. If None, the function returns immediately.
        add_as_first : bool, optional
            If True, the comment is added as the first comment. Default is False.

        Returns
        -------
        None

        Notes
        -----
        If no comments are in the header, they will be added just before the 'END OF HEADER'.
        Nevertheless, the sort_header() method executed a bit after will bring them
        just after PGM '/ RUN BY / DATE'
        """
        if self.status:
            return

        if not comment:
            return

        end_of_header_idx = search_idx_value(self.rinex_data, "END OF HEADER") + 1
        idx = [
            i
            for i, e in enumerate(self.rinex_data[0:end_of_header_idx])
            if "COMMENT" in e
        ]

        if (
            len(comment) < 60
        ):  # if the comment is shorter than 60 characters, we center it with dashes
            new_line = " {} ".format(comment).center(59, "-")[:59] + " COMMENT"
        else:  # if the comment is longer than 60 characters, we print it as it is (truncated to 60 characters)
            new_line = comment[:59] + " COMMENT"

        # regular case: some comments already exist
        if len(idx) > 0:
            # add the comment as last (default)
            if not add_as_first:
                last_comment_idx = max(idx)
                new_comment_idx = last_comment_idx + 1
            # add the comment as first
            else:
                first_comment_idx = min(idx)
                new_comment_idx = first_comment_idx
        # no comment in the header, then the first comment is added before the 'END OF HEADER'
        else:
            new_comment_idx = end_of_header_idx - 1

        self.rinex_data.insert(new_comment_idx, new_line)

        return

    def add_prg_run_date_comment(self, program, run_by):
        """
        Add a COMMENT, looking like as a 'PGM / RUN BY / DATE'-like line
        Useful to describe autorino edition, but without erasing the conversion
        program information
        """
        if self.status:
            return

        date = datetime.utcnow().strftime("%Y%m%d %H%M%S UTC")
        new_line = "{:20}{:20}{:20}{:}".format(program, run_by, date, "COMMENT")

        self.add_comment(new_line, add_as_first=True)

    def add_comments(self, comment_list):
        """
        Add several comments at the same time.
        The input is then a list of comments (strings)
        Useful for the full history changes for instance

        """
        for com in comment_list:
            self.add_comment(com)
        return

    def clean_history(self):
        """
        Remove the Full History Comments
        """

        i_start, i_end = None, None

        for il, l in enumerate(self.rinex_data):
            if "FULL HISTORY" in l:
                i_start = il
            if "Removed" in l:
                i_end = il
            if "END OF HEADER" in l:
                break

        if i_start and i_end:
            self.rinex_data = (
                self.rinex_data[0 : i_start - 1] + self.rinex_data[i_end + 1 :]
            )
        return

    def clean_rinexmod_comments(self, clean_history=True):
        """
        Remove all RinexMod Comments
        """
        if clean_history:
            self.clean_history()

        rinex_data_new = []
        for l in self.rinex_data:
            if not "rinexmod" in l.lower():
                rinex_data_new.append(l)
        self.rinex_data = rinex_data_new
        return

    def clean_translation_comments(
        self, internal_use_only=True, format_conversion=False
    ):
        """
        clean warning blocks generated during RINEX 2>3 translation

        Parameters
        ----------
        internal_use_only : bool, optional
            clean ``"WARNING - FOR INTERNAL USE ONLY"`` block.
            The default is True.
        format_conversion : bool, optional
            clean ``WARNING - FORMAT CONVERSION`` block.
            The default is False.

        Returns
        -------
        None.

        """

        def __translat_cleaner(rinex_data_in, block_title):
            i_start, i_end = None, None
            inblock = False
            for il, l in enumerate(rinex_data_in):
                if block_title in l:
                    i_start = il - 1  ## -1 for the 1st "*********" line
                    inblock = True
                if inblock and "*" * 50 in l:
                    i_end = il
                    inblock = False
                    break
                if "END OF HEADER" in l:
                    break

            if i_start and i_end:
                rinex_data_out = (
                    rinex_data_in[0 : i_start - 1] + rinex_data_in[i_end + 1 :]
                )
            else:
                logger.warn("no block %s found in header", block_title)
                rinex_data_out = rinex_data_in

            return rinex_data_out

        if internal_use_only:
            self.rinex_data = __translat_cleaner(
                self.rinex_data, "WARNING - FOR INTERNAL USE ONLY"
            )
        if format_conversion:
            self.rinex_data = __translat_cleaner(
                self.rinex_data, "WARNING - FORMAT CONVERSION"
            )

        return

    def sort_header(self):
        header_order = [
            "RINEX VERSION / TYPE",
            "PGM / RUN BY / DATE",
            "COMMENT",
            "MARKER NAME",
            "MARKER NUMBER",
            "MARKER TYPE",
            "OBSERVER / AGENCY",
            "REC # / TYPE / VERS",
            "ANT # / TYPE",
            "APPROX POSITION XYZ",
            "ANTENNA: DELTA H/E/N",
            "ANTENNA: DELTA X/Y/Z",
            "ANTENNA: PHASECENTER",
            "ANTENNA: B.SIGHT XYZ",
            "ANTENNA: ZERODIR AZI",
            "ANTENNA: ZERODIR XYZ",
            "CENTER OF MASS: XYZ",
            "DOI",
            "LICENSE OF USE",
            "STATION INFORMATION",
            "SYS / # / OBS TYPES",
            "SIGNAL STRENGTH UNIT",
            "INTERVAL",
            "TIME OF FIRST OBS",
            "TIME OF LAST OBS",
            "RCV CLOCK OFFS APPL",
            "SYS / DCBS APPLIED",
            "SYS / PCVS APPLIED",
            "SYS / SCALE FACTOR",
            "SYS / PHASE SHIFT",
            "GLONASS SLOT / FRQ #",
            "GLONASS COD/PHS/BIS",
            "LEAP SECONDS",
            "# OF SATELLITES",
            "PRN / # OF OBS",
            "END OF HEADER",
        ]

        head, body, i_end_head = self.get_header_body(True)
        try:
            head_sort = sorted(head, key=lambda x: header_order.index(x[60:].strip()))
            self.rinex_data = head_sort + body
        except:
            logger.warning("unable to sort header's lines, action skipped (RNXv3 only)")
        return


# *****************************************************************************
# low level functions (outside RinexFile class)
def search_idx_value(data, field):
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
