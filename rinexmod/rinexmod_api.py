#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on 27/06/2025 15:10:30

@author: psakic
"""
import warnings
warnings.warn(
    f"from rinexmod import rinexmod_api is deprecated, use from import rinexmod.api as rimo_api instead.",
    category=DeprecationWarning,
    stacklevel=2,
)


# from rinexmod import rinexmod_api
# from rinexmod import api as rimo_api

from .api import *
