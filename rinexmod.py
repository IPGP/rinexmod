#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This program takes RINEX files (v2 or v3, compressed or not), rename them and 
modifiy their headers, and write them back to a destination directory. 

Check the program's synopsis (with --help option) or read the README 
for more details
(https://github.com/IPGP/rinexmod/blob/master/README.md)

# Credits:
v1 - 2021-02-07 Félix Léger - leger@ipgp.fr
v2 - 2023-03-23 Pierre Sakic - sakic@ipgp.fr
"""

import rinexmod.rinexmod_api as rimo_api

if __name__ == '__main__':

    import argparse
    ##### Class for --modif_kw
    class ParseKwargs(argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):
            setattr(namespace, self.dest, dict())
            for value in values:
                try:
                    key, value = value.split('=')
                    getattr(namespace, self.dest)[key] = value
                except Exception as e:
                    def _print_tips(values):
                        print("********************************************")
                        print("TIP1: be sure you have respected the syntax:")
                        print("      -k keyword_1='value' keyword2='value' ")
                        print("TIP2: don't use -k as last option, it will  ")
                        print("      enroll rinexinput & outputfolder args ")
                        print("      use for instance -t to end -k part    ")        
                        print("********************************************")
                        print(values)
                        return None
                    _print_tips(values)
                    raise e

    ##### Parsing Args
    parser = argparse.ArgumentParser(description='This program takes RINEX files (v2 or v3, compressed or not), rename them and modifiy their headers, and write them back to a destination directory')
    parser.add_argument('rinexinput', type=str,
                        help="Input list file of the RINEX paths to process (generated with a find or ls command for instance) OR a single RINEX file's path (see -a/--alone for a single input file)")
    parser.add_argument('outputfolder', type=str,
                        help='Output folder for modified RINEX files')
    parser.add_argument(
        '-s', '--sitelog', help="Get the RINEX header values from file's site's sitelog. Provide a single sitelog path or a folder contaning sitelogs.", type=str, default="")
    parser.add_argument('-k', '--modif_kw', help="""Modification keywords for RINEX's header fields and/or filename. Will override the information from the sitelog. 
                                                    Format : -k keyword_1='value' keyword2='value'. Acceptable keywords:\n
                                                    comment, marker_name, marker_number, station (legacy alias for marker_name), receiver_serial, receiver_type, receiver_fw, antenna_serial, antenna_type,
                                                    antenna_X_pos, antenna_Y_pos, antenna_Z_pos, antenna_H_delta, antenna_E_delta, antenna_N_delta,
                                                    operator, agency, sat_system, observables (legacy alias for sat_system), interval, filename_file_period (01H, 01D...), filename_data_freq (30S, 01S...), filename_data_source (R, S, U)
                                                    """, nargs='*', action=ParseKwargs, default=None)
        
    parser.add_argument('-m', '--marker', help="A four or nine character site code that will be used to rename input files. (apply also to the header's MARKER NAME, but a custom -k marker_name='XXXX' overrides it)", type=str, default='')
    parser.add_argument('-n', '--ninecharfile',
                        help='Path of a file that contains 9-char. site names (e.g. from the M3G database)', type=str, default="")
    parser.add_argument('-sti', '--station_info',
                        help='Path of a GAMIT station.info file to obtain GNSS site metadata information (needs also -lfi option)', type=str, default="")
    parser.add_argument('-lfi', '--lfile_apriori',
                        help='Path of a GAMIT apriori apr/L-File to obtain GNSS site position and DOMES information (needs also -sti option)', type=str, default="")    
    parser.add_argument('-r', '--relative', help='Reconstruct files relative subfolders. You have to indicate the common parent folder, that will be replaced with the output folder', type=str, default=0)
    parser.add_argument('-c', '--compression', type=str,
                        help="Set file's compression (acceptable values : 'gz' (recommended to fit IGS standards), 'Z', 'none')", default='')
    parser.add_argument(
        '-l', '--longname', help='Rename file using long name RINEX convention (force gzip compression).', action='store_true', default=False)
    parser.add_argument(
        '-fs', '--force_sitelog', help="If a single sitelog is provided, force sitelog-based header values when RINEX's header and sitelog site name do not correspond. \n If several sitelogs are provided, skip badly-formated sitelogs.", action='store_true', default=False)
    parser.add_argument(
        '-fc', '--force_fake_coords', help="When using GAMIT station.info metadata without apriori coordinates in the L-File, gives fake coordinates at (0°,0°) to the site", action='store_true', default=False)
    parser.add_argument(
        '-fr', '--force_rnx_load', help="Force the loading of the input RINEX. Useful if its name is not standard", action='store_true', default=False)
    parser.add_argument(
        '-i', '--ignore', help='Ignore firmware changes between instrumentation periods when getting header values info from sitelogs', action='store_true')
    parser.add_argument(
        '-a', '--alone', help='INPUT is a single/alone RINEX file (and not a list file of RINEX paths)', action='store_true')
    parser.add_argument('-o', '--output_logs',
                        help='Folder where to write output logs. If not provided, logs will be written to OUTPUTFOLDER', type=str)
    parser.add_argument(
        '-w', '--write', help='Write (RINEX version, sample rate, file period) dependant output lists', action='store_true')
    parser.add_argument(
        '-v', '--verbose', help="Print file's metadata before and after modifications.", action='store_true', default=False)
    parser.add_argument(
        '-t', '--sort', help='Sort the input RINEX list.', action='store_true', default=False)
    parser.add_argument(
        '-u', '--full_history', help="Add the full history of the station in the RINEX's 'header as comment.", action='store_true', default=False)
    parser.add_argument(
            '-tol', '--tolerant_file_period', help="the RINEX file period is tolerant and stick to the actual data content, but then can be odd (e.g. 07H, 14H...). A strict file period is applied per default (01H or 01D), being compatible with the IGS conventions", action='store_true', default=False)
    parser.add_argument(
            '-mp', '--multi_process', help="number of parallel multiprocesing (default: %(default)s, no parallelization)", type=int, default=1)
    parser.add_argument(
            '-d', '--debug', help="debug mode, stops if something goes wrong (default: %(default)s)", action='store_true', default=False)
    
    
    
    args = parser.parse_args()

    rinexinput = args.rinexinput
    outputfolder = args.outputfolder
    sitelog = args.sitelog
    modif_kw = args.modif_kw
    marker = args.marker
    ninecharfile = args.ninecharfile
    relative = args.relative
    compression = args.compression
    longname = args.longname
    force_sitelog = args.force_sitelog
    force_rnx_load = args.force_rnx_load
    ignore = args.ignore
    alone = args.alone
    output_logs = args.output_logs
    write = args.write
    verbose = args.verbose
    sort = args.sort
    full_history = args.full_history
    tolerant_file_period = args.tolerant_file_period 
    multi_process = args.multi_process
    debug = args.debug
    station_info = args.station_info
    lfile_apriori = args.lfile_apriori
    force_fake_coords = args.force_fake_coords
    
    
    rimo_api.rinexmod_cli(rinexinput,
                          outputfolder,
                          sitelog=sitelog,
                          modif_kw=modif_kw,
                          marker=marker,
                          longname=longname,
                          force_sitelog=force_sitelog,
                          force_rnx_load=force_rnx_load,
                          ignore=ignore, 
                          ninecharfile=ninecharfile, 
                          compression=compression,
                          relative=relative, 
                          verbose=verbose, 
                          alone=alone, 
                          output_logs=output_logs, 
                          write=write, 
                          sort=sort,
                          full_history=full_history,
                          tolerant_file_period=tolerant_file_period,
                          multi_process=multi_process,
                          debug=debug,
                          station_info=station_info,
                          lfile_apriori=lfile_apriori,
                          force_fake_coords=force_fake_coords) 


