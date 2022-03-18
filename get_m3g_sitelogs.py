#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import subprocess
import json
import os, glob

"""
This script will get last version of sitelogs from M3G repository and write them
in an observatory dependent subfolder set in 'observatories'.
The -d --delete option will delete old version as to get only last version even
in a name changing case.
2021-10-18 FL
"""

def get_m3g_sitelogs(sitelogsfolder, delete):

    # M3G country webservice. We use countries to filter IPGP's obs stations.
    country_url = 'https://gnss-metadata.eu/v1/sitelog/metadata-list?country='

    # Observatories. First field is the counrty code in M3G's webservice.
    # Second field is the name of the observatory and is used to build the subfolder
    observatories = {'MTQ' : 'OVSM',
                     'GLP' : 'OVSG',
                     'REU' : 'OVPF'}

    # Check that output folder exists
    if not os.path.exists(sitelogsfolder):
        print('# ERROR : : The output folder for log file doesn\'t exist')
        return

    # Check that obs' subfolder exists. If not, creates.
    for obs in [*observatories.values()]:
        obs_path = os.path.join(sitelogsfolder, obs)
        if not os.path.exists(obs_path):
            os.mkdir(obs_path)

    for obs in observatories.keys():

        obs_url = country_url + obs

        obs_infos = requests.get(obs_url)
        obs_infos = obs_infos.content.decode('utf-8')
        obs_infos = obs_infos.splitlines()
        obs_infos = obs_infos[1:] # remove header

        obs_path = os.path.join(sitelogsfolder, observatories[obs])

        # If delete, empty folders
        if delete:
            old_sitelogs = glob.glob(obs_path + '/*log')
            for f in old_sitelogs:
                os.remove(f)

        print("### Downloading {} sitelogs from M3G to {}".format(observatories[obs], obs_path))

        for line in obs_infos:
            line = line.split()

            # station_name = line[0]

            # If station is declared in M3G but sitelog not available yet
            if len(line) < 6:
                print('### ' + line[0] + ' : not available ###')
                continue

            sitelog_url = line[6]
            sitelog_name = line[3]

            print('### ' + sitelog_name + ' ###')

            # Dowload the sitelog
            # r = requests.get(sitelog_url, allow_redirects=True)
            # print(r.status_code)
            # open(os.path.join(obs_path, sitelog_name), 'wb').write(r.content)
            subprocess.call(['wget', '--no-check-certificate', sitelog_url, '-q', '-O', os.path.join(obs_path, sitelog_name)])


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


if __name__ == '__main__':

    import argparse

    # Parsing Args
    parser = argparse.ArgumentParser(description='Get all IPGP sitelogs in the last version for M3G repository')
    parser.add_argument('sitelogsfolder', type=str, help='Output folder where to store downloaded sitelogs')
    parser.add_argument('-d', '--delete', help='Delete old sitelogs in storage folder', action='store_true')

    args = parser.parse_args()
    sitelogsfolder = args.sitelogsfolder
    delete = args.delete

    get_m3g_sitelogs(sitelogsfolder, delete)
