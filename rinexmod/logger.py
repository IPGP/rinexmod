#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Feb 26 14:45:44 2024

@author: psakic

logger for RinexMod
"""

import logging
import colorlog

# *****************************************************************************
# logger definition


def logger_define(level_prompt, logfile=None, level_logfile=None):
    """
    This function manage logging levels. It has two outputs, one to the prompt,
    the other to a logfile defined by 'logfile'.
    """

    logger_out = colorlog.getLogger('rinexmod')
    logger_out.propagate = True
    logger_out.setLevel(level_prompt)

    # This handler is for prompt (console)
    prompthandler = colorlog.StreamHandler()
    promptformatter = colorlog.ColoredFormatter(
        "%(asctime)s.%(msecs)03d|%(log_color)s%(levelname).1s%(reset)s|%(log_color)s%(funcName)-15s%(reset)s|%(message)s",
        datefmt="%y%m%dT%H:%M:%S",
        log_colors={
            "DEBUG": "cyan",
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "red,bg_white",
        },
    )
    prompthandler.setFormatter(promptformatter)
    prompthandler.setLevel(level_prompt)
    if not len(logger_out.handlers):
        logger_out.addHandler(prompthandler)

    # This handler will write to a log file
    if logfile:
        if not level_logfile:
            level_logfile = level_prompt
        filehandler = logging.FileHandler(logfile, mode="a", encoding="utf-8")
        fileformatter = logging.Formatter(
            "%(asctime)s.%(msecs)03d|%(levelname).1s|%(funcName)-15s|%(message)s",
            datefmt="%y%m%dT%H:%M:%S",
        )
        filehandler.setFormatter(fileformatter)
        filehandler.setLevel(level_logfile)
        logger_out.addHandler(filehandler)

    return logger_out


logger = logger_define("INFO")


def logger_tester():
    logger.debug("debug message")
    logger.info("info message")
    logger.warning("warning message")
    logger.error("error message")
    logger.critical("critical message")
