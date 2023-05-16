#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Mar  5 11:57:01 2023

@author: psakicki
"""

#### Import star style
# from geodezyx import *                   # Import the GeodeZYX modules
# from geodezyx.externlib import *         # Import the external modules
# from geodezyx.megalib.megalib import *   # Import the legacy modules names


import rinexmod_api as rma
import glob

filepath = "/home/psakicki/aaa_FOURBI/convertertest/"
file="/home/psakicki/aaa_FOURBI/convertertest/BULG______202110270000A.21o"
file="/home/psakicki/aaa_FOURBI/convertertest/LEN0______202110270000A.21o"
file="/home/psakicki/aaa_FOURBI/convertertest/ABD0______202110270000A.23o"
outputfolder="/home/psakicki/aaa_FOURBI/convertertest/converted/rinexmoded"

psitelog="/home/psakicki/GFZ_WORK/IPGP_WORK/OVS/GNSS_OVS/0030_sites_manage_n_M3G/0020_sitelogs/030_sitelogs_M3G/2205_automatic_download"
sitelogs_obj_list = rma.sitelog_files2objs_convert(psitelog)


for s in sitelogs_obj_list:
    print(s.rinex_full_history_lines())

# [sl.site4char for sl in sitelogs_obj_list]

# rmm.rinexmod(file,
#              outputfolder,
#              sitelog=sitelogs_obj_list,
#              force_rnx_load=True)


#FILES = sorted(glob.glob(filepath + '*rnx*'))
FILES = sorted(glob.glob(filepath + '*o'))

for file in FILES:
    try:
        rma.rinexmod(file,
                     outputfolder,
                     sitelog=sitelogs_obj_list,
                     force_rnx_load=True,
                     longname=True,
                     verbose=False,
                     compression="gz",
                     full_history=True)
    except:
        continue