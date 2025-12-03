#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on 27/06/2025 15:10:30

@author: psakic
"""


import warnings
warnings.warn(
    f"from rinexmod import metadata is deprecated, use import rinexmod.classes.metadata instead.",
    category=DeprecationWarning,
    stacklevel=2,
)


from .classes.metadata import *
