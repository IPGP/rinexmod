#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API functions of RinexMod

Created on Wed Mar  8 12:14:54 2023

@author: psakic
"""

import os
import re
import subprocess
import string
import pandas as pd
from datetime import datetime, timedelta


import rinexmod as rimo
import rinexmod.readers.gamit as rimo_gmm
import rinexmod.readers.rinexmod_info as rimo_rmo
import rinexmod.classes.metadata as rimo_mda
import rinexmod.classes.rinexfile as rimo_rnx


import rinexmod.logger as rimo_log
logger = rimo_log.logger_define("INFO")

# *****************************************************************************
# core functions

# get Git hash (to get a version number-equivalent of the RinexMod used)



