#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Class
2021-02-07 Félix Léger - leger@ipgp.fr
"""

import os, re
from   datetime import datetime
import configparser
import json, copy


class Sitelog:
    """
    Parses and store in a dict informations from an IGS sitelog.
    Requires one parameter, the sitelog path.
    At instantiation, will parse the sitelog and store in a dict all parsed values.
    Dict accessible via Sitelog.info
    Will also create a tab, stored in Sitelog.instrumentations, containing all
    the different instrumentation periods, tab containing a start and an end date,
    and for each line a dict of antenna instrumentation an receiver isntrumentation.

    3 available methods:
    get_instrumentation takes a start and an end date and returns the instrumentation
    corresponding to the period, if found.
    teqcargs also takes a start and an end date and returns a string of args to
    pass to teqc so that it will modify a rinex file's header.
    write_json will write the dict of the parsed values from the sitelog to a
    json file.
    """

    def __init__(self, sitelogfile):

        self.path = sitelogfile
        self.info = self._sitelog2dict()
        if self.info:
            self.instrumentations = self._instrumentations()
        else:
            self.instrumentations = None


    def _sitelog2dict(self):
        """
        Main function for reading a Sitelog file. From the sitelog file,
        returns a dict with all readed values.
        """
        ###### Input and output file tests #######

        # Checking if inexisting file
        if not os.path.isfile(self.path):
            # print('The provided Sitelog is not valid : ' + self.path)
            return None

        # Getting filename and basename for output purposes
        filename = (os.path.splitext(os.path.basename(self.path))[0])
        dirname = os.path.dirname(self.path)

        ####### Reading Sitelog File #########

        # Reading the sitelog file
        try:
            with open(self.path, "r", encoding="utf-8") as datafile:
                sitelog = datafile.read()
        except UnicodeDecodeError: # OVPF sitelogs are in iso-8859-1
            try:
                with open(self.path, "r", encoding="iso-8859-1") as datafile:
                    sitelog = datafile.read()
            except:
                raise

        # We delete all initial space.
        pattern = re.compile(r'\n +')
        sitelog = re.sub(pattern, r'\n', sitelog)

        # We rearrange multiline content to be complient with .ini format.
        pattern = re.compile(r'(\n *): *')
        sitelog = re.sub(pattern, ' ', sitelog)

        # We transform  multiple contacts into sub blocs
        pattern = re.compile(r'((?:Secondary|Primary) [Cc]ontact):{0,1}')
        sitelog = re.sub(pattern, r'[\1]', sitelog)

        # We remove the final graphic if exists
        antennagraphic = re.search(r'Antenna Graphics with Dimensions', sitelog)
        if antennagraphic:
            sitelog = sitelog[:antennagraphic.start(0)]

        # List of formated blocs
        formatedblocs = []
        # Final dict to store values
        sitelogdict = {}

        # We split the file into major blocs (reading the '4.'' type pattern)
        iter = re.finditer(r'\d{1,2}\. +.+\n', sitelog)
        indices = [m.start(0) for m in iter]

        blocs = [sitelog[i:j] for i,j in zip(indices, indices[1:]+[None])]

        if len(blocs) == 0:
            # print('The provided Sitelog is not correct : ' + self.path)
            return None

        # We loop into those blocs, after a test that permits keeping only blocs
        # beggining with patterns like '6.'. This permits removing the title bloc.
        for bloc in [bloc for bloc in blocs if re.match(r'\d.', bloc[:2])]:

            # We search for '4.3', '4.3.', '4.2.3' patterns for subbloc detection
            iter = re.finditer(r'\n\d{1,2}\.\d{0,2}\.{0,1}\w{0,2}\.{0,1}', bloc)
            indices = [m.start(0) +1 for m in iter]

            if len(indices) > 0: # If subblocs
                subblocs = [bloc[i:j] for i,j in zip(indices, indices[1:]+[None])]

                for subbloc in subblocs:
                    # We separate index (the first line) from values
                    index, subbloc = subbloc.split('\n', 1)
                    # If available, the data contained in the first line (now stored in index)
                    # is pushed back in the subbloc varaible in a new 'type' entry.
                    try:
                        index, title = index.split(' ', 1)
                        if ':' not in title:
                            title = 'type : ' + title
                        subbloc = title.lstrip() + '\n' + subbloc
                    except :
                        pass
                    # We append the subbloc to the list of blocs to read
                    formatedblocs.append([index, subbloc])

            elif re.search(r'\n', bloc):
                # Get index and bloc content
                index, bloc = bloc.split('\n', 1)
                index = re.match(r'\d{1,2}\.', index).group(0)

                # We append it to the list of blocs to read
                formatedblocs.append([index, bloc])

            else:
                pass

        # Now that blocs are formated, we read them with configparser
        for [index, bloc] in formatedblocs:

            if 'x' in index[0:5]:
                pass # If it's a model section (like 3.x), we don't proceed it
            else:
                # We add a section header to work on it with ConfigParser
                bloc = '[dummy_section]\n' + bloc

                cfgparser = configparser.RawConfigParser(allow_no_value=True)
                cfgparser.optionxform = str # Respect case
                cfgparser.read_string(bloc)

                # We construct the bloc dict
                blocdict = {}
                for section_name in cfgparser.sections():
                    # For 'dummy_section' section, we quit the section_name
                    if section_name == 'dummy_section':
                        blocdict.update(dict(cfgparser[section_name]))
                    # For other sections (Primary & Secondary contact, added earlier), we keep the section_name
                    else:
                        blocdict.update({section_name: dict(cfgparser[section_name])})

                # We append the bloc dict to the global dict
                sitelogdict[index] = blocdict

        # Contact corrections - putting the field 'Additional Information' in the right level dict
        # and removing network information
        for key in [key for key in sitelogdict.keys() if key in ['11.' ,'12.']]:
            if 'network' in sitelogdict[key]['Agency'].lower():
                index_network =  sitelogdict[key]['Agency'].lower().index('network')
                sitelogdict[key]['Agency'] = sitelogdict[key]['Agency'][:index_network]
            # Removing extra spaces
            sitelogdict[key]['Agency'] = sitelogdict[key]['Agency'].strip()
            sitelogdict[key]['Agency'] = " ".join(sitelogdict[key]['Agency'].split())
            if sitelogdict[key]['Secondary Contact']['Additional Information']:
                # Putting the 'Additional Information' in the lower level dict
                sitelogdict[key]['Additional Information'] = sitelogdict[key]['Secondary Contact']['Additional Information']
                # Removing it from the incorrect dict level
                sitelogdict[key]['Secondary Contact'].pop('Additional Information', None)


        return sitelogdict


    def _instrumentations(self):
        """
        This function identifies the different complete installations from the antenna
        and receiver change dates, then returns a table with only instrumented periods.
        """

        ##### Constructing a list of date intervals from all changes dates #####

        listdates = []

        # We extract dates for blocs 3. and 4. (reveiver, antenna)
        for key in [key for key in self.info.keys() if key.startswith('3.') or key.startswith('4.')]:
            # Formating parsed dates - set empty to 'infinity' date. If not a date, it's because it's an open border.
            self.info[key]['Date Installed'] = self._tryparsedate(self.info[key]['Date Installed'])
            self.info[key]['Date Removed'] = self._tryparsedate(self.info[key]['Date Removed'])
            # Adding dates to listdate
            listdates += self.info[key]['Date Installed'], self.info[key]['Date Removed']

        # # We extract dates from blocs 8 (meteo). If found and parsable, we add them to the list.
        # for key in [key for key in self.info.keys() if key.startswith('8.')]:
        #     dates = re.findall(r'\d{4}-\d{1,2}-\d{1,2}', self.info[key]['Effective Dates'])
        #     if len(dates) == 2:
        #         metpackstartdate = self._tryparsedate(dates[0])
        #         metpackenddate = self._tryparsedate(dates[1])
        #         listdates += metpackstartdate, metpackenddate
        #     elif len(dates) == 1:
        #         metpackstartdate = self._tryparsedate(dates[0])
        #         metpackenddate = self._tryparsedate(None) # Infinity date
        #         listdates += metpackstartdate, metpackenddate
        #     else:
        #         pass

        # Quitting null values
        listdates = [date for date in listdates if date]
        # Quitting duplicates
        listdates = list(set(listdates))
        # Sorting
        listdates.sort()

        # List of installations. An installation is a date interval, a receiver and an antena
        installations = []

        # Constructiong the installations list - date intervals
        for i in range(0, len(listdates) - 1):
            # Construct interval from listdates
            dates = [listdates[i], listdates[i+1]]
            # Setting date interval in Dict of installation
            installation = dict(dates = dates, receiver = None, antenna = None, metpack = None)
            # Append it to list of installations
            installations.append(installation)

        ##### Getting Receiver info for each interval #####

        receivers = [self.info[key] for key in self.info.keys() if key.startswith('3.')]

        # Constructiong the installations list - Receivers
        for installation in installations:
            # We get the receiver corresponding to the date interval
            for receiver in receivers:
                if (receiver['Date Installed']  <= installation['dates'][0]) and \
                   (receiver['Date Removed'] >= installation['dates'][1]) :
                    installation['receiver'] = receiver
                    # Once found, we quit the loop
                    break

        ##### Getting Antena info for each interval #####

        antennas = [self.info[key] for key in self.info.keys() if key.startswith('4.')]

        # Constructiong the installations list - Antennas
        for installation in installations:
            # We get the antenna corresponding to the date interval
            for antenna in antennas:
                if (antenna['Date Installed']  <= installation['dates'][0]) and \
                   (antenna['Date Removed'] >= installation['dates'][1]) :
                    installation['antenna'] = antenna
                    # Once found, we quit the loop
                    break

        ##### Removing from installation list periods without antenna or receiver #####

        installations = [i for i in installations if i['receiver'] and i['antenna']]

        return installations


    def _tryparsedate(self, date):
        # Different date format to test on the string in case of bad standard compliance
        formats = ['%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%dT%H:%MZ', '%Y-%m-%d %H:%M', '%Y-%m-%dT%H:%M',
                   '%Y/%m/%dT%H:%MZ', '%Y-%m-%d %H:%M', '%Y-%m-%dT%H:%M',
                   '%d/%m/%YT%H:%MZ', '%d/%m/%Y %H:%M', '%d/%m/%YT%H:%M',
                   '%Y-%m-%d',        '%Y/%m/%d',       '%d/%m/%Y'      ]
        if date:
            # Parse to date trying different formats
            for format in formats:
                try:
                    date = datetime.strptime(date, format)
                    break
                except:
                    pass
        if not isinstance(date, datetime):
            # We set the date to 'infinity' date. If not a date, it's because it's an open border.
            date = datetime.strptime('9999-01-01', '%Y-%m-%d')

        return date


    def get_instrumentation(self, starttime, endtime, ignore = False):
        '''
        We get the installation corresponding to the starttime and endtime.
        If force option set to True, we will force ignoring the firmware version
        modification between two periods and consider only the other parameters
        '''

        # We get the installation corresponding to the starttime and endtime
        thisinstall = None
        ignored = False

        for installation in self.instrumentations:
            if installation['dates'][0] <= starttime and installation['dates'][1] >= endtime:
                thisinstall = installation
                break

        # If we can't find a corresponding installation period and we use the force
        # option, we will force ignoring the firmware version modification and
        # consider only the other parameters
        if not thisinstall and ignore:

            # We work with consecutive instrumentation periods
            for i in range(0, len(self.instrumentations) - 1):
                if self.instrumentations[i]['dates'][0] <= starttime \
                    and self.instrumentations[i+1]['dates'][1] >= endtime:

                    # we copy the two instrumentation periods dictionnary to remove firmware info
                    nofirmware_instrumentation_i = copy.deepcopy(self.instrumentations[i])
                    nofirmware_instrumentation_i1 = copy.deepcopy(self.instrumentations[i+1])

                    # We remove date infos
                    nofirmware_instrumentation_i.pop('dates')
                    nofirmware_instrumentation_i1.pop('dates')
                    for e in ['Date Removed', 'Date Installed', 'Additional Information']:
                        nofirmware_instrumentation_i['antenna'].pop(e)
                        nofirmware_instrumentation_i['receiver'].pop(e)
                        nofirmware_instrumentation_i1['antenna'].pop(e)
                        nofirmware_instrumentation_i1['receiver'].pop(e)

                    # We remove Firmware info
                    nofirmware_instrumentation_i['receiver'].pop('Firmware Version')
                    nofirmware_instrumentation_i1['receiver'].pop('Firmware Version')

                    # If, except dates and firmware version, the dicts are equls, we set
                    # instrumentation to the first one of the two.
                    if nofirmware_instrumentation_i == nofirmware_instrumentation_i1:
                        thisinstall = self.instrumentations[i]
                        ignored = True


        return thisinstall, ignored


    def merge_firmwares(self):


        return installations


    def teqcargs(self, starttime, endtime, ignore = False):
        """
        Will return a string of teqc args containing all infos from the sitelog,
        incuding instrumetnation infos taking into account a start and an end date.
        """

        instrumentation, ignored = self.get_instrumentation(starttime, endtime, ignore)

        if not instrumentation:
            return '', ignored

        ########### GNSS one-letter codes ###########

        # From https://www.unavco.org/software/data-processing/teqc/tutorial/tutorial.html
        gnss_codes = {
                      'GPS': 'G',
                      'GLO' : '­R',
                      'GAL' : '­E',
                      'BDS' : '­C',
                      'QZSS' : '­J',
                      'IRNSS' : 'I',
                      'SBAS' : 'S'
                      }

        # GNSS system. M if multiple, else, one letter code from gnss_codes dict.
        o_system = instrumentation['receiver']['Satellite System']
        if '+' in o_system:
            o_system = 'M'
        else:
            o_system = gnss_codes[o_system]

        # We construct the TEQC args line
        teqcargs = [
                    "-O.mo[nument] '{}'".format(self.info['1.']['Four Character ID']),
                    "-M.mo[nument] '{}'".format(self.info['1.']['Four Character ID']),
                    "-O.mn '{}'".format(self.info['1.']['Four Character ID']),
                    "-O.px[WGS84xyz,m] {} {} {}".format(self.info['2.']['X coordinate (m)'],
                                                        self.info['2.']['Y coordinate (m)'],
                                                        self.info['2.']['Z coordinate (m)']),
                    "-O.s[ystem] {}".format(o_system),
                    "-O.rt '{}'".format(instrumentation['receiver']['Receiver Type']),
                    "-O.rn '{}'".format(instrumentation['receiver']['Serial Number']),
                    "-O.rv '{}'".format(instrumentation['receiver']['Firmware Version']),
                    "-O.at '{}'".format(instrumentation['antenna']['Antenna Type']),
                    "-O.an '{}'".format(instrumentation['antenna']['Serial Number']),
                    "-O.pe[hEN,m] {} {} {}".format(instrumentation['antenna']['Marker->ARP Up Ecc. (m)'].zfill(8),
                                                   instrumentation['antenna']['Marker->ARP East Ecc(m)'].zfill(8),
                                                   instrumentation['antenna']['Marker->ARP North Ecc(m)'].zfill(8)),
                    "-O.o[perator] '{}'".format(self.info['11.']['Preferred Abbreviation']),
                    "-O.r[un_by] '{}'".format(self.info['11.']['Preferred Abbreviation']),
                    "-O.ag[ency] '{}'".format(self.info['12.']['Preferred Abbreviation'])
                    ]

        return teqcargs, ignored


    def write_json(self, output = None):
        """
        Writes sitelog's dict to json. If no output provided, will write it in
        the same directory as the sitelog.
        """

        filename = (os.path.splitext(os.path.basename(self.path))[0])
        if not output:
            output = os.path.dirname(self.path)
        elif not os.path.isdir(output):
            print("error, output folder incorrect " + output)
            return None

        outputfilejson = os.path.join(output, filename + '.json')
        with open(outputfilejson, "w+") as j:
            json.dump(self.info, j, default=str)

        return outputfilejson
