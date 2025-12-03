#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on 26/06/2025 18:26:58

@author: psakic
"""

import argparse
import multiprocessing as mp
import os
import re
import subprocess
from datetime import datetime
import hatanaka
import pandas as pd

import rinexmod.api as rimo_api
import rinexmod.api.core_fcts as rimo_cor
import rinexmod.api.rinexmod_main as rimo_main

import rinexmod.logger as rimo_log
logger = rimo_log.logger_define("INFO")

# *****************************************************************************
# Upper level rinexmod for a Console run


def rinexmod_cli(
    rinexinput,
    outputfolder,
    sitelog=None,
    modif_kw=dict(),
    marker="",
    country="",
    longname=False,
    shortname=False,
    force_sitelog=False,
    force_rnx_load=False,
    ignore=False,
    ninecharfile=None,
    no_hatanaka=False,
    compression="gz",
    relative="",
    verbose=True,
    alone=False,
    output_logs=None,
    write=False,
    sort=False,
    full_history=False,
    filename_style="basic",
    multi_process=1,
    debug=False,
    station_info=None,
    lfile_apriori=None,
    force_fake_coords=False,
    remove=False,
    keep_rnx_rec=False,
    round_instru_dates=False,
):
    """
    Main function for reading a Rinex list file. It processes the list, and apply
    file name modification, command line based header modification, or sitelog-based
    header modification.

    Optimized for a CLI (in a Terminal usage) but can be used also in a
    stand-alone API mode.

    For a detailed description, check the help of the lower level
    `rinexmod` function or the help of the frontend CLI function in a Terminal
    """

    # If no longname, modif_kw and sitelog, return
    if (
        not sitelog
        and not modif_kw
        and not marker
        and not longname
        and not shortname
        and not station_info
        and not lfile_apriori
    ):
        logger.critical(
            "No action asked, provide at least one of the following args:"
            "--sitelog, --modif_kw, --marker, --longname, --shortname, --station_info, --lfile_apriori"
        )
        return None

    # If force option provided, check if sitelog option too, if not, not relevant.
    if force_sitelog and not sitelog:
        logger.critical(
            "--force option is relevant only when --sitelog option with a **single** sitelog is also provided"
        )
        return None

    # If ignore option provided, check if sitelog option too, if not, not relevant.
    if ignore and not sitelog:
        logger.critical(
            "--ignore option is relevant only when using also --sitelog option"
        )
        return None

    if ninecharfile and not longname:
        logger.critical(
            "--ninecharfile option is relevant only when using also --longname option"
        )
        return None

    if (station_info and not lfile_apriori) or (not station_info and lfile_apriori):
        logger.critical("--station_info and --lfile_apriori must be provided together")
        return None

    if station_info and lfile_apriori and sitelog:
        logger.critical(
            "both sitelogs and GAMIT files given as metadata input. Managing both is not implemented yet"
        )
        return None

    # If inputfile doesn't exists, return
    if len(rinexinput) == 1 and not os.path.isfile(rinexinput[0]):
        logger.critical("The input file doesn't exist: %s", rinexinput)
        return None

    if len(rinexinput) > 1 and alone:
        logger.critical("several inputs are given while -a/--alone option is set")
        return None

    if output_logs and not os.path.isdir(output_logs):
        logger.critical(
            "The specified output folder for logs doesn't exist : " + output_logs
        )
        return None

    outputfolder = os.path.abspath(outputfolder)
    if not os.path.isdir(outputfolder):
        # mkdirs ???
        os.makedirs(outputfolder)

    # Creating log file
    now = datetime.now()
    nowstr = datetime.strftime(now, "%Y%m%d%H%M%S")

    if output_logs:
        logfolder = output_logs
    else:
        logfolder = outputfolder

    logfile = os.path.join(logfolder, nowstr + "_" + "rinexmod_errors.log")
    if verbose:
        _ = rimo_log.logger_define("DEBUG", logfile, "DEBUG")
    else:
        _ = rimo_log.logger_define("INFO", logfile, "INFO")

    ### the refactor of 2024-03 make this obsolete
    ## now rinexinput is ALWAYS a list
    # if isinstance(rinexinput, list):
    #     pass
    # elif alone:
    #     rinexinput = [rinexinput]
    ### the refactor of 2024-03 make this obsolete

    # Opening and reading lines of the file containing list of rinex to proceed
    if len(rinexinput) == 1 and not alone:
        try:
            rinexinput_use = [line.strip() for line in open(rinexinput[0]).readlines()]
        except:
            errmsg = f"Something went wrong while reading: {str(rinexinput[0])}"
            logger.error(errmsg)
            logger.error("Did you forget -a/--alone option?")
            return rimo_cor.RinexModInputArgsError(errmsg)
    else:
        rinexinput_use = rinexinput

    if not rinexinput_use:
        errmsg = f"The input file is empty: {str(rinexinput)}"
        logger.error(errmsg)
        return rimo_cor.RinexModInputArgsError(errmsg)

    if rinexinput_use[0].endswith("RINEX VERSION / TYPE"):
        errmsg = f"The input file is not a file list but a RINEX: {str(rinexinput[0])}"
        logger.error(errmsg)
        logger.error("Did you forget -a/--alone option?")
        return rimo_cor.RinexModInputArgsError(errmsg)

    # sort the RINEX list
    if sort:
        rinexinput_use.sort()

    ### load the sitelogs/GAMIT-files as a **list of MetaData objects**
    # from sitelogs
    if sitelog:
        sitelogs_list_use = rimo_cor.metadata_input_manage(sitelog, force_sitelog)
    # from GAMIT files
    elif station_info and lfile_apriori:
        sitelogs_list_use = rimo_cor.gamit2mda_objs(
            station_info, lfile_apriori, force_fake_coords=force_fake_coords
        )
    else:
        sitelogs_list_use = None

    ### Looping in file list ###
    return_lists = dict()
    ####### Iterate over each RINEX
    rnxmod_kwargs_lis = []
    for rnx in rinexinput_use:
        rnxmod_kwargs = {
            "rinexfile": rnx,
            "outputfolder": outputfolder,
            "sitelog": sitelogs_list_use,
            "modif_kw": modif_kw,
            "marker": marker,
            "country": country,
            "longname": longname,
            "shortname": shortname,
            "force_rnx_load": force_rnx_load,
            "force_sitelog": force_sitelog,
            "ignore": ignore,
            "ninecharfile": ninecharfile,
            "no_hatanaka": no_hatanaka,
            "compression": compression,
            "relative": relative,
            "verbose": verbose,
            "return_lists": return_lists,
            "full_history": full_history,
            "filename_style": filename_style,
            "station_info": station_info,
            "lfile_apriori": lfile_apriori,
            "force_fake_coords": force_fake_coords,
            "remove": remove,
            "keep_rnx_rec": keep_rnx_rec,
            "round_instru_dates": round_instru_dates,
        }

        rnxmod_kwargs_lis.append(rnxmod_kwargs)

    global rinexmod_mpwrap

    def rinexmod_mpwrap(rnxmod_kwargs_inp):
        try:
            return_lists_out = rimo_main.rinexmod(**rnxmod_kwargs_inp)
            return return_lists_out
        except Exception as e:
            if debug:  ### set as True for debug mode
                raise e
            else:
                logger.error(
                    "%s raised, RINEX is skiped: %s. Use -d/--debug option for more details",
                    type(e).__name__,
                    rnxmod_kwargs_inp["rinexfile"],
                )
                return None

    # number of parallel processing
    if multi_process > 1:
        logger.info("multiprocessing: %d cores used", multi_process)
    pool = mp.Pool(processes=multi_process)
    res_raw = [pool.apply_async(rinexmod_mpwrap, args=(x,)) for x in rnxmod_kwargs_lis]
    results = [e.get() for e in res_raw]

    for return_lists_mono in results:
        try:
            rimo_cor.rtun_lsts_make(return_lists_mono, return_lists)
        except rimo_cor.ReturnListError:
            logger.warning(
                "one file has been skipped because of an odd individual return list"
            )
            continue

    #########################################
    logger.handlers.clear()

    if write:
        rimo_cor.rtun_lsts_write(return_lists, logfolder, now)

    return return_lists


##### Class for --modif_kw
class ParseKwargs(argparse.Action):
    # source:
    # https://sumit-ghosh.com/posts/parsing-dictionary-key-value-pairs-kwargs-argparse-python/
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, dict())
        icmt = 0
        for value in values:
            try:
                key, value = value.split("=")

                if key == "comment":
                    getattr(namespace, self.dest)[key + "_" + str(icmt)] = value
                    icmt += 1
                else:
                    getattr(namespace, self.dest)[key] = value

            except Exception as e:

                def _print_kw_tips(values_inp):
                    logger.critical("********************************************")
                    logger.critical("TIP1: be sure you have respected the syntax:")
                    logger.critical("      -k keyword1='value1' keyword2='value2'")
                    logger.critical("********************************************")
                    logger.critical(values_inp)
                    return None

                _print_kw_tips(values)
                raise e


# *****************************************************************************
