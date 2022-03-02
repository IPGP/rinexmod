#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Class
2022-02-01 Félix Léger - felixleger@gmail.com
"""

import os, re
import hatanaka
from pathlib import Path
from datetime import datetime


class RinexFile:
    """
    Will store a compressed rinex file content in a file-like list of strings using
    using the hatanaka library.
    Will then provide methods to modifiy the file's header.
    """

    def __init__(self, rinexfile):

        self.path = rinexfile
        self.filename = self._filename()
        self.rinex_data, self.status = self._load_rinex_data()


    def _load_rinex_data(self):
        """
        Load the uncompressed rinex data into a list var using hatanaka library.
        Will return a table of lines of the uncompressed file, and a status.
        Status 0 is OK. The other ones corresponds to the errors codes raised in
        rinexarchive and in rinexmod.
        01 - The specified file does not exists
        02 - Not an observation Rinex file
        03 - Invalid  or empty Zip file
        04 - Invalid Compressed Rinex file
        """

        # Checking if existing file
        if not os.path.isfile(self.path):
            return None, 1

        pattern = re.compile('....[0-9]{3}.\.[0-9]{2}(d\.((Z)|(gz)))')

        if not pattern.match(os.path.basename(self.path)):
            status = 2
        else:
            status = 0

        try:
            rinex_data = hatanaka.decompress(self.path).decode('utf-8')
            rinex_data = rinex_data.split('\n')

        except ValueError:
            return None, 3

        except hatanaka.hatanaka.HatanakaException:
            return None, 4

        return rinex_data, status


    def _filename(self):
        """ Get filename without compression extension """

        filename = os.path.splitext(os.path.basename(self.path))[0]

        return filename


    def __str__(self):
        """
        Defnies a print method for the rinex file object. Will print all the
        header, plus 20 lines of data, plus the number of not printed lines.
        """
        if self.rinex_data == None:
            return ''

        # We get header
        end_of_header_idx = next(i for i, e in enumerate(self.rinex_data) if 'END OF HEADER' in e) + 1
        str_RinexFile = self.rinex_data[0:end_of_header_idx]
        # We add 20 lines of data
        str_RinexFile.extend(self.rinex_data[end_of_header_idx:end_of_header_idx + 20])
        # We add a line that contains the number of lines not to be printed
        lengh = len(self.rinex_data) - len(str_RinexFile) -20
        cutted_lines_rep = ' ' * 20 + '[' + '{} lines hidden'.format(lengh).center(40, '.') + ']' + ' ' * 20
        str_RinexFile.append(cutted_lines_rep)

        return '\n'.join(str_RinexFile)


    def print_metadata(self):
        """
        Returns a printable, with carriage-return, string of metadata lines from
        the header
        """
        if self.status != 0:
            return ''

        metadata = []

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
                    metadata.append(line)
                    break

        print('\n'.join(metadata))

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

        outputfile = os.path.join(path, self.filename + '.' + compression)

        Path(outputfile).write_bytes(output_data)

        return


    def get_station(self):

        if self.status != 0:
            return ''

        meta_station = 'MARKER NAME'

        for line in self.rinex_data:
            if re.search(meta_station, line):
                meta_station = line
                break

        if meta_station == 'MARKER NAME':
            return None

        meta_station = meta_station.split(' ')[0].upper()

        return meta_station


    def get_date(self):

        if self.status != 0:
            return ''

        meta_date = 'TIME OF FIRST OBS'

        # metadata_list = self.metadata.split('\n')

        for line in self.rinex_data:
            if re.search(meta_date, line):
                meta_date = line
                break

        if meta_date == 'TIME OF FIRST OBS':
            return None

        meta_date = meta_date.split()
        meta_date = datetime.strptime(' '.join(meta_date[0:6]) , '%Y %m %d %H %M %S.%f0')

        return meta_date


    def set_receiver(self, serial=None, type=None, firmware=None):

        if self.status != 0:
            return

        # Identify line that contains REC # / TYPE / VERS
        receiver_header_idx = next(i for i, e in enumerate(self.rinex_data) if 'REC # / TYPE / VERS' in e)
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

        # Identify line that contains ANT # / TYPE
        antenna_header_idx = next(i for i, e in enumerate(self.rinex_data) if 'ANT # / TYPE' in e)
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


    def set_antenna_pos(self, X=None, Y=None, Z=None):

        if self.status != 0:
            return

        # Identify line that contains APPROX POSITION XYZ
        antenna_pos_header_idx = next(i for i, e in enumerate(self.rinex_data) if 'APPROX POSITION XYZ' in e)
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

        # Identify line that contains ANTENNA: DELTA H/E/N
        antenna_delta_header_idx = next(i for i, e in enumerate(self.rinex_data) if 'ANTENNA: DELTA H/E/N' in e)
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


    def set_marker(self, station):

        if self.status != 0:
            return

        # Identify line that contains MARKER NAME
        marker_name_header_idx = next(i for i, e in enumerate(self.rinex_data) if 'MARKER NAME' in e)
        marker_name_meta = self.rinex_data[marker_name_header_idx]
        # Edit line
        new_line = '{}'.format(station.ljust(60)) + 'MARKER NAME'
        # Set line
        self.rinex_data[marker_name_header_idx] = new_line

        # Identify line that contains MARKER NUMBER
        marker_number_header_idx = next(i for i, e in enumerate(self.rinex_data) if 'MARKER NUMBER' in e)
        if marker_number_header_idx:
            new_line = '{}'.format(station.ljust(60)) + 'MARKER NUMBER'
            # Set line
            self.rinex_data[marker_number_header_idx] = new_line

        return


    def set_agencies(self, operator=None, agency=None):

        if self.status != 0:
            return

        # Identify line that contains OBSERVER / AGENCY
        agencies_header_idx = next(i for i, e in enumerate(self.rinex_data) if 'OBSERVER / AGENCY' in e)
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


    def set_observable_type(self, observable_type):

        if self.status != 0:
            return

        # Identify line that contains RINEX VERSION / TYPE
        observable_type_header_idx = next(i for i, e in enumerate(self.rinex_data) if 'RINEX VERSION / TYPE' in e)
        observable_type_meta = self.rinex_data[observable_type_header_idx]
        # Parse line
        rinex_ver_meta = observable_type_meta[0:9]
        type_of_rinex_file_meta = observable_type_meta[20:40]
        # observable_type_meta = observable_type_meta[40:60]
        label = observable_type_meta[60:]
        # Edit line
        if '+' in observable_type:
            observable_type = 'MIXED'
            observable_type_code = 'M'
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
            observable_type_code = gnss_codes[observable_type]

        observable_type_meta = observable_type_code[0] + ' : ' + observable_type[:16].ljust(16)
        new_line = rinex_ver_meta + ' ' * 11 + type_of_rinex_file_meta + observable_type_meta + label
        # Set line
        self.rinex_data[observable_type_header_idx] = new_line

        return


    def add_comment(self, comment):

        if self.status != 0:
            return

        end_of_header_idx = next(i for i, e in enumerate(self.rinex_data) if 'END OF HEADER' in e) + 1
        last_comment_idx = max(i for i, e in enumerate(self.rinex_data[0:end_of_header_idx]) if 'COMMENT' in e)

        new_line = ' {} '.format(comment).center(60, '-') + 'COMMENT'
        self.rinex_data.insert(last_comment_idx + 1, new_line)

        return


















        #EOF
