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

import argparse
import textwrap

import rinexmod
import rinexmod.rinexmod_api as rimo_api

from argparse import RawTextHelpFormatter

def main():

    class SmartFormatter(argparse.HelpFormatter):
        # source: https://stackoverflow.com/a/22157136/3464212
        def _split_lines(self, text, width):
            if text.startswith("R|"):
                return text[2:].splitlines()
            # this is the RawTextHelpFormatter._split_lines
            return argparse.HelpFormatter._split_lines(self, text, width)

    # Parsing Args
    parser = argparse.ArgumentParser(
        description="rinexmod takes RINEX files (v2 or v3/4, compressed or not), "
        "rename them and modifiy their headers, and write them back to a destination directory",
        #formatter_class=SmartFormatter,
        formatter_class=RawTextHelpFormatter,
        epilog=textwrap.dedent(
            "RinexMod "
            + str(rinexmod.__version__)
            + " - GNU Public Licence v3 - P. Sakic et al. - IPGP-OVS - https://github.com/IPGP/rinexmod"
        ),
    )
    required = parser.add_argument_group("required arguments")
    optional = parser.add_argument_group("optional arguments")

    required.add_argument(
        "-i",
        "--rinexinput",
        type=str,
        required=True,
        nargs="+",
        help="Input RINEX file(s). It can be: \n"
        "1) a list file of the RINEX paths to process (generated with find or ls command for instance) \n"
        "2) several RINEX files paths \n"
        "3) a single RINEX file path (see -a/--alone for a single input file)",
    )
    required.add_argument(
        "-o",
        "--outputfolder",
        type=str,
        required=True,
        help="Output folder for modified RINEX files",
    )
    optional.add_argument(
        "-s",
        "--sitelog",
        help="Get the RINEX header values from file's site's sitelog."
        " Provide a single sitelog path or a folder contaning sitelogs.",
        type=str,
        default="",
    )

    optional.add_argument(
        "-k",
        "--modif_kw",
        help="Modification keywords for RINEX's header fields and/or filename.\n"
            "Format: -k keyword_1='value1' keyword2='value2'.\n"
            "Will override the information from the sitelog.\n"
            "Acceptable keywords: comment, marker_name, marker_number, station (legacy alias for marker_name), "
            "receiver_serial, receiver_type, receiver_fw, antenna_serial, antenna_type, "
            "antenna_X_pos, antenna_Y_pos, antenna_Z_pos, antenna_H_delta, "
            "antenna_E_delta, antenna_N_delta, operator, agency, sat_system, "
            "observables (legacy alias for sat_system), interval, "
            "filename_file_period (01H, 01D...), filename_data_freq (30S, 01S...), filename_data_source (R, S, U)",
        nargs="+",
        metavar="KEY=VALUE",
        action=rimo_api.ParseKwargs,
        default=None,
    )
    optional.add_argument(
        "-m",
        "--marker",
        help="A four or nine-character site code that will be used to rename input files."
        "(apply also to the header's MARKER NAME, but a custom -k marker_name='XXXX' overrides it)",
        type=str,
        default="",
    )
    optional.add_argument(
        "-co",
        "--country",
        help="A three-character string corresponding to the ISO 3166 Country code "
        "that will be used to rename input files. "
        "It overrides other country code sources (sitelog, --marker...). "
        "List of ISO country codes: https://en.wikipedia.org/wiki/List_of_ISO_3166_country_codes",
        type=str,
        default="",
    )
    optional.add_argument(
        "-n",
        "--ninecharfile",
        help="Path of a file that contains 9-char. site names (e.g. from the M3G database)",
        type=str,
        default="",
    )
    optional.add_argument(
        "-sti",
        "--station_info",
        help="Path of a GAMIT station.info file to obtain GNSS site metadata information (needs also -lfi option)",
        type=str,
        default="",
    )
    optional.add_argument(
        "-lfi",
        "--lfile_apriori",
        help="Path of a GAMIT apriori apr/L-File to obtain GNSS site position "
        "and DOMES information (needs also -sti option)",
        type=str,
        default="",
    )
    optional.add_argument(
        "-r",
        "--relative",
        help="Reconstruct files relative subfolders."
        "You have to indicate the common parent folder, "
        "that will be replaced with the output folder",
        type=str,
        default=0,
    )
    optional.add_argument(
        "-nh",
        "--no_hatanaka",
        help="Skip high-level RINEX-specific Hatanaka compression (performed per default). See also -c 'none'",
        action="store_true",
        default=False,
    )
    optional.add_argument(
        "-c",
        "--compression",
        type=str,
        help="Set low-level RINEX file compression "
        "(acceptable values : 'gz' (recommended to fit IGS standards), 'Z', 'none', default: %(default)s)",
        choices=['gz', 'Z', 'none'],
        default="gz",
    )
    optional.add_argument(
        "-l",
        "--longname",
        help="Force RINEX file renaming with long name convention (force gzip compression)."
        "Mutually exclusive with shortname.",
        action="store_true",
        default=False,
    )
    optional.add_argument(
        "-sh",
        "--shortname",
        help="Force RINEX file renaming with short name convention."
        "Mutually exclusive with longname.",
        action="store_true",
        default=False,
    )
    optional.add_argument(
        "-fs",
        "--force_sitelog",
        help="If a single sitelog is provided, force sitelog-based header values when RINEX's header and sitelog site"
        " name do not correspond. \n If several sitelogs are provided, skip badly-formated sitelogs.",
        action="store_true",
        default=False,
    )
    optional.add_argument(
        "-fc",
        "--force_fake_coords",
        help="When using GAMIT station.info metadata without apriori coordinates in the L-File, "
        "gives fake coordinates at (0°,0°) to the site",
        action="store_true",
        default=False,
    )
    optional.add_argument(
        "-fr",
        "--force_rnx_load",
        help="Force the loading of the input RINEX. Useful if its name is not standard",
        action="store_true",
        default=False,
    )
    optional.add_argument(
        "-ig",
        "--ignore",
        help="Ignore firmware changes between instrumentation periods when getting header values info from sitelogs",
        action="store_true",
    )
    optional.add_argument(
        "-a",
        "--alone",
        help="INPUT is a single/alone RINEX file (and not a list file of RINEX paths)",
        action="store_true",
    )
    optional.add_argument(
        "-ol",
        "--output_logs",
        help="Folder where to write output logs. If not provided, logs will be written to OUTPUTFOLDER",
        type=str,
    )
    optional.add_argument(
        "-w",
        "--write",
        help="Write (RINEX version, sample rate, file period) dependant output lists",
        action="store_true",
    )
    optional.add_argument(
        "-v",
        "--verbose",
        help="Print file's metadata before and after modifications.",
        action="store_true",
        default=False,
    )
    optional.add_argument(
        "-t",
        "--sort",
        help="Sort the input RINEX list.",
        action="store_true",
        default=False,
    )
    optional.add_argument(
        "-u",
        "--full_history",
        help="Add the full history of the station in the RINEX's 'header as comment.",
        action="store_true",
        default=False,
    )
    optional.add_argument(
        "-fns",
        "--filename_style",
        help="Set the RINEX filename style.\n"
        "acceptable values : 'basic' (per default), 'flex', 'exact'.\n"
        "* 'basic': a simple mode to apply a strict filename period (01H or 01D), "
        "being compatible with the IGS conventions.\n"
        "e.g.: FNG000GLP_R_20242220000_01D_30S_MO.crx.gz\n"
        "* 'flex': the filename period is tolerant and corresponds to"
        "the actual data content, but then can be odd (e.g. 07H, 14H...). "
        "The filename start time is rounded to the hour.\n"
        "e.g.: FNG000GLP_R_20242221800_06H_30S_MO.crx.gz\n"
        "* 'exact': the filename start time is strictly "
        "the one of the first epoch in the RINEX. "
        "Useful for some specific cases like splicing.\n"
        "e.g.: FNG000GLP_R_20242221829_06H_30S_MO.crx.gz\n"
        "(default: %(default)s)",
        choices=['basic', 'flex', 'exact'],
        default='basic',
    )
    optional.add_argument(
        "-mp",
        "--multi_process",
        help="Number of parallel multiprocesing (default: %(default)s, no parallelization)",
        type=int,
        default=1,
    )
    optional.add_argument(
        "-d",
        "--debug",
        help="Debug mode, stops if something goes wrong (default: %(default)s)",
        action="store_true",
        default=False,
    )

    optional.add_argument(
        "-rm",
        "--remove",
        help="Remove input RINEX file if the output RINEX is correctly written. Use it at your own risk. "
             "(default: %(default)s)",
        action="store_true",
        default=False,
    )

    optional.add_argument(
        "-krr",
        "--keep_rnx_rec",
        help="Keep the RINEX receiver header record in the output RINEX. "
             "Metadata from the external source (e.g. sitelogs) will not be modded. "
             "(default: %(default)s)",
        action="store_true",
        default=False,
    )

    args = parser.parse_args()

    rimo_api.rinexmod_cli(
        args.rinexinput,
        args.outputfolder,
        sitelog=args.sitelog,
        modif_kw=args.modif_kw,
        marker=args.marker,
        country=args.country,
        longname=args.longname,
        shortname=args.shortname,
        force_sitelog=args.force_sitelog,
        force_rnx_load=args.force_rnx_load,
        ignore=args.ignore,
        ninecharfile=args.ninecharfile,
        no_hatanaka=args.no_hatanaka,
        compression=args.compression,
        relative=args.relative,
        verbose=args.verbose,
        alone=args.alone,
        output_logs=args.output_logs,
        write=args.write,
        sort=args.sort,
        full_history=args.full_history,
        filename_style=args.filename_style,
        multi_process=args.multi_process,
        debug=args.debug,
        station_info=args.station_info,
        lfile_apriori=args.lfile_apriori,
        force_fake_coords=args.force_fake_coords,
        remove=args.remove,
        keep_rnx_rec=args.keep_rnx_rec
    )

if __name__ == '__main__':
    main()