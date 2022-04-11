#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Class
2022-02-01 Félix Léger - felixleger@gmail.com
"""

import os, re
import hatanaka
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import matplotlib.pyplot as plt


def search_idx_value(data, field):
    """
    find the index (line number) of a researched filed in the RINEX data
    """
    idx = -1
    out_idx = None
    for e in data:
        idx += 1
        if field in e:
            out_idx = idx
            break
    return out_idx


class RinexFile:
    """
    Will store a compressed rinex file content in a file-like list of strings
    using the hatanaka library.
    Will then provide methods to modifiy the file's header.
    The method to get the sample rate will read the whole file and will set as
    unknow sample rate files that have more than 10% of non-nominam sample rate.
    The method to get the file duration is based on reading the file name and
    not the data.
    A method to write the file in selected compression is also available.
    The get_metadata method permits to have a printable string of all file's metadata.
    """

    def __init__(self, rinexfile, plot=False):

        self.path = rinexfile
        self.rinex_data, self.name_conv, self.status = self._load_rinex_data()
        self.size = self._get_size()
        self.compression, self.hatanka_input = self._get_compression()
        self.filename = self._filename()
        self.version = self._get_version()
        self.start_date, self.end_date = self._get_dates()
        self.sample_rate, self.sample_rate_numeric  = self._get_sample_rate(plot)
        self.file_period, self.session = self._get_file_period()
        self.sat_system = self._get_sat_system()


    def __str__(self):
        """
        Defnies a print method for the rinex file object. Will print all the
        header, plus 20 lines of data, plus the number of not printed lines.
        """
        if self.rinex_data == None:
            return ''

        # We get header
        end_of_header_idx = search_idx_value(self.rinex_data,'END OF HEADER') + 1
        str_RinexFile = self.rinex_data[0:end_of_header_idx]
        # We add 20 lines of data
        str_RinexFile.extend(self.rinex_data[end_of_header_idx:end_of_header_idx + 20])
        # We add a line that contains the number of lines not to be printed
        lengh = len(self.rinex_data) - len(str_RinexFile) -20
        cutted_lines_rep = ' ' * 20 + '[' + '{} lines hidden'.format(lengh).center(40, '.') + ']' + ' ' * 20
        str_RinexFile.append(cutted_lines_rep)

        return '\n'.join(str_RinexFile)


    def _load_rinex_data(self):
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

        # Checking if existing file
        if not os.path.isfile(self.path):
            return None, None, 1
        # Daily or hourly, gz or Z compressed hatanaka file
        pattern_shortname = re.compile('....[0-9]{3}(\d|\D)\.[0-9]{2}(d\.((Z)|(gz)))')
        pattern_longname = re.compile('.{4}[0-9]{2}.{3}_(R|S|U)_[0-9]{11}_([0-9]{2}\w)_[0-9]{2}\w_\w{2}\.\w{3}(\.gz|)')

        if pattern_shortname.match(os.path.basename(self.path)):
            name_conv = 'SHORT'
            status = 0
        elif pattern_longname.match(os.path.basename(self.path)):
            name_conv = 'LONG'
            status = 0
        else:
            print('rinex filename does not match a regular name: ' + os.path.basename(self.path))
            return None, None, 2

        try:
            rinex_data = hatanaka.decompress(self.path).decode('utf-8')
            rinex_data = rinex_data.split('\n')

        except ValueError:
            return None, None, 3

        except hatanaka.hatanaka.HatanakaException:
            return None, None, 4

        return rinex_data, name_conv, status


    def _get_size(self):

        """ Get RINEX file size """

        if self.status != 0:
            return 0

        size = os.path.getsize(self.path)

        return size


    def _get_compression(self):
        """
        get the compression type (compress,hatanaka)
        compress is a string: gz, Z, 7z
        hatanaka is a bool
        """

        basename = os.path.basename(self.path)

        if basename.lower().endswith('z'):
            compress = os.path.splitext(basename)[1][1:]
        else:
            compress = None

        if self.name_conv == "SHORT":

            if compress:
                type_letter = basename.split('.')[-2][-1]
            else:
                type_letter = basename[-1]

            if type_letter == "d":
                hatanaka = True
            else:
                hatanaka = False

        else: ### LONG name
            if compress:
                type_ext = basename.split('.')[-2][-3:]
            else:
                type_ext = basename[-3:]

            if type_ext == "crx":
                hatanaka = True
            else:
                hatanaka = False

        return compress , hatanaka


    def _filename(self):
        """ Get filename and compression extension """

        if self.status != 0:
            return None

        if not self.compression:
            filename = os.path.basename(self.path)
        else:
            basename = os.path.splitext(os.path.basename(self.path))
            filename = basename[0]

        return filename


    def _get_version(self):

        """ Get RINEX version """

        if self.status != 0:
            return ''

        version_header_idx = search_idx_value(self.rinex_data,'RINEX VERSION / TYPE')
        version_header = self.rinex_data[version_header_idx]
        # Parse line
        rinex_ver_meta = version_header[0:9].strip()

        return rinex_ver_meta


    def _get_dates(self):

        """ Getting start and end date from rinex file.
        Start date cames from TIME OF FIRST OBS file's header.
        In RINEX3, there's a TIME OF LAST OBS in the heder but it's not available
        in RINEX2, so we search for the date of the last observation directly in
        the data.
        """

        if self.status != 0:
            return None, None

        # Getting start date
        start_meta = 'TIME OF FIRST OBS'

        for line in self.rinex_data:
            if re.search(start_meta, line):
                start_meta = line
                break
        # If not found
        if start_meta == 'TIME OF FIRST OBS':
            return None, None

        start_meta = start_meta.split()
        start_meta = datetime.strptime(' '.join(start_meta[0:6]) , '%Y %m %d %H %M %S.%f0')

        # Getting end date
        if self.version[0] == '3':
            # Pattern of an observation line containing a date
            ## date_pattern = re.compile('> (\d{4}) (\d{2}) (\d{2}) (\d{2}) (\d{2}) ((?: |\d)\d.\d{4})')
            date_pattern = re.compile('> (\d{4}) (\d{2}| \d) (\d{2}| \d) (\d{2}| \d) (\d{2}| \d) ((?: |\d)\d.\d{4})')
            # Searching the last one of the file
            for line in reversed(self.rinex_data):
                m = re.search(date_pattern, line)
                if m:
                    break

            year =  m.group(1)

        elif self.version[0] == '2':
            # Pattern of an observation line containing a date
            date_pattern = re.compile(' (\d{2}) ((?: |\d)\d{1}) ((?: |\d)\d{1}) ((?: |\d)\d{1}) ((?: |\d)\d{1}) ((?: |\d)\d{1}.\d{4})')
            # Searching the last one of the file
            for line in reversed(self.rinex_data):
                m = re.search(date_pattern, line)
                if m:
                    break

            year = '20' + m.group(1)

        # Building a date string
        end_meta = year + ' ' + m.group(2) + ' ' + m.group(3) + ' ' + \
                   m.group(4) + ' ' + m.group(5) + ' ' + m.group(6)

        end_meta = datetime.strptime(end_meta, '%Y %m %d %H %M %S.%f')

        return start_meta, end_meta


    def _get_sample_rate(self, plot=False):

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

        if self.status != 0:
            return None,None

        # Removing this test on INTERVAL header line because not reliable (at least in IPGP data set)
        # sr_meta = 'INTERVAL'
        #
        # for line in self.rinex_data:
        #     if re.search(sr_meta, line):
        #         sr_meta = line
        #         break
        # # If not found
        # if sr_meta != 'INTERVAL':
        #
        #     return sr_meta

        # Date lines pattern
        if self.version[0] == '3':
            # Pattern of an observation line containing a date - RINEX 3
            #date_pattern = re.compile('> (\d{4}) (\d{2}) (\d{2}) (\d{2}) (\d{2}) ((?: |\d)\d.\d{4})')
            date_pattern = re.compile('> (\d{4}) (\d{2}| \d) (\d{2}| \d) (\d{2}| \d) (\d{2}| \d) ((?: |\d)\d.\d{4})')
            year_prefix = "" # Prefix of year for date formatting

        elif self.version[0] == '2':
            # Pattern of an observation line containing a date - RINEX 2
            date_pattern = re.compile(' (\d{2}) ((?: |\d)\d{1}) ((?: |\d)\d{1}) ((?: |\d)\d{1}) ((?: |\d)\d{1}) ((?: |\d)\d{1}.\d{4})')
            year_prefix = "20" # Prefix of year for date formatting

        Samples_stack = []

        for line in self.rinex_data: # We get all the epochs dates
            if re.search(date_pattern, line):
                Samples_stack.append(re.search(date_pattern, line))

        # If less than 2 samples, can't get a sample rate
        if len(Samples_stack) < 2:
            self.status = 5
            print("# ERROR: _get_sample_rate: less than 2 samples found, , can't get a sample rate",Samples_stack)
            return None,None

        # Building a date string
        def date_conv(sample):
            date = year_prefix + sample.group(1) + ' ' + sample.group(2) + ' ' + sample.group(3) + ' ' + \
                         sample.group(4) + ' ' + sample.group(5) + ' ' + sample.group(6)

            date = datetime.strptime(date, '%Y %m %d %H %M %S.%f')
            return date

        Samples_stack = [date_conv(d) for d in Samples_stack] # Format dates to datetime
        Samples_rate_diff = np.diff(Samples_stack) # Getting intervals
        # Converting timedelta to seconds and removing 0 values (potential doubles in epochs)
        Samples_rate_diff = [diff.total_seconds() for diff in Samples_rate_diff if diff != timedelta(seconds=0)]

        # If less than one interval after removing 0 values, can't get a sample rate
        if len(Samples_rate_diff) < 1:
            self.status = 5
            print("# ERROR: _get_sample_rate: less than one interval after removing 0 values",Samples_rate_diff)
            return None,None

        # If less than 2 intervals, can't compare intervals
        if len(Samples_rate_diff) < 2:
            return 'XXU',0.

        # Most frequent
        sample_rate = max(set(Samples_rate_diff), key = Samples_rate_diff.count)

        # Counting the intervals that are not equal to the most frequent
        num_bad_sp = len([diff for diff in Samples_rate_diff if diff != sample_rate])

        non_nominal_interval_percent = num_bad_sp / len(Samples_rate_diff)

        if plot:
            print('{:29} : {}'.format('Sample intervals not nominals', str(non_nominal_interval_percent * 100) + ' %'))
            plt.plot(Samples_rate_diff)
            plt.show()

        if non_nominal_interval_percent > 0.1: # Don't set sample rate to files
                                               # That have more that 10% of non
                                               # nominal sample rate
            return 'XXU',0.

        # Format of sample rate from RINEX3 specs : RINEX Long Filenames
        # We round samples rates to avoid leap-seconds related problems
        if sample_rate <= 0.0001:
            # XXU – Unspecified
            sample_rate_str = 'XXU'
        elif sample_rate <= 0.01:
            # XXC – 100 Hertz
            sample_rate = round(sample_rate, 4)
            sample_rate_str = (str(int(1 / (100 * sample_rate))) + 'C').rjust(3, '0')
        elif sample_rate < 1:
            # XXZ – Hertz
            sample_rate = round(sample_rate, 2)
            sample_rate_str = (str(int(1 / sample_rate)) + 'Z').rjust(3, '0')
        elif sample_rate < 60:
            # XXS – Seconds
            sample_rate = round(sample_rate, 0)
            sample_rate_str = (str(int(sample_rate)) + 'S').rjust(3, '0')
        elif sample_rate < 3600:
            # XXM – Minutes
            sample_rate = round(sample_rate, 0)
            sample_rate_str = (str(int(sample_rate / 60)) + 'M').rjust(3, '0')
        elif sample_rate < 86400:
            # XXH – Hours
            sample_rate = round(sample_rate, 0)
            sample_rate_str = (str(int(sample_rate / 3600)) + 'H').rjust(3, '0')
        elif sample_rate <= 8553600:
            # XXD – Days
            sample_rate = round(sample_rate, 0)
            sample_rate_str = (str(int(sample_rate / 86400)) + 'D').rjust(3, '0')
        else:
            # XXU – Unspecified
            sample_rate_str = 'XXU'

        return sample_rate_str, sample_rate


    def _get_file_period(self):
        """
        Get the file period from the file's name.
        In long name convention, gets it striaght from the file name.
        In short name convention, traduces digit to '01H' and '0' to 01D
        """

        if self.status != 0:
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

        else:
            # 00U-Unspecified
            file_period = '00U'

        return file_period, session


    def _get_sat_system(self):
        """ Parse RINEX VERSION / TYPE line to get observable type """

        if self.status != 0:
            return None

        # Identify line that contains RINEX VERSION / TYPE
        sat_system_header_idx = search_idx_value(self.rinex_data,'RINEX VERSION / TYPE')
        sat_system_meta = self.rinex_data[sat_system_header_idx]
        # Parse line
        sat_system = sat_system_meta[40:41]

        return sat_system


    def get_metadata(self):
        """
        Returns a printable, with carriage-return, string of metadata lines from
        the header, and a python dict of the same information.
        """

        if self.status not in [0,2]:
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
                           'File' : self.path,
                           'File size (bytes)' : self.size,
                           'Rinex version' : metadata['RINEX VERSION / TYPE'][0:9].strip(),
                           'Sample rate' : self.sample_rate,
                           'File period' : self.file_period,
                           'Observable type' : metadata['RINEX VERSION / TYPE'][40:60].strip(),
                           'Marker name' : metadata['MARKER NAME'][0:60].strip(),
                           'Marker number' : metadata['MARKER NUMBER'][0:60].strip(),
                           'Operator' : metadata['OBSERVER / AGENCY'][0:20].strip(),
                           'Agency' : metadata['OBSERVER / AGENCY'][20:40].strip(),
                           'Receiver serial' : metadata['REC # / TYPE / VERS'][0:20].strip(),
                           'Receiver type' : metadata['REC # / TYPE / VERS'][20:40].strip(),
                           'Receiver firmware version' : metadata['REC # / TYPE / VERS'][40:60].strip(),
                           'Antenna serial' : metadata['ANT # / TYPE'][0:20].strip(),
                           'Antenna type' : metadata['ANT # / TYPE'][20:40].strip(),
                           'Antenna position (XYZ)' : '{:14} {:14} {:14}'.format(metadata['APPROX POSITION XYZ'][0:14].strip(),
                                                               metadata['APPROX POSITION XYZ'][14:28].strip(),
                                                               metadata['APPROX POSITION XYZ'][28:42].strip()),
                           'Antenna delta (H/E/N)' :  '{:14} {:14} {:14}'.format(metadata['ANTENNA: DELTA H/E/N'][0:14].strip(),
                                                                metadata['ANTENNA: DELTA H/E/N'][14:28].strip(),
                                                                metadata['ANTENNA: DELTA H/E/N'][28:42].strip())
                          }

        metadata_parsed['Start date and time'] = self.start_date
        metadata_parsed['Final date and time'] = self.end_date

        metadata_string = '\n'.join(['{:29} : {}'.format(key, value) for key, value in metadata_parsed.items()])

        metadata_string = '\n' + metadata_string + '\n'

        return metadata_string, metadata_parsed


    def get_site_from_header(self):

        """ Getting site name from the MARKER NAME line in rinex file's header """

        if self.status != 0:
            return ''

        station_meta = 'MARKER NAME'

        for line in self.rinex_data:
            if re.search(station_meta, line):
                station_meta = line
                break

        if station_meta == 'MARKER NAME':
            return None

        station_meta = station_meta.split(' ')[0].upper()

        return station_meta


    def get_site_from_filename(self,case='lower',only_4char=False):

        """ Getting site name from the filename """

        if only_4char:
            cut = 4
        else:
            cut = None

        if case == 'lower':
            return self.filename[:cut].lower()
        elif case == 'upper':
            return self.filename[:cut].upper()


    def get_longname(self, monum_country="00XXX", data_source="R", obs_type='O', ext='auto', compression='auto', inplace=False):

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

        site_9char = self.get_site_from_filename('upper',True) + monum_country

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
        else: ## when a manual compression arg is given
            compression = '.' + compression

        if self.file_period == '01D':
            if self.session:
                timeformat = '%Y%j%H%M'
            else:
                timeformat = '%Y%j0000' # Start of the day
        else:
            timeformat = '%Y%j%H00' # Start of the hour

        longname = '_'.join((site_9char.upper(),
                             data_source,
                             self.start_date.strftime(timeformat),
                             self.file_period,
                             self.sample_rate,
                             self.sat_system + obs_type + ext + compression))

        if inplace:
            self.filename = longname

        return longname


    def get_shortname(self, file_type='auto', compression='auto', inplace=False):
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
        elif  file_type == 'auto' and not self.hatanka_input:
            file_type = 'o'

        if compression == 'auto':
            compression = self.compression

        site_4char = self.get_site_from_filename('lower',True)

        compression = '.' + compression

        print(self.file_period)

        if self.file_period == '01D':
            timeformat = '%j0.%y' + file_type + compression
        else:
            Alphabet = list(map(chr, range(97, 123)))
            timeformat = '%j' + Alphabet[self.start_date.hour] + '.%y' + file_type + compression

        shortname = site_4char + self.start_date.strftime(timeformat)

        if inplace:
            self.filename = shortname

        return shortname


    def set_marker(self, station):

        if self.status != 0:
            return

        if not station:
            return

        # Identify line that contains MARKER NAME
        marker_name_header_idx = search_idx_value(self.rinex_data, 'MARKER NAME')
        marker_name_meta = self.rinex_data[marker_name_header_idx]
        # Edit line
        new_line = '{}'.format(station.ljust(60)) + 'MARKER NAME'
        # Set line
        self.rinex_data[marker_name_header_idx] = new_line

        # Identify line that contains MARKER NUMBER
        marker_number_header_idx = next((i for i, e in enumerate(self.rinex_data) if 'MARKER NUMBER' in e), None)
        if marker_number_header_idx:
            new_line = '{}'.format(station.ljust(60)) + 'MARKER NUMBER'
            # Set line
            self.rinex_data[marker_number_header_idx] = new_line

        return


    def set_receiver(self, serial=None, type=None, firmware=None):

        if self.status != 0:
            return

        if not any([serial, type, firmware]):
            return

        # Identify line that contains REC # / TYPE / VERS
        receiver_header_idx = search_idx_value(self.rinex_data, 'REC # / TYPE / VERS')
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


    def set_antenna(self, serial=None, type=None):

        if self.status != 0:
            return

        if not any([serial, type]):
            return

        # Identify line that contains ANT # / TYPE
        antenna_header_idx = search_idx_value(self.rinex_data, 'ANT # / TYPE' )
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


    def set_interval(self, sample_rate=None):

        if self.status != 0:
            return

        if not any([sample_rate]):
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
        sample_rate_meta = "{:10.3f}".format(float(sample_rate))

        new_line = sample_rate_meta + ' ' * 50 + label

        # Set line
        if line_exists:
            self.rinex_data[interval_idx] = new_line
        else:
            self.rinex_data.insert(interval_idx,new_line)

        return


    def set_antenna_pos(self, X=None, Y=None, Z=None):

        if self.status != 0:
            return

        if not any([X, Y, Z]):
            return

        # Identify line that contains APPROX POSITION XYZ
        antenna_pos_header_idx = search_idx_value(self.rinex_data, 'APPROX POSITION XYZ' )
        antenna_pos_meta = self.rinex_data[antenna_pos_header_idx]
        # Parse line
        X_meta = antenna_pos_meta[0:14]
        Y_meta = antenna_pos_meta[14:28]
        Z_meta = antenna_pos_meta[28:42]
        label = antenna_pos_meta[60:]
        # Edit line
        if X: # Format as 14.4 float. Set to zero if too large but should not happen
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


    def set_antenna_delta(self, X=None, Y=None, Z=None):

        if self.status != 0:
            return

        if not any([X, Y, Z]):
            return

        # Identify line that contains ANTENNA: DELTA H/E/N
        antenna_delta_header_idx = search_idx_value(self.rinex_data, 'ANTENNA: DELTA H/E/N')
        antenna_delta_meta = self.rinex_data[antenna_delta_header_idx]
        # Parse line
        X_meta = antenna_delta_meta[0:14]
        Y_meta = antenna_delta_meta[14:28]
        Z_meta = antenna_delta_meta[28:42]
        label = antenna_delta_meta[60:]
        # Edit line
        if X: # Format as 14.4 float. Set to zero if too large but should not happen
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
        self.rinex_data[antenna_delta_header_idx] = new_line

        return


    def set_agencies(self, operator=None, agency=None):

        if self.status != 0:
            return

        if not any([operator, agency]):
            return

        # Identify line that contains OBSERVER / AGENCY
        agencies_header_idx = search_idx_value(self.rinex_data, 'OBSERVER / AGENCY')
        agencies_meta = self.rinex_data[agencies_header_idx]
        # Parse line
        operator_meta = agencies_meta[0:20]
        agency_meta = agencies_meta[20:40]
        label = agencies_meta[60:]
        # Edit line
        if operator: # Format as 14.4 float. Cut if too large but will not happen
            operator_meta = operator[:20].ljust(20)
        if agency:
            agency_meta = agency[:40].ljust(40)
        new_line = operator_meta + agency_meta + label
        # Set line
        self.rinex_data[agencies_header_idx] = new_line

        return


    def set_sat_system(self, sat_system):

        if self.status != 0:
            return

        if not sat_system:
            return

        # Identify line that contains RINEX VERSION / TYPE
        sat_system_header_idx = search_idx_value(self.rinex_data,'RINEX VERSION / TYPE')
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
                          'GLO' : 'R',
                          'GAL' : 'E',
                          'BDS' : 'C',
                          'QZSS' : 'J',
                          'IRNSS' : 'I',
                          'SBAS' : 'S',
                          'MIXED' : 'M'
                          }
            sat_system_code = gnss_codes.get(sat_system)

            if not sat_system_code:
                sat_system_code = sat_system
                sat_system = ''

        sat_system_meta = sat_system_code[0] + ' : ' + sat_system[:16].ljust(16)
        new_line = rinex_ver_meta + ' ' * 11 + type_of_rinex_file_meta + sat_system_meta + label
        # Set line
        self.rinex_data[sat_system_header_idx] = new_line

        return


    def add_comment(self, comment):
        '''
        We add the argument comment line at the end of the header
        '''
        if self.status != 0:
            return

        end_of_header_idx = search_idx_value(self.rinex_data, 'END OF HEADER') + 1
        last_comment_idx = max(i for i, e in enumerate(self.rinex_data[0:end_of_header_idx]) if 'COMMENT' in e)

        new_line = ' {} '.format(comment).center(60, '-') + 'COMMENT'
        self.rinex_data.insert(last_comment_idx + 1, new_line)

        return


    def write_to_path(self, path, compression = 'gz'):
        """
        Will turn rinex_data from list to string, utf-8, then compress as hatanaka
        and zip to the 'compression' format, then write to file. The 'compression' param
        will be used as an argument to hatanaka.compress and for naming the output file.
        Available compressions are those of hatanaka compress function :
        'gz' (default), 'bz2', 'Z', or 'none'
        """

        if self.status != 0:
            return

        output_data = '\n'.join(self.rinex_data).encode('utf-8')
        output_data = hatanaka.compress(output_data, compression = compression)

        ### manage compressed extension
        if "rnx" in self.filename:
            filename_out = self.filename.replace("rnx","crx")
        elif ".o" in self.filename:
            filename_out = self.filename.replace(".o",".d")
        else:
            filename_out = self.filename

        if compression == 'none':
            outputfile = os.path.join(path, filename_out)
        else:
            outputfile = os.path.join(path, filename_out + '.' + compression)

        Path(outputfile).write_bytes(output_data)

        return outputfile
