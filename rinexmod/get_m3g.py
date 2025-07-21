#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on 27/08/2024 20:14:09

@author: psakic
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

    sitelog_local_paths = []

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
            sitelog_local_path = os.path.join(obs_path, sitelog_name)
            sitelog_local_paths.append(sitelog_local_path)

            ### skip excluded stations
            exclude = [e.lower() for e in exclude]
            if sitelog_name[:4] in exclude or sitelog_name[:9] in exclude:
                print("### " + sitelog_name + " skip (excluded) ###")
                continue

            ### get the checksum for the existing sitelog, if any
            if os.path.exists(sitelog_local_path):
                local_file = open(sitelog_local_path, "rb")
                local_md5 = hashlib.md5(local_file.read()).hexdigest()
            else:
                local_md5 = None

            if force or (local_md5 != sitelog_md5):
                print("### " + sitelog_name + " download ###")
                ##Dowload the sitelog
                r = requests.get(sitelog_url, allow_redirects=True)
                # print(r.status_code)
                content = r.content  # .rstrip()
                open(sitelog_local_path, "wb").write(content)
                # subprocess.call(['wget',
                #                  '--no-check-certificate',
                #                  sitelog_url,'-q',
                #                  '-O', sitelog_local_path])

            else:
                print("### " + sitelog_name + " skip (already exists) ###")

            ### get existing old sitelogs for moving or delete
            if move_folder or delete:
                old_sitelogs_mv = glob.glob(f"{obs_path}/*{sitelog_name[:9]}*.log")
                for f in old_sitelogs_mv:
                    if f == sitelog_local_path:
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
        for sitelog_local in sitelog_local_paths:
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
    # sitelog_url = "https://gnss-metadata.eu/v1/sitelog/exportlog?id="
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
