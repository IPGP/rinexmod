#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Class
2022-02-01 Félix Léger - felixleger@gmail.com & sakic@ipgp.fr
"""

import os
import re
import hatanaka
from io import StringIO
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import matplotlib.pyplot as plt


# Create a logger object.
import logging
logger = logging.getLogger(__name__)

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
    The get_metadata method permits to have a printable string of all file's metadata.
    """

    def __init__(self, rinex_input, force_rnx_load=False):
        
        ##### the RINEX input is a file, thus a string or a Path is given
        if type(rinex_input) in (str,Path):      
            self.source_from_file = True
            self.path = rinex_input.strip()
            self.path_output =  "" 
            self.content_input = self.path
        ##### the RINEX input is directely data, in a StringIO
        elif type(rinex_input) is StringIO:
            self.source_from_file = False
            self.path = ""
            self.path_output = ""
            self.content_input = bytes(rinex_input.read(),'utf-8') ## ready-to-read for hatanaka
        else:
            logger.error("input rinex_input is not str, Path, or StringIO")

        self.rinex_data, self.status = self._load_rinex_data(force_rnx_load=force_rnx_load)
        self.size = self.get_size()
        self.name_conv = self.get_naming_convention()
        self.compression, self.hatanka_input = self.get_compression()
        self.filename = self.get_filename()
        
        #### site is an internal attribute, always 9char 
        # (filled with 00XXX in nothing else is provided)
        # it is accessible wit get_site()
        self._site = self.get_site_from_filename(False,False)
        
        self.version = self.get_version()
        self.start_date, self.end_date = self.get_dates()
        self.sample_rate_string, self.sample_rate_numeric = self.get_sample_rate(plot=False)
        #self.file_period, self.session = self.get_file_period_from_filename()
        self.file_period, self.session = self.get_file_period_from_data()
        self.sat_system = self.get_sat_system()

    def __str__(self):
        """
        Defnies a print method for the rinex file object. Will print all the
        header, plus 20 lines of data, plus the number of not printed lines.
        """
        if self.rinex_data == None:
            return ''

        # We get header
        end_of_header_idx = search_idx_value(
            self.rinex_data, 'END OF HEADER') + 1
        str_RinexFile = self.rinex_data[0:end_of_header_idx]
        # We add 20 lines of data
        str_RinexFile.extend(
            self.rinex_data[end_of_header_idx:end_of_header_idx + 20])
        # We add a line that contains the number of lines not to be printed
        lengh = len(self.rinex_data) - len(str_RinexFile) - 20
        cutted_lines_rep = ' ' * 20 + \
            '[' + \
            '{} lines hidden'.format(lengh).center(40, '.') + ']' + ' ' * 20
        str_RinexFile.append(cutted_lines_rep)

        return '\n'.join(str_RinexFile)
    
# *****************************************************************************
#### Main methods

    def get_metadata(self):
        """
        Returns a printable, with carriage-return, string of metadata lines from
        the header, and a python dict of the same information.
        """

        #if self.status not in [0, 2]:
        #    return None

        if self.status:
            return None

        metadata = {}

        metadata_lines = [
            'RINEX VERSION / TYPE',
            'MARKER NAME',
            'MARKER NUMBER',
            'OBSERVER / AGENCY',
            'REC # / TYPE / VERS',
            'ANT # / TYPE',
            'APPROX POSITION XYZ',
            'ANTENNA: DELTA H/E/N',
            'TIME OF FIRST OBS'
        ]

        for kw in metadata_lines:
            for line in self.rinex_data:
                if kw in line:
                    metadata[kw] = line
                    break

        if not'MARKER NUMBER' in metadata:
            metadata['MARKER NUMBER'] = ''

        metadata_parsed = {
            'File': self.path,
            'File size (bytes)': self.size,
            'Rinex version': metadata['RINEX VERSION / TYPE'][0:9].strip(),
            'Sample rate': self.sample_rate_string,
            'File period': self.file_period,
            'Observable type': metadata['RINEX VERSION / TYPE'][40:60].strip(),
            'Marker name': metadata['MARKER NAME'][0:60].strip(),
            'Marker number': metadata['MARKER NUMBER'][0:60].strip(),
            'Operator': metadata['OBSERVER / AGENCY'][0:20].strip(),
            'Agency': metadata['OBSERVER / AGENCY'][20:40].strip(),
            'Receiver serial': metadata['REC # / TYPE / VERS'][0:20].strip(),
            'Receiver type': metadata['REC # / TYPE / VERS'][20:40].strip(),
            'Receiver firmware version': metadata['REC # / TYPE / VERS'][40:60].strip(),
            'Antenna serial': metadata['ANT # / TYPE'][0:20].strip(),
            'Antenna type': metadata['ANT # / TYPE'][20:40].strip(),
            'Antenna position (XYZ)': '{:14} {:14} {:14}'.format(metadata['APPROX POSITION XYZ'][0:14].strip(),
                                                                 metadata['APPROX POSITION XYZ'][14:28].strip(
            ),
                metadata['APPROX POSITION XYZ'][28:42].strip()),
            'Antenna delta (H/E/N)':  '{:14} {:14} {:14}'.format(metadata['ANTENNA: DELTA H/E/N'][0:14].strip(),
                                                                 metadata['ANTENNA: DELTA H/E/N'][14:28].strip(
            ),
                metadata['ANTENNA: DELTA H/E/N'][28:42].strip())
        }

        metadata_parsed['Start date and time'] = self.start_date
        metadata_parsed['Final date and time'] = self.end_date

        metadata_string = '\n'.join(['{:29} : {}'.format(
            key, value) for key, value in metadata_parsed.items()])

        metadata_string = '\n' + metadata_string + '\n'

        return metadata_string, metadata_parsed

    
    def get_site(self,
                 lower_case=True, 
                 only_4char=False,
                 no_country_then_4char=False):
        """
        get the site of the Rinex Object
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
        
        if len(site_4or9char) not in (4,9):
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

        
    
    def get_longname(self, 
                     data_source="R",
                     obs_type='O',
                     ext='auto',
                     compression='auto',
                     inplace_set=False):
        """
        generate the long RINEX filename
        can be stored directly as filename attribute with inplace = True

        ext :
            'auto' (based on the RinexFile attribute) or manual : 'rnx' or 'crx'
            is given without dot as 1st character

        compression :
            'auto' (based on the RinexFile attribute) or manual : 'Z', 'gz', etc...
            is given without dot as 1st character
        """

        if ext == "auto" and self.hatanka_input:
            ext = 'crx'
        elif ext == "auto" and not self.hatanka_input:
            ext = 'rnx'
        else:
            ext = 'rnx'

        ext = '.' + ext

        if compression == 'auto' and self.compression:
            compression = '.' + self.compression
        elif compression == 'auto' and not self.compression:
            compression = ''
        elif compression != "":  # when a manual compression arg is given, and is not void
            compression = '.' + compression
        else:
            compression = ''

        if self.file_period == '01D': ## Daily case
            if self.session:
                timeformat = '%Y%j%H%M'
            else:
                timeformat = '%Y%j0000'  # Start of the day
        elif self.file_period == '00U': ## Unknown case: the filename deserves a full description to identify potential bug 
            timeformat = '%Y%j%H%M'
        else: ## Hourly case
            timeformat = '%Y%j%H00'  # Start of the hour

        
        longname = '_'.join((self.get_site(False,False),
                             data_source,
                             self.start_date.strftime(timeformat),
                             self.file_period,
                             self.sample_rate_string,
                             self.sat_system + obs_type + ext + compression))

        if inplace_set:
            self.filename = longname
            self.name_conv = "LONG"

        return longname

    def get_shortname(self,
                      file_type='auto',
                      compression='auto',
                      inplace_set=False):
        """
        generate the short RINEX filename
        can be stored directly as filename attribute with inplace = True

        file_type :
            'auto' (based on the RinexFile attribute) or manual : 'o', 'd' etc...

        compression :
            'auto' (based on the RinexFile attribute) or manual : 'Z', 'gz', etc...
            is given without dot as 1st character
        """

        if file_type == 'auto' and self.hatanka_input:
            file_type = 'd'
        elif file_type == 'auto' and not self.hatanka_input:
            file_type = 'o'

        if compression == 'auto':
            compression = self.compression

        if compression != "":
            compression = '.' + compression

        if self.file_period == '01D':
            timeformat = '%j0.%y' + file_type + compression
        else:
            Alphabet = list(map(chr, range(97, 123)))
            timeformat = '%j' + \
                Alphabet[self.start_date.hour] + \
                '.%y' + file_type + compression

        shortname = self.get_site(True,True) + self.start_date.strftime(timeformat)

        if inplace_set:
            self.filename = shortname
            self.name_conv = "SHORT"

        return shortname
    
    def get_header_body(self,return_index_end=False):
        """
        get the RINEX's header and body as a list of lines, 
        and the index of the END OF HEADER line if asked
        """
        i_end = None
        i_end = search_idx_value(self.rinex_data, 'END OF HEADER')

        head = self.rinex_data[:i_end+1]
        body = self.rinex_data[i_end+1:]
        
        if return_index_end:
            return head, body, i_end
        else:
            return head, body

    
# *****************************************************************************
### internal methods

    def _load_rinex_data(self,force_rnx_load=False):
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
                rinex_data = hatanaka.decompress(self.content_input).decode('utf-8')
                rinex_data = rinex_data.split('\n')
                status = None
    
            except ValueError:
                rinex_data = None
                status = '03 - Invalid or empty compressed file'
    
            except hatanaka.hatanaka.HatanakaException:
                rinex_data = None
                status = '04 - Invalid Compressed RINEX file'       
            
            bool_l1_obs = "OBSERVATION DATA" in rinex_data[0]
            bool_l1_crx = "COMPACT RINEX FORMAT" in rinex_data[0]
            
            if not force_rnx_load and not (bool_l1_obs or bool_l1_crx) :
                logger.warning("File's 1st line does not match an Observation RINEX: " + 
                               os.path.join(self.path))
                logger.warning("try to force the loading with force_rnx_load = True")
                rinex_data = None
                status = '02 - Not an observation RINEX file'
            
        if status:
            logger.warning(status)
    
        return rinex_data, status
    

    def get_naming_convention(self):
        # Daily or hourly, hatanaka or not, gz or Z compressed file
        pattern_shortname = re.compile(
            '....[0-9]{3}(\d|\D)\.[0-9]{2}(o|d)(|\.(Z|gz))')
        pattern_longname = re.compile(
            '.{4}[0-9]{2}.{3}_(R|S|U)_[0-9]{11}_([0-9]{2}\w)_[0-9]{2}\w_\w{2}\.\w{3}(\.gz|)')
        # GFZ's DataCenter internal naming convention (here it is equivalent to a longname)
        pattern_longname_gfz = re.compile(
            '.{4}[0-9]{2}.{3}_[0-9]{8}_.{3}_.{3}_.{2}_[0-9]{8}_[0-9]{6}_[0-9]{2}\w_[0-9]{2}\w_[A-Z]*\.\w{3}(\.gz)?')

        if pattern_shortname.match(os.path.basename(self.path)):
            name_conv = 'SHORT'
        elif pattern_longname.match(os.path.basename(self.path)):
            name_conv = 'LONG'
        elif pattern_longname_gfz.match(os.path.basename(self.path)):
            name_conv = 'LONGGFZ'
        else:  
            name_conv = 'UNKNOWN'
            
        return name_conv
    

    def get_size(self):
        """ Get RINEX file size """

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
        if basename.lower().endswith('z'):
            compress = os.path.splitext(basename)[1][1:]
        else:
            compress = None

        # find hatanaka value
        if self.name_conv == "SHORT":

            if compress:
                type_letter = basename.split('.')[-2][-1]
            else:
                type_letter = basename[-1]

            if type_letter == "d":
                hatanaka = True
            else:
                hatanaka = False

        else:  # LONG name
            if compress:
                type_ext = basename.split('.')[-2][-3:]
            else:
                type_ext = basename[-3:]

            if type_ext == "crx":
                hatanaka = True
            else:
                hatanaka = False

        return compress, hatanaka

    def get_filename(self):
        """ Get filename WITHOUT its compression extension """

        if self.status:
            return None

        if not self.compression:
            filename = os.path.basename(self.path)
        else:
            basename = os.path.splitext(os.path.basename(self.path))
            filename = basename[0]

        return filename

    def get_version(self):
        """ Get RINEX version """

        if self.status:
            return ''

        version_header_idx = search_idx_value(
            self.rinex_data, 'RINEX VERSION / TYPE')
        version_header = self.rinex_data[version_header_idx]
        # Parse line
        rinex_ver_meta = version_header[0:9].strip()

        return rinex_ver_meta        
        
    
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
        if self.version[0] >= '3':
            # Pattern of an observation line containing a date - RINEX 3
            #date_pattern = re.compile('> (\d{4}) (\d{2}) (\d{2}) (\d{2}) (\d{2}) ((?: |\d)\d.\d{4})')
            date_pattern = re.compile(
                '> (\d{4}) (\d{2}| \d) (\d{2}| \d) (\d{2}| \d) (\d{2}| \d) ((?: |\d)\d.\d{4})')
            year_prefix = ""  # Prefix of year for date formatting

        elif self.version[0] == '2':
            # Pattern of an observation line containing a date - RINEX 2
            date_pattern = re.compile(
                ' (\d{2}) ((?: |\d)\d{1}) ((?: |\d)\d{1}) ((?: |\d)\d{1}) ((?: |\d)\d{1}) ((?: |\d)\d{1}.\d{4})')
            year_prefix = "20"  # Prefix of year for date formatting
            ### !!!!!!!!! before 2000 must be implemented !!!!!!
        
        return date_pattern, year_prefix
    
    
    def get_dates(self):
        """ 
        Getting start and end date from rinex file.
        we search for the date of the first and last observation directly in
        the data.
        if you want the values in the header, use get_dates_in_header
        """

        if self.status:
            return None, None

        def _find_first_last_epoch_line(rnxobj, last_epoch = False):
            
            date_pattern , year_pattern = rnxobj._get_date_patterns()
            
            if last_epoch:
                datause = reversed(rnxobj.rinex_data)
            else:
                datause = rnxobj.rinex_data
            
            # Searching the last one of the file
            for line in datause:
                m = re.search(date_pattern, line)
                if m:
                    break
            if m:  
                year = year_pattern + m.group(1)
                    
                # Building a date string
                epoc = year + ' ' + m.group(2) + ' ' + m.group(3) + ' ' + \
                    m.group(4) + ' ' + m.group(5) + ' ' + m.group(6)
    
                epoc = datetime.strptime(epoc, '%Y %m %d %H %M %S.%f')
            else:
                epoc = None
                        
            return epoc
        
        start_epoch = _find_first_last_epoch_line(self)
        end_epoch   = _find_first_last_epoch_line(self,last_epoch = True)

        return start_epoch, end_epoch
    
    
    def get_dates_in_header(self):
        """ 
        Getting start and end date from rinex file.
        Start date cames from TIME OF FIRST OBS file's header.
        In RINEX3, there's a TIME OF LAST OBS in the heder but it's not available
        in RINEX2, so we search for the date of the last observation directly in
        the data.
        """

        if self.status != 0:
            return None, None

        def _find_meta_label(meta_label_in):
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
                date_out = datetime.strptime(' '.join(date_out[0:6]),
                                             '%Y %m %d %H %M %S.%f0')
            return date_out
                        
        start_meta = _find_meta_label('TIME OF FIRST OBS')
        end_meta = _find_meta_label('TIME OF LAST OBS')

        return start_meta, end_meta
            
    def get_dates_all(self):
        """
        Returns all the epochs in the RINEX
        """
        if self.status:
            return None, None

        Samples_stack = []
        
        date_pattern, _ = self._get_date_patterns()

        for line in self.rinex_data:  # We get all the epochs dates
            if re.search(date_pattern, line):
                Samples_stack.append(re.search(date_pattern, line))
                
        return Samples_stack


    def get_sample_rate(self, plot=False):
        """
        Getting sample rate from rinex file.
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
        
        Samples_stack = self.get_dates_all()
        date_pattern, year_prefix = self._get_date_patterns()


        # If less than 2 samples, can't get a sample rate
        if len(Samples_stack) < 2:
            self.status = '05 - Less than two epochs in the file'
            logger.error("get_sample_rate: less than 2 samples found, can't get a sample rate %s", Samples_stack)
            return None, None

        # Building a date string
        def _date_conv(sample):
            date = year_prefix + sample.group(1) + ' ' + sample.group(2) + ' ' + sample.group(3) + ' ' + \
                sample.group(4) + ' ' + sample.group(5) + ' ' + sample.group(6)

            date = datetime.strptime(date, '%Y %m %d %H %M %S.%f')
            return date

        # Format dates to datetime
        Samples_stack = [_date_conv(d) for d in Samples_stack]
        Samples_rate_diff = np.diff(Samples_stack)  # Getting intervals
        # Converting timedelta to seconds and removing 0 values (potential doubles in epochs)
        Samples_rate_diff = [diff.total_seconds(
        ) for diff in Samples_rate_diff if diff != timedelta(seconds=0)]

        # If less than one interval after removing 0 values, can't get a sample rate
        if len(Samples_rate_diff) < 1:
            self.status = '05 - Less than two epochs in the file'
            logger.error(" get_sample_rate: less than one interval after removing 0 values %s", Samples_rate_diff)
            return None, None

        # If less than 2 intervals, can't compare intervals
        if len(Samples_rate_diff) < 2:
            return '00U', 0.

        # Most frequent
        sample_rate_num = max(set(Samples_rate_diff),
                              key=Samples_rate_diff.count)

        # Counting the intervals that are not equal to the most frequent
        num_bad_sp = len(
            [diff for diff in Samples_rate_diff if diff != sample_rate_num])

        non_nominal_interval_percent = num_bad_sp / len(Samples_rate_diff)

        if plot:
            print('{:29} : {}'.format('Sample intervals not nominals',
                  str(non_nominal_interval_percent * 100) + ' %'))
            plt.plot(Samples_rate_diff)
            plt.show()

        if non_nominal_interval_percent > 0.1:  # Don't set sample rate to files
            # That have more that 10% of non
            # nominal sample rate
            return '00U', 0.

        # Format of sample rate from RINEX3 specs : RINEX Long Filenames
        # We round samples rates to avoid leap-seconds related problems
        if sample_rate_num <= 0.0001:
            # XXU – Unspecified
            sample_rate_str = '00U'
        elif sample_rate_num <= 0.01:
            # XXC – 100 Hertz
            sample_rate_num = round(sample_rate_num, 4)
            sample_rate_str = (
                str(int(1 / (100 * sample_rate_num))) + 'C').rjust(3, '0')
        elif sample_rate_num < 1:
            # XXZ – Hertz
            sample_rate_num = round(sample_rate_num, 2)
            sample_rate_str = (
                str(int(1 / sample_rate_num)) + 'Z').rjust(3, '0')
        elif sample_rate_num < 60:
            # XXS – Seconds
            sample_rate_num = round(sample_rate_num, 0)
            sample_rate_str = (str(int(sample_rate_num)) + 'S').rjust(3, '0')
        ##### NB: a sample rate at the minute level or even above is very unlikely
        elif sample_rate_num < 3600:
            # XXM – Minutes
            sample_rate_num = round(sample_rate_num, 0)
            sample_rate_str = (
                str(int(sample_rate_num / 60)) + 'M').rjust(3, '0')
        elif sample_rate_num < 86400:
            # XXH – Hours
            sample_rate_num = round(sample_rate_num, 0)
            sample_rate_str = (
                str(int(sample_rate_num / 3600)) + 'H').rjust(3, '0')
        elif sample_rate_num <= 8553600:
            # XXD – Days
            sample_rate_num = round(sample_rate_num, 0)
            sample_rate_str = (
                str(int(sample_rate_num / 86400)) + 'D').rjust(3, '0')
        else:
            # XXU – Unspecified
            sample_rate_str = '00U'

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

        if self.name_conv == 'SHORT':
            file_period = self.filename[7:8]
            if file_period.isdigit():
                if file_period != '0':
                    session = True
                # 01D–1 Day
                file_period = '01D'
            elif file_period.isalpha():
                # 01H–1 Hour
                file_period = '01H'
            else:
                # 00U-Unspecified
                file_period = '00U'

        elif self.name_conv == 'LONG':
            file_period = self.filename[24:27]

        elif self.name_conv == 'LONGGFZ':
            file_period = self.filename[46:49]
        else:
            # 00U-Unspecified
            file_period = '00U'

        return file_period, session
    
    
    def get_file_period_from_data(self,allow_several_hours=True):
        """
        Get the file period from the data themselves.
        
        NB: this method respects the IGS convention and thus uses NOMINAL 
        period
        """
        
        rndtup = lambda x,t: round_time(x,timedelta(minutes=t),"up")
        rndtdown = lambda x,t: round_time(x,timedelta(minutes=t),"down")
        rndtaver = lambda x,t: round_time(x,timedelta(minutes=t),"average")
        delta = rndtup(self.end_date,60) - rndtdown(self.start_date,60)

        ### first, the special case : N *full* hours
        if allow_several_hours and delta <= timedelta(seconds=86400 - 3600): ## = 23h max
            # delta2 is a more precise delta (average)
            delta2 = rndtaver(self.end_date,60) - rndtaver(self.start_date,60)
            hours = int(delta2.total_seconds() / 3600 )
            file_period = str(hours).zfill(2) + 'H'
            session = True
        ### more regular cases : 01H, 01D, or Unknown
        elif delta <= timedelta(seconds=3600):
            # NB: this test is useless, it is treated by the previous test
            file_period = '01H'
            session = True
        elif timedelta(seconds=3600) < delta and delta <= timedelta(seconds=86400 + 3600): ##Note1
            file_period = '01D'
            session = False
        else:
            file_period = '00U'
            session = False
        ### Note1: a tolerance of +/- 1 hours is given because old ashtech RINEXs includes the epoch of the next hour/day
        ###        and then the present delta value reach 25
        ###        it justify also the necessity of the delta2 variable
            
        return file_period, session

    def get_sat_system(self):
        """ Parse RINEX VERSION / TYPE line to get observable type """

        if self.status:
            return None

        # Identify line that contains RINEX VERSION / TYPE
        sat_system_header_idx = search_idx_value(
            self.rinex_data, 'RINEX VERSION / TYPE')
        sat_system_meta = self.rinex_data[sat_system_header_idx]
        # Parse line
        sat_system = sat_system_meta[40:41]

        return sat_system

    def get_site_from_filename(self, lower_case=True, only_4char=False):
        """ Getting site name from the filename """
        
        if self.status:
            return None
            
        if self.name_conv in ("LONG","LONGGFZ"):
            site_out = self.filename[:9]
        else:
            site_out = self.filename[:4] + '00' + 'XXX'
            
        if only_4char:
            site_out = site_out[:9]  

        if lower_case:
            return site_out.lower()
        else:
            return site_out.upper()
        
        
    def get_site_from_header(self):
        """ Getting site name from the MARKER NAME line in rinex file's header """

        if self.status:
            return ''

        site_meta = 'MARKER NAME'

        for line in self.rinex_data:
            if re.search(site_meta, line):
                site_meta = line
                break

        if site_meta == 'MARKER NAME':
            return None

        site_meta = site_meta.split(' ')[0].upper()

        return site_meta
    
    def get_sys_obs_types(self):
        """
        get the systems/observables values from the 
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
        
        if self.version[0] < '3':
            logger.warn("get_sys_obs_types is only compatible with RINEX3/4")
            return
        
        # Identify line that contains SYS / # / OBS TYPES
        sys_obs_idx0 = search_idx_value(self.rinex_data,
                                       'SYS / # / OBS TYPES')
        
        sys_obs_idx_fin = sys_obs_idx0
        while 'SYS / # / OBS TYPES' in self.rinex_data[sys_obs_idx_fin]:
            sys_obs_idx_fin += 1
            
        #### get the systems and observations
        Lines_sys = self.rinex_data[sys_obs_idx0:sys_obs_idx_fin]
        print(Lines_sys)
        ## clean SYS / # / OBS TYPES
        Lines_sys = [l[:60] for l in Lines_sys]
        
        ## manage the 2 lines systems => they are stacked in one
        for il,l in enumerate(Lines_sys):
            if l[0] == " ":
                Lines_sys[il-1] = Lines_sys[il-1] + l
                Lines_sys.remove(l)
        
        #### store system and observables in a dictionnary
        dict_sys_obs = dict()
        dict_sys_nobs = dict()
        
        for il,l in enumerate(Lines_sys):
            Sysobs = l.split()
            sys = Sysobs[0]
            dict_sys_obs[sys] = Sysobs[2:]
            dict_sys_nobs[sys] = int(Sysobs[1])
            ## adds the LLI and SSI indicators
            if len(Sysobs[2:]) != int(Sysobs[1]):
                logger.warn("difference between theorectical (%d) and actual (%d) obs nbr for sys (%s)",
                            len(Sysobs[2:]),int(Sysobs[1]),sys)

        return dict_sys_obs, dict_sys_nobs
    
### ***************************************************************************
### mod methods. change the content of the RINEX header

    def mod_marker(self, marker_inp, number_inp=None):

        if self.status:
            return

        if not marker_inp:
            return

        # Identify line that contains MARKER NAME
        marker_name_header_idx = search_idx_value(
            self.rinex_data, 'MARKER NAME')
        # Edit line
        new_line = '{}'.format(marker_inp.ljust(60)) + 'MARKER NAME'
        if marker_name_header_idx:
            #marker_name_meta = self.rinex_data[marker_name_header_idx]
            # Set line
            self.rinex_data[marker_name_header_idx] = new_line
        else:
            pgm_header_idx = search_idx_value(
                self.rinex_data, 'PGM / RUN BY / DATE')
            self.rinex_data.insert(pgm_header_idx, new_line)

        if number_inp:
            # Identify line that contains MARKER NUMBER
            ## marker_number_header_idx = next((i for i, e in enumerate(self.rinex_data) if 'MARKER NUMBER' in e), None)
            marker_number_header_idx = search_idx_value(
                self.rinex_data, 'MARKER NUMBER')
            # Edit line
            new_line = '{}'.format(number_inp.ljust(60)) + 'MARKER NUMBER'
            if marker_number_header_idx:  # The line exsits
                # Set line
                self.rinex_data[marker_number_header_idx] = new_line
            else:  # The line does not exsits
                # Set line
                self.rinex_data.insert(marker_name_header_idx+1, new_line)

        return

    def mod_receiver(self, serial=None, type=None, firmware=None):

        if self.status:
            return

        if not any([serial, type, firmware]):
            return

        # Identify line that contains REC # / TYPE / VERS
        receiver_header_idx = search_idx_value(
            self.rinex_data, 'REC # / TYPE / VERS')
        receiver_meta = self.rinex_data[receiver_header_idx]
        # Parse line
        serial_meta = receiver_meta[0:20]
        type_meta = receiver_meta[20:40]
        firmware_meta = receiver_meta[40:60]
        label = receiver_meta[60:]
        # Edit line
        if serial:
            serial_meta = serial[:20].ljust(20)
        if type:
            type_meta = type[:20].ljust(20)
        if firmware:
            firmware_meta = firmware[:20].ljust(20)
        new_line = serial_meta + type_meta + firmware_meta + label
        # Set line
        self.rinex_data[receiver_header_idx] = new_line

        return

    def mod_antenna(self, serial=None, type=None):

        if self.status:
            return

        if not any([serial, type]):
            return

        # Identify line that contains ANT # / TYPE
        antenna_header_idx = search_idx_value(self.rinex_data, 'ANT # / TYPE')
        antenna_meta = self.rinex_data[antenna_header_idx]
        # Parse line
        serial_meta = antenna_meta[0:20]
        type_meta = antenna_meta[20:40]
        label = antenna_meta[60:]
        # Edit line
        if serial:
            serial_meta = serial[:20].ljust(20)
        if type:
            type_meta = type[:20].ljust(20)
        new_line = serial_meta + type_meta + ' ' * 20 + label
        # Set line
        self.rinex_data[antenna_header_idx] = new_line

        return

    def mod_interval(self, sample_rate_input=None):

        if self.status:
            return

        if not any([sample_rate_input]):
            return

        # Identify line that contains INTERVAL
        line_exists = False
        idx = -1
        for e in self.rinex_data:
            idx += 1
            if "INTERVAL" in e:
                line_exists = True
                interval_idx = idx
                break
            elif 'TIME OF FIRST OBS' in e:
                interval_idx = idx
            elif "END OF HEADER" in e:
                break
            else:
                continue

        if line_exists:
            #interval_idx = next(i for i, e in enumerate(self.rinex_data) if 'INTERVAL' in e)
            interval_meta = self.rinex_data[interval_idx]
            label = interval_meta[60:]
        else:
            #interval_idx = next(i for i, e in enumerate(self.rinex_data) if 'TIME OF FIRST OBS' in e)
            label = "INTERVAL"

        # Parse line
        sample_rate_meta = "{:10.3f}".format(float(sample_rate_input))

        new_line = sample_rate_meta + ' ' * 50 + label

        # Set line
        if line_exists:
            self.rinex_data[interval_idx] = new_line
        else:
            self.rinex_data.insert(interval_idx, new_line)

        return

    def mod_antenna_pos(self, X=None, Y=None, Z=None):

        if self.status:
            return

        if not any([X, Y, Z]):
            return

        # Identify line that contains APPROX POSITION XYZ
        antenna_pos_header_idx = search_idx_value(
            self.rinex_data, 'APPROX POSITION XYZ')
        antenna_pos_meta = self.rinex_data[antenna_pos_header_idx]
        # Parse line
        X_meta = antenna_pos_meta[0:14]
        Y_meta = antenna_pos_meta[14:28]
        Z_meta = antenna_pos_meta[28:42]
        label = antenna_pos_meta[60:]
        # Edit line
        if X:  # Format as 14.4 float. Set to zero if too large but should not happen
            X_meta = '{:14.4f}'.format(float(X))
            if len(X_meta) > 14:
                X_meta = '{:14.4f}'.format(float('0'))
        if Y:
            Y_meta = '{:14.4f}'.format(float(Y))
            if len(Y_meta) > 14:
                Y_meta = '{:14.4f}'.format(float('0'))
        if Z:
            Z_meta = '{:14.4f}'.format(float(Z))
            if len(Z_meta) > 14:
                Z_meta = '{:14.4f}'.format(float('0'))
        new_line = X_meta + Y_meta + Z_meta + ' ' * 18 + label
        # Set line
        self.rinex_data[antenna_pos_header_idx] = new_line

        return

    def mod_antenna_delta(self, H=None, E=None, N=None):

        if self.status:
            return

        if not any([H, E, N]):
            return

        # Identify line that contains ANTENNA: DELTA H/E/N
        antenna_delta_header_idx = search_idx_value(
            self.rinex_data, 'ANTENNA: DELTA H/E/N')
        antenna_delta_meta = self.rinex_data[antenna_delta_header_idx]
        # Parse line
        H_meta = antenna_delta_meta[0:14]
        E_meta = antenna_delta_meta[14:28]
        N_meta = antenna_delta_meta[28:42]
        label = antenna_delta_meta[60:]
        # Edit line
        if H:  # Format as 14.4 float. Set to zero if too large but should not happen
            H_meta = '{:14.4f}'.format(float(H))
            if len(H_meta) > 14:
                H_meta = '{:14.4f}'.format(float('0'))
        if E:
            E_meta = '{:14.4f}'.format(float(E))
            if len(E_meta) > 14:
                E_meta = '{:14.4f}'.format(float('0'))
        if N:
            N_meta = '{:14.4f}'.format(float(N))
            if len(N_meta) > 14:
                N_meta = '{:14.4f}'.format(float('0'))
        new_line = H_meta + E_meta + N_meta + ' ' * 18 + label
        # Set line
        self.rinex_data[antenna_delta_header_idx] = new_line

        return

    def mod_agencies(self, operator=None, agency=None):

        if self.status:
            return

        if not any([operator, agency]):
            return

        # Identify line that contains OBSERVER / AGENCY
        agencies_header_idx = search_idx_value(
            self.rinex_data, 'OBSERVER / AGENCY')
        agencies_meta = self.rinex_data[agencies_header_idx]
        # Parse line
        operator_meta = agencies_meta[0:20]
        agency_meta = agencies_meta[20:40]
        label = agencies_meta[60:]
        # Edit line
        if operator:  # Format as 14.4 float. Cut if too large but will not happen
            operator_meta = operator[:20].ljust(20)
        if agency:
            agency_meta = agency[:40].ljust(40)
        new_line = operator_meta + agency_meta + label
        # Set line
        self.rinex_data[agencies_header_idx] = new_line

        return

    def mod_sat_system(self, sat_system):

        if self.status:
            return

        if not sat_system:
            return

        # Identify line that contains RINEX VERSION / TYPE
        sat_system_header_idx = search_idx_value(
            self.rinex_data, 'RINEX VERSION / TYPE')
        sat_system_meta = self.rinex_data[sat_system_header_idx]
        # Parse line
        rinex_ver_meta = sat_system_meta[0:9]
        type_of_rinex_file_meta = sat_system_meta[20:40]
        # sat_system_meta = sat_system_meta[40:60]
        label = sat_system_meta[60:]
        # Edit line
        if '+' in sat_system:
            sat_system = 'MIXED'
            sat_system_code = 'M'
        else:
            gnss_codes = {
                'GPS': 'G',
                'GLO': 'R',
                'GAL': 'E',
                'BDS': 'C',
                'QZSS': 'J',
                'IRNSS': 'I',
                'SBAS': 'S',
                'MIXED': 'M'
            }
            sat_system_code = gnss_codes.get(sat_system)

            if not sat_system_code:
                sat_system_code = sat_system
                sat_system = ''

        sat_system_meta = sat_system_code[0] + \
            ' : ' + sat_system[:16].ljust(16)
        new_line = rinex_ver_meta + ' ' * 11 + \
            type_of_rinex_file_meta + sat_system_meta + label
        # Set line
        self.rinex_data[sat_system_header_idx] = new_line

        return
    
    
    def mod_time_obs(self,first_obs=None,last_obs=None):
        
        if self.status:
            return

        if not first_obs:
            first_obs = self.start_date
            
        if not last_obs:
            last_obs = self.end_date
            
            
        # Identify line that contains TIME OF FIRST OBS
        first_obs_idx = search_idx_value(self.rinex_data,
                                         'TIME OF FIRST OBS')
        last_obs_idx = search_idx_value(self.rinex_data,
                                        'TIME OF LAST OBS')

        first_obs_meta = self.rinex_data[first_obs_idx]
        
        # Parse line
        def _time_line_make(time,sys="GPS"):
            timel = "{:6d}{:6d}{:6d}{:6d}{:6d}{:13.7f}     {:3s}        "
            
            timelout = timel.format(time.year,
                                    time.month,
                                    time.day,
                                    time.hour,
                                    time.minute,
                                    time.second + time.microsecond * 10**-6,
                                    sys)
            
            return timelout
            
        sysuse = first_obs_meta[48:52]
        line_firstobs = _time_line_make(first_obs,sysuse) + "TIME OF FIRST OBS"
        line_lastobs = _time_line_make(last_obs,sysuse)   + "TIME OF LAST OBS"
            
        self.rinex_data[first_obs_idx] = line_firstobs
        if last_obs_idx:
            self.rinex_data[last_obs_idx] = line_lastobs
        else:
            self.rinex_data.insert(first_obs_idx+1,line_lastobs)
            
        return
            

    def mod_sys_obs_types(self,dict_sys_obs):
        """
        change the systems/observables from the ``SYS / # / OBS TYPES`` lines
        
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
        
        if self.version[0] < '3':
            logger.warn("mod_sys_obs_types is only compatible with RINEX3/4")
            return

        # Identify line that contains SYS / # / OBS TYPES
        sys_obs_idx0 = search_idx_value(self.rinex_data,
                                       'SYS / # / OBS TYPES')
        
        sys_obs_idx_fin = sys_obs_idx0
        while 'SYS / # / OBS TYPES' in self.rinex_data[sys_obs_idx_fin]:
            sys_obs_idx_fin += 1
            
        ### parse the dict
        lfmt_stk = []
        for sys, obs in dict_sys_obs.items():            
            ### make slice of 13 elements, i.e. the number of obervable max in 
            ### one line 
            obs_slice = slice_list(obs,13)
            
            for iobss,obss in enumerate(obs_slice):
                nobss = len(obss) 
                if iobss == 0:
                    l = "{:1s}  {:3d}" + " {:3s}" * nobss + "    " * (13-nobss)
                    fmt_tup = tuple([sys,nobss] + obss)
                    lfmt = l.format(*fmt_tup)
                else:
                    l = "      " + " {:3s}" * nobss + "   " * (13-nobss)
                    lfmt = l.format(*obss)
                lfmt = lfmt + '  SYS / # / OBS TYPES'
                lfmt_stk.append(lfmt)                    
                
        self.rinex_data = self.rinex_data[:sys_obs_idx0] + \
                          lfmt_stk +  \
                          self.rinex_data[sys_obs_idx_fin:]
                          
        return   



    def mod_filename_data_freq(self, data_freq_inp):
        self.sample_rate_str = data_freq_inp
        return

    def mod_filename_file_period(self, file_period_inp):
        self.file_period = file_period_inp
        return
    
#############################################################################
### misc methods. change the content of the RINEX header

    def get_as_string(self,encode='utf-8'):
        """
        get the RINEX data (header and body) as a string
        """
        return '\n'.join(self.rinex_data).encode(encode)


    def write_to_path(self, output_directory, compression='gz'):
        """
        Will turn rinex_data from list to string, utf-8, then compress as hatanaka
        and zip to the 'compression' format, then write to file. The 'compression' param
        will be used as an argument to hatanaka.compress and for naming the output file.
        Available compressions are those of hatanaka compress function :

        Parameters
        ----------
        output_directory : str
            The output directory.
            
        compression : TYPE, optional
            'gz' (default), 'bz2', 'Z', 
            'none' (string, compliant with hatanaka module) or 
            None (NoneType, compliant with the rinex object initialisation). 
            The default is 'gz'.
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
            comp_htnk_inp = 'none'
        else:
            comp_htnk_inp = compression
            
        output_data = self.get_as_string()

        output_data = hatanaka.compress(output_data, compression=comp_htnk_inp)

        ### The data source is an actual RINEX file
        if self.source_from_file:
            # manage hatanaka compression extension
            # RNX3
            if "rnx" in self.filename:
                filename_out = self.filename.replace("rnx", "crx")
            # RNX2
            elif self.filename[-1] in "o":
                filename_out = self.filename[:-1] + "d"
            else:
                filename_out = self.filename
    
            # manage low-level compression extension
            if compression in ('none', None):
                outputfile = os.path.join(output_directory, filename_out)
            else:
                outputfile = os.path.join(output_directory,
                                          filename_out + '.' + compression)
        ### the data source is a StringIO
        else:
            outputfile = output_directory

        Path(outputfile).write_bytes(output_data)
        
        self.path_output = outputfile
        
        return outputfile


    def add_comment(self, comment, add_pgm_cmt=False):
        '''
        We add the argument comment line at the end of the header
        Append as last per default

        add_pgm_cmt=True add a 'PGM / RUN BY / DATE'-like line 
        Then comment is a 2-tuple (program,run_by)
        '''
        if self.status:
            return

        end_of_header_idx = search_idx_value(
            self.rinex_data, 'END OF HEADER') + 1
        Idx = [i for i, e in enumerate(
            self.rinex_data[0:end_of_header_idx]) if 'COMMENT' in e]

        if not add_pgm_cmt:
            last_comment_idx = max(Idx)
            new_comment_idx = last_comment_idx + 1
            new_line = ' {} '.format(comment).center(59, '-') + ' COMMENT'

        else:
            first_comment_idx = min(Idx)
            new_comment_idx = first_comment_idx
            program, run_by = comment
            date = datetime.utcnow().strftime("%Y%m%d %H%M%S UTC")
            new_line = '{:20}{:20}{:20}{:}'.format(
                program, run_by, date, 'COMMENT')

        self.rinex_data.insert(new_comment_idx, new_line)

        return
    
    def add_comments(self,comment_list):
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
        
        i_start,i_end = None,None
        
        for il,l in enumerate(self.rinex_data):
            if "FULL HISTORY" in l:
                i_start = il
            if "Removed" in l:
                i_end = il
            if "END OF HEADER" in l:
                break
                        
        if i_start and i_end:
            self.rinex_data = self.rinex_data[0:i_start-1] + self.rinex_data[i_end+1:]
        return
            
    def clean_rinexmod_comments(self,clean_history=True):
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
    
    
    def clean_gfzrnx_comments(self,
                              internal_use_only=True,
                              format_conversion=False):
        """
        clean warning blocks generated by GFZRNX's RINEX 2>3 conversion

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
        
        def __gfzrnx_cleaner(self,block_title):
            
            i_start,i_end = None,None            
            for il,l in enumerate(self.rinex_data):
                if block_title in l:
                    i_start = il - 1 ## -1 for the "*********" line
                if "***********************************************************" in l:
                    i_end = il
                if "END OF HEADER" in l:
                    break
                            
            if i_start and i_end:
                self.rinex_data = self.rinex_data[0:i_start-1] + self.rinex_data[i_end+1:]
            return
        
        if internal_use_only:
            self.__gfzrnx_cleaner("WARNING - FOR INTERNAL USE ONLY")
        if format_conversion:
            self.__gfzrnx_cleaner("WARNING - FORMAT CONVERSION")
        
        return 

        
    def sort_header(self):
        header_order = ['RINEX VERSION / TYPE',
        'PGM / RUN BY / DATE',
        'COMMENT',
        'MARKER NAME',
        'MARKER NUMBER',
        'MARKER TYPE',
        'OBSERVER / AGENCY',
        'REC # / TYPE / VERS',
        'ANT # / TYPE',
        'APPROX POSITION XYZ',
        'ANTENNA: DELTA H/E/N',
        'ANTENNA: DELTA X/Y/Z',
        'ANTENNA: PHASECENTER',
        'ANTENNA: B.SIGHT XYZ',
        'ANTENNA: ZERODIR AZI',
        'ANTENNA: ZERODIR XYZ',
        'CENTER OF MASS: XYZ',
        'DOI',
        'LICENSE OF USE',
        'STATION INFORMATION',
        'SYS / # / OBS TYPES',
        'SIGNAL STRENGTH UNIT',
        'INTERVAL',
        'TIME OF FIRST OBS',
        'TIME OF LAST OBS',
        'RCV CLOCK OFFS APPL',
        'SYS / DCBS APPLIED',
        'SYS / PCVS APPLIED',
        'SYS / SCALE FACTOR',
        'SYS / PHASE SHIFT',
        'GLONASS SLOT / FRQ #',
        'GLONASS COD/PHS/BIS',
        'LEAP SECONDS',
        '# OF SATELLITES',
        'PRN / # OF OBS',
        'END OF HEADER']
        
        head, body, i_end_head = self.get_header_body(True)
        try:
            head_sort = sorted(head,key=lambda x: header_order.index(x[60:].strip()))
            self.rinex_data = head_sort + body
        except:
            logger.warning("unable to sort header's lines, action skipped (only possible for RNXv3)")
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

def slice_list(seq,num):
    """ make sublist of num elts of a list """
    # http://stackoverflow.com/questions/4501636/creating-sublists
    return [seq[i:i+num] for i in range(0, len(seq), num)]


def round_time(dt=None, date_delta=timedelta(minutes=60), to='average'):
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
        if to == 'up':
            # // is a floor division, not a comment on following line (like in javascript):
            rounding = (seconds + dt.microsecond/1000000 + round_to) // round_to * round_to
        elif to == 'down':
            rounding = seconds // round_to * round_to
        else:
            rounding = (seconds + round_to / 2) // round_to * round_to

    return dt + timedelta(0, rounding - seconds, - dt.microsecond)