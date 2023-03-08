#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This script takes a list of RINEX Hanakata compressed files (.d.Z or .d.gz or .rnx.gz),
loop the RINEX files list to modifiy the file's header. It then write them back to Hanakata
compressed format in an output folder. It permits also to rename the files changing
the four first characters of the file name with another site code. It can write
those files with the long name naming convention with the --longname option.

Two ways of passing parameters to modifiy headers are possible:

--modif_kw : you pass as argument the field(s) that you want to modifiy and its value.
                      Acceptable_keywords are : marker_name, marker_number, 
                      site (legacy alias for marker_name), receiver_serial,
                      receiver_type, receiver_fw, antenna_serial, antenna_type,
                      antenna_X_pos, antenna_Y_pos, antenna_Z_pos,
                      antenna_H_delta, antenna_E_delta, antenna_N_delta,
                      operator, agency, observables, interval, 
                      filename_file_period, filename_data_freq

--sitelog  : you pass sitelogs file. The argument must be a sitelog path or the path of a folder
               containing sitelogs. You then have to pass a list of files and the script will
               assign sitelogs to correspondig files, based on the file's name.
               The script will take the start and end time of each proceeded file
               and use them to extract from the sitelog the site instrumentation
               of the corresponding period and fill file's header with following infos :
                       Four Character ID
                       X coordinate (m)
                       Y coordinate (m)
                       Z coordinate (m)
                       Receiver Type
                       Serial Number
                       Firmware Version
                       Satellite System (will translate this info to one-letter code, see RinexFile.set_sat_system())
                       Antenna Type
                       Serial Number
                       Marker->ARP Up Ecc. (m)
                       Marker->ARP East Ecc(m)
                       Marker->ARP North Ecc(m)
                       On-Site Agency Preferred Abbreviation
                       Responsible Agency Preferred Abbreviation

You can not provide both --modif_kw and --sitelog options.

The script will add two comment lines, one indicating the source of the modifiaction
(sitelog or arguments) and the other the timestamp of the modification.

USE :

RINEXLIST : Input list file of the RINEX files to process
generated with a find or ls command for instance.
OUTPUTFOLDER : Folder where to write the modified RINEX files. 
This is a compulsory argument, you can not modify files inplace.

OPTIONS :

-s : --sitelog :            Sitelog file in witch rinexmod will find file's period's
                            instrumentation informations, or folder containing sitelogs.
-k : --modif_kw :           Modification keywords for RINEX's header fields and/or filename.
                            Will override the information from the sitelog.
                            The sitelogs must be valid as the script does not check it.
-f : --force :              Force sitelog-based header values when RINEX's header
                            and sitelog's site name do not correspond.
-i : --ignore :             Ignore firmware changes between instrumentation periods
                            when getting headers args info from sitelogs.
-m : --marker :             A four or nine character site code that will be used to rename
                            input files.
                            (apply also to the header\'s MARKER NAME, 
                             but a custom -k marker_name='XXXX' overrides it)
-n : --ninecharfile :       path a of a list file containing 9-char. site names from
                            the M3G database generated with get_m3g_stations.
                            This will be used for longname file's renaming.
                            Not mandatory, but nessessary to get the country code to rename
                            files to long name standard. If not provided the country code will be XXX.
-l : --longname :           Rename file using long name RINEX convention (force gzip compression).
-a : --alone :              Option to provide if you want to run this script on a alone
                            RINEX file and not on a list of files.
-c : --compression :        Set file's compression. Acceptables values : 'gz' (recommended
                            to fit IGS standards), 'Z' or 'none'. Default value will retrieve
                            the actual compression of the input file.
-r : --relative :           Reconstruct files relative subdirectory. You have to indicate the
                            part of the path that is common to all files in the list and
                            that will be replaced with output folder.
-o : --output_logs :        Folder where to write output log. If not provided, logs
                            will be written to OUTPUTFOLDER.
-w : --write :              Write (RINEX version, sample rate, file period, observatory)
                            dependant output lists to log folder.
-v : --verbose:             Will print file's metadata before and after modifications.
-t : --sort:                Sort the input RINEX list.

EXAMPLES:

./rinexmod.py RINEXLIST OUTPUTFOLDER (-k antenna_type='ANT TYPE' antenna_X_pos=9999 agency=AGN) (-m AGAL) (-r ./ROOTFOLDER/) (-f) (-v)
./rinexmod.py (-a) RINEXFILE OUTPUTFOLDER (-s ./sitelogsfolder/stationsitelog.log) (-i) (-w) (-o ./LOGFOLDER) (-v)

REQUIREMENTS :

You need Python Hatanaka library from Martin Valgur:

pip install hatanaka

2021-02-07 Félix Léger - leger@ipgp.fr
"""

import rinexmod_api as rma

if __name__ == '__main__':

    import argparse

    class ParseKwargs(argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):
            setattr(namespace, self.dest, dict())
            for value in values:
                key, value = value.split('=')
                getattr(namespace, self.dest)[key] = value

    # Parsing Args
    parser = argparse.ArgumentParser(description='Read a Sitelog file and create a CSV file output')
    parser.add_argument('rinexlist', type=str,
                        help='Input list file of the RINEX paths to process (see also -a/--alone for a single input file)')
    parser.add_argument('outputfolder', type=str,
                        help='Output folder for modified RINEX files')
    parser.add_argument(
        '-s', '--sitelog', help='Get the RINEX header values from file\'s site\'s sitelog. Provide a single sitelog path or a folder contaning sitelogs.', type=str, default="")
    parser.add_argument('-k', '--modif_kw', help='''Modification keywords for RINEX's header fields and/or filename. Will override the information from the sitelog. 
                                                           Format : keyword_1=\'value\' keyword2=\'value\'. Acceptable keywords:\n
                                                           marker_name, marker_number, station (legacy alias for marker_name), receiver_serial, receiver_type, receiver_fw, antenna_serial, antenna_type,
                                                           antenna_X_pos, antenna_Y_pos, antenna_Z_pos, antenna_H_delta, antenna_E_delta, antenna_N_delta,
                                                           operator, agency, observables, interval, filename_file_period (01H, 01D...), filename_data_freq (30S, 01S...)''', nargs='*', action=ParseKwargs, default=None)
    parser.add_argument('-m', '--marker', help="A four or nine character site code that will be used to rename input files. (apply also to the header\'s MARKER NAME, but a custom -k marker_name='XXXX' overrides it)", type=str, default='')
    parser.add_argument('-n', '--ninecharfile',
                        help='Path of a file that contains 9-char. site names from the M3G database', type=str, default="")
    parser.add_argument('-r', '--relative', help='Reconstruct files relative subfolders. You have to indicate the common parent folder, that will be replaced with the output folder', type=str, default=0)
    parser.add_argument('-c', '--compression', type=str,
                        help='Set file\'s compression (acceptables values : \'gz\' (recommended to fit IGS standards), \'Z\', \'none\')', default='')
    parser.add_argument(
        '-l', '--longname', help='Rename file using long name RINEX convention (force gzip compression).', action='store_true', default=False)
    parser.add_argument(
        '-f', '--force', help="Force sitelog-based header values when RINEX's header and sitelog site name do not correspond", action='store_true')
    parser.add_argument(
        '-i', '--ignore', help='Ignore firmware changes between instrumentation periods when getting header values info from sitelogs', action='store_true')
    parser.add_argument(
        '-a', '--alone', help='INPUT is a alone RINEX file and not a file containing list of RINEX files paths', action='store_true')
    parser.add_argument('-o', '--output_logs',
                        help='Folder where to write output logs', type=str)
    parser.add_argument(
        '-w', '--write', help='Write (RINEX version, sample rate, file period) dependant output lists', action='store_true')
    parser.add_argument(
        '-v', '--verbose', help='Print file\'s metadata before and after modifications.', action='store_true', default=False)
    parser.add_argument('-t', '--sort', help='Sort the input RINEX list.', action='store_true', default=False)
    
    args = parser.parse_args()

    rinexlist = args.rinexlist
    outputfolder = args.outputfolder
    sitelog = args.sitelog
    modif_kw = args.modif_kw
    marker = args.marker
    ninecharfile = args.ninecharfile
    relative = args.relative
    compression = args.compression
    longname = args.longname
    force = args.force
    ignore = args.ignore
    alone = args.alone
    output_logs = args.output_logs
    write = args.write
    verbose = args.verbose
    sort = args.sort
    
    rma.rinexmod_cli(rinexlist,
                     outputfolder,
                     sitelog=sitelog,
                     modif_kw=modif_kw,
                     marker=marker,
                     longname=longname,
                     force=force, 
                     ignore=ignore, 
                     ninecharfile=ninecharfile, 
                     compression=compression,
                     relative=relative, 
                     verbose=verbose, 
                     alone=alone, 
                     output_logs=output_logs, 
                     write=write, 
                     sort=sort)