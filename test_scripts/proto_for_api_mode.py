#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Oct  3 14:58:53 2023

@author: psakicki
"""

import rinexfile

p="<..>/REYK00ISL_R_20200420000_01D_30S_MO.crx"

R = rinexfile.RinexFile(p)

#### get the systems/observables values from the  ``SYS / # / OBS TYPES`` lines
R.get_sys_obs_types()

R.write_to_path()

d = {"G":["L1C","L2C"]}
R.mod_sys_obs_types(d)


