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

import requests
import subprocess
import hashlib
import os, glob
import shutil
import sys

def get_m3g_sitelogs(
    sitelogsfolder,
    delete=False,
    observatory=None,
    root_folder=False,
    svn_mode=False,
    move_folder=None,
    force=False,
    exclude=[],
    geodesyml=False,
):
    """
    Downloads the latest version of sitelogs from the M3G repository and writes them
    to an observatory-dependent subfolder set in 'observatories'.

    Parameters
    ----------
    sitelogsfolder : str
        The folder where the downloaded sitelogs will be stored.
    delete : bool
        If True, deletes old sitelogs in the storage folder to keep only the latest version.
    observatory : str or list of str, optional
        IPGP's observatories IDs to filter sitelogs to download.
        Valid values are: OVSM, OVSG, OVPF, REVOSIMA, OGA.
        Default is None.
    root_folder : bool, optional
        If True, stores sitelogs in the root of OUTPUTFOLDER. Default is False.
    svn_mode : bool, optional
        If True, maintains the legacy OVS's SVN folders,
        downloads the sitelog of a single observatory, and performs an 'svn commit'.
        Default is False.
    move_folder : str, optional
        The folder where old sitelogs will be moved. Default is None.
    force : bool, optional
        If True, forces download even if an identical sitelog already exists locally.
        Default is False.
    exclude : list, optional
        List of site codes (4 or 9 characters) to exclude from download.
        Default is an empty list.
    geodesyml : bool, optional
        If True, downloads GeodesyML files instead of sitelogs.

    Returns
    -------
    None
    """
    # the root folder option is automatically activated for the SVN mode
    if svn_mode:
        root_folder = True

    # a single observatory must be given for the SVN mode
    if svn_mode and not observatory:
        sys.exit(
            "when using SVN mode (-s), a single observatory must be given with -o option"
        )

    if not isinstance(observatory,list):
        observatory = [observatory]

    # M3G country webservice. We use countries to filter IPGP's obs stations.
    country_url = "https://gnss-metadata.eu/v1/sitelog/metadata-list?country="
    country_url = "https://gnss-metadata.eu/v1/sitelog/metadata-list?network="

    # # Observatories. First field is the counrty code in M3G's webservice.
    # # Second field is the name of the observatory and is used to build the subfolder
    # observatories = {
    #     "MTQ": "OVSM",
    #     "GLP": "OVSG",
    #     "BLM": "OVSG",  ### St Barthelemy
    #     "MAF": "OVSG",  ### St Martin (no station there for the moment)
    #     "REU": "OVPF",
    #     "MYT": "REVOSIMA",
    #     "ATF": "REVOSIMA",
    #     "DJI": "OGA",
    # }  ### TAAF aka Terres Australes

    # (No more country but network 2025-03)
    net_obs_dic_all = {
        "MQ": "OVSM",
        "GL": "OVSG",
        "PF": "OVPF",
        "QM": "REVOSIMA",
        "DJ": "OGA",
    }

    # If observatory names are given, only download its/their sitelogs
    if observatory and not (len(observatory) == 1 and not observatory[0]):
        net_obs_dic = {
            net_key: obs_val
            for net_key, obs_val in net_obs_dic_all.items()
            if obs_val in observatory
        }
    else:
        net_obs_dic = net_obs_dic_all

    ## complex for and ifs structure (2025-04)
    # if not (len(observatory) == 1 and not observatory[0]):
    #     for obs in observatory:
    #         if obs in net_obs_dic.values():
    #             net_obs_dic_cln = dict()
    #             for net_key, obs_val in net_obs_dic.items():
    #                 if obs_val in obs:
    #                     net_obs_dic_cln[net_key] = obs_val
    #
    #             net_obs_dic = net_obs_dic_cln

    ## simple way to filter observatories if observatories is bijective
    ## not the case anymore because ATF, BLM ... (2022-10)
    # net_key = list(observatories.keys())[list(observatories.values()).index(obs)]
    # observatories = {net_key: observatories[net_key]}

    # Check that output folder exists
    if not os.path.exists(sitelogsfolder):
        print("# ERROR : The output folder for sitelogs doesn't exist")
        return

    if move_folder and not os.path.exists(move_folder):
        print("# ERROR : The archive folder for old sitelogs doesn't exist")
        return

    # Check that obs' subfolder exists. If not, creates.
    for obs in [*net_obs_dic.values()]:
        if not root_folder:
            obs_path = os.path.join(sitelogsfolder, obs)
        else:
            obs_path = sitelogsfolder

        if not os.path.exists(obs_path):
            os.mkdir(obs_path)

    file_local_paths = []

    for net in net_obs_dic.keys():

        obs_url = country_url + net

        obs_infos = requests.get(obs_url)
        obs_infos = obs_infos.content.decode("utf-8")
        obs_infos = obs_infos.splitlines()
        obs_infos = obs_infos[1:]  # remove header
        obs_infos = list(reversed(obs_infos))  # list is reversed per def.

        if not root_folder:
            obs_path = os.path.join(sitelogsfolder, net_obs_dic[net])
        else:
            obs_path = sitelogsfolder

        print(
            "###### Downloading {} ({}) sitelogs from M3G to {}".format(
                net_obs_dic[net], net, obs_path
            )
        )

        for line in obs_infos:
            line = line.split()

            # station_name = line[0]

            # If station is declared in M3G but sitelog not available yet
            if len(line) < 6:
                print("### " + line[0] + " : not available ###")
                continue

            sitelog_md5 = line[1]
            sitelog_url = line[5]
            sitelog_name = line[2]
            geodesyml_url = line[6]
            geodesyml_name = line[3]

            if geodesyml:
                file_name = geodesyml_name
                file_url = geodesyml_url
            else:
                file_name = sitelog_name
                file_url = sitelog_url

            file_local_path = os.path.join(obs_path, file_name)
            file_local_paths.append(file_local_path)

            ### skip excluded stations
            exclude = [e.lower() for e in exclude]
            if file_name[:4] in exclude or file_name[:9] in exclude:
                print("### " + file_name + " skip (excluded) ###")
                continue

            ### get the checksum for the existing sitelog, if any
            if os.path.exists(file_local_path):
                local_file = open(file_local_path, "rb")
                local_md5 = hashlib.md5(local_file.read()).hexdigest()
            else:
                local_md5 = None

            if force or (local_md5 != sitelog_md5):
                print("### " + file_name + " download ###")
                ##Dowload the sitelog
                r = requests.get(file_url, allow_redirects=True)
                # print(r.status_code)
                content = r.content  # .rstrip()
                open(file_local_path, "wb").write(content)
                # subprocess.call(['wget',
                #                  '--no-check-certificate',
                #                  file_url,'-q',
                #                  '-O', file_local_path])

            else:
                print("### " + file_name + " skip (already exists) ###")

            ### get existing old sitelogs for moving or delete
            if move_folder or delete:
                old_sitelogs_mv = glob.glob(f"{obs_path}/*{file_name[:9]}*.log")
                for f in old_sitelogs_mv:
                    if f == file_local_path:
                        # f is the new sitelog
                        continue
                    elif move_folder:
                        print(f"### {os.path.basename(f)} moved to archive folder ###")
                        shutil.move(f, move_folder)
                    elif delete:
                        print(f"### {os.path.basename(f)} deleted ###")
                        os.remove(f)

    if svn_mode:
        print("### SVN add/commit of the downloaded sitelogs")
        for sitelog_local in file_local_paths:
            subprocess.call(["svn", "add", sitelog_local])
        subprocess.call(
            ["svn", "commit", "-m", "get_m3g_sitelogs auto commit", sitelogsfolder]
        )

    # # Other tecnhique using node webservice that will send back less information
    # # about the sitelogs but will filter with the node ID, and will return all
    # # sitelogs belonging to IPGP node
    #
    # node_url = "https://gnss-metadata.eu/v1/node/view?id="
    # node_id = '5e4d07d9468524145a7cf0f2' # IPGP
    #
    # file_url = "https://gnss-metadata.eu/v1/sitelog/exportlog?id="
    #
    # # Getting station list related to IPGP node
    # node_url = node_url + node_id
    #
    # node_infos = requests.get(node_url)
    # node_infos = node_infos.content.decode('utf-8')
    # node_infos = json.loads(node_infos)
    #
    # station_list = node_infos['stations']
    #
    # for station in station_list:
    #
    #     output = os.path.join(sitelogsfolder, observatories[station[-3:]], station.lower() + '.log')


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

    parser.add_argument(
        "-g",
        "--geodesyml",
        help="Download GeodesyML files instead of sitelogs",
        action="store_true",
        default=False,
    )

    args = parser.parse_args()

    get_m3g_sitelogs(
        sitelogsfolder=args.sitelogsfolder,
        delete=args.delete,
        observatory=args.observatory,
        root_folder=args.root,
        svn_mode=args.svn,
        move_folder=args.move,
        force=args.force,
        exclude=args.exclude,
        geodesyml=args.geodesyml,
    )


if __name__ == "__main__":
    main()
