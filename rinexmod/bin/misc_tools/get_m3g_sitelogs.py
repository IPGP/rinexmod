#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This script will get last version of sitelogs from M3G repository and write them
in an observatory dependent subfolder set in 'observatories'.
The -d --delete option will delete old version as to get only last version even
in a name changing case.
The -o --obsevatory option will download sitelogs for the specified observatory
only. Possible values : OVSM|OVSG|OVPF|REVOSIMA
USE :


* OUTPUTFOLDER : Folder where to write the downloaded sitelogs.

OPTION :

* -d : delete : Delete old sitelogs in storage folder. This allows to have only
                the last version, as version changing sitelogs changes of name.

* -m : move : Move old sitelogs into the given archive folder

* -o : observatory : IPGP's observatory ID that will be used to filter
                     sitelogs to download. Valid values are : OVSM|OVSG|OVPF|REVOSIMA.

* -r : root folder : per default, an observatory-specific folder is created
                     to store the corresponding sitelogs.
                     This option stores them in OUTPUTFOLDER's root

* -s : svn : a mode to maintain the legacy OVS's SVN folders.
             download the sitelog of a single obs and perform a 'svn commit'
             a single observatory must be given with -o option.
             the root folder option is automatically activated (-r)

* -f : force : Force download even if an identical sitelog already exists locally

* -e : exclude : Site(s) you want to exclude from download.
                 Provide as input 4 or 9 character site codes separated with spaces

EXAMPLE:

./get_m3g_sitelogs.py OUTPUTFOLDER (-d) (-o OVSM|OVSG|OVPF|REVOSIMA) (-r) (-s)

2021-10-18 FL
2023-03-21 PS
"""

import rinexmod.get_m3g


def main():
    import argparse

    # Parsing Args
    parser = argparse.ArgumentParser(
        description="Get the last versions of the IPGP sitelogs sorted on the M3G Database"
    )
    parser.add_argument(
        "sitelogsfolder",
        type=str,
        help="Output folder where to store downloaded sitelogs",
    )
    parser.add_argument(
        "-d",
        "--delete",
        help="Delete old sitelogs in the output folder. "
             "This allows to have only the last version, "
             "as version changing sitelogs changes of name.",
        action="store_true",
    )
    parser.add_argument(
        "-m",
        "--move",
        help="Move old sitelogs into the given archive folder",
        type=str,
        default=None,
    )
    parser.add_argument(
        "-o",
        "--observatory",
        nargs="+",
        help="Download sitelogs for some specific IPGP's observatories."
             "Valid values are : OVSM OVSG OVPF REVOSIMA OGA",
        type=str,
        default=None,
    )
    parser.add_argument(
        "-r",
        "--root",
        help="Store the sitelogs in OUTPUTFOLDER root."
             "(per default, an observatory-specific folder is"
             "created to store the corresponding sitelogs.)",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "-s",
        "--svn",
        help="A mode to maintain the legacy OVS SVN folder."
             "Download the sitelog of a single obs and perform a svn commit."
             "A single observatory must be given with -o option."
             "The root folder option is automatically activated (-r)",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "-f",
        "--force",
        help="Force download even if an identical sitelog already exists locally",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "-e",
        "--exclude",
        help="Site(s) you want to exclude from download. "
             "Provide as input 4 or 9 character site codes separated with spaces",
        nargs="+",
        default=[],
    )

    args = parser.parse_args()

    rinexmod.get_m3g.get_m3g_sitelogs(
        sitelogsfolder=args.sitelogsfolder,
        delete=args.delete,
        observatory=args.observatory,
        root_folder=args.root,
        svn_mode=args.svn,
        move_folder=args.move,
        force=args.force,
        exclude=args.exclude,
    )


if __name__ == "__main__":
    main()
