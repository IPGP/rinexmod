#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on 26/06/2025 18:24:11

@author: psakic
"""

import os
from datetime import datetime
import hatanaka

import rinexmod as rimo
import rinexmod.common.gamit_meta as rimo_gmm
import rinexmod.classes.metadata as rimo_mda
import rinexmod.classes.rinexfile as rimo_rnx
import rinexmod.api.core_fcts as rimo_cor


import rinexmod.logger as rimo_log
logger = rimo_log.logger_define("INFO")


# *****************************************************************************
# Main function


def rinexmod(
    rinexfile,
    outputfolder,
    sitelog=None,
    modif_kw=dict(),
    marker="",
    country="",
    longname=False,
    shortname=False,
    force_rnx_load=False,
    force_sitelog=False,
    ignore=False,
    ninecharfile=None,
    no_hatanaka=False,
    compression="gz",
    relative="",
    verbose=True,
    full_history=False,
    filename_style="basic",
    return_lists=None,
    station_info=None,
    lfile_apriori=None,
    force_fake_coords=False,
    remove=False,
    keep_rnx_rec=False,
    round_instru_dates=False,
):
    """
    Parameters
    ----------
    rinexfile : str
        Input RINEX file to process.
    outputfolder : str
        Folder where to write the modified RINEX files.
    sitelog : str, list of str, MetaData object, list of MetaData objects, optional
        Get the RINEX header values from a sitelog.
        Possible inputs are:
         * list of string (sitelog file paths),
         * single string (single sitelog file path or directory containing the sitelogs),
         * list of MetaData object
         * single MetaData object
        The function will search for the latest and right sitelog
        corresponding to the site.
        One can force a single sitelog with force_sitelog.
        The default is None.
    modif_kw : dict, optional
        Modification keywords for RINEX's header fields and/or filename.
        Will override the information from the sitelog.
        Acceptable keywords for the header fields:
         * comment
         * marker_name
         * marker_number
         * station (legacy alias for marker_name)
         * receiver_serial
         * receiver_type
         * receiver_fw
         * antenna_serial
         * antenna_type
         * antenna_X_pos
         * antenna_Y_pos
         * antenna_Z_pos
         * antenna_H_delta
         * antenna_E_delta
         * antenna_N_delta
         * operator
         * agency
         * sat_system (M, G, R, E, C...)
         * observables (legacy alias for sat_system)
         * interval
        Acceptable keywords for the filename:
         * filename_file_period (01H, 01D...)
         * filename_data_freq (30S, 01S...)
         * filename_data_source (R, S, U)
        The default is dict().
    marker : str, optional
        A four or nine character site code that will be used to rename
        input files.
        Apply also to the header's MARKER NAME,
        but a custom modification keyword marker_name='XXXX' overrides it
        (modif_kw argument below)
        The default is ''.
    country : str, optional
        A three character string corresponding to the ISO 3166 Country code
        that will be used to rename input files.
        It overrides other country code sources (sitelog, --marker...)
        list of ISO country codes:
        https://en.wikipedia.org/wiki/List_of_ISO_3166_country_codes
        The default is ''.
    longname : bool, optional
        Force RINEX file renaming with long name convention (force gzip compression).
        Mutually exclusive with shortname.
        The default is False.
    shortname : bool, optional
        Force RINEX file renaming with short name convention.
        Mutually exclusive with longname.
        The default is False.
    force_rnx_load : bool, optional
        Force the loading of the input RINEX. Useful if its name is not standard.
        The default is False.
    force_sitelog : bool, optional
        If a single sitelog is provided, force sitelog-based header
        values when RINEX's header and sitelog site name do not correspond.
        If several sitelogs are provided, skip badly-formated sitelogs.
        The default is False.
    ignore : bool, optional
        Ignore firmware changes between instrumentation periods
        when getting header values info from sitelogs. The default is False.
    ninecharfile : str, optional
        Path of a file that contains 9-char. site names from the M3G database.
        The default is None.
    no_hatanaka : bool, optional
        Skip high-level RINEX-specific Hatanaka compression
        (performed per default).
        The default is False.
    compression : str, optional
        Set low-level RINEX file compression.
        acceptable values : 'gz' (recommended to fit IGS standards), 'Z', None.
        The default is 'gz'.
    relative : str, optional
        Reconstruct files relative subfolders.
        You have to indicate the common parent folder,
        that will be replaced with the output folder. The default is ''.
    verbose : bool, optional
        set the level of verbosity
        (False for the INFO level, True for the DEBUG level).
        The default is True.
    full_history : bool, optional
        Add the full history of the station in
        the RINEX's header as comment.
    filename_style : str, optional
        Set the RINEX filename style.
        acceptable values : 'basic' (per default), 'flex', 'exact'.
        * 'basic': a simple mode to apply a strict filename period (01H or 01D),
        being compatible with the IGS conventions.
        e.g.: `FNG000GLP_R_20242220000_01D_30S_MO.crx.gz`
        * 'flex': the filename period is tolerant and corresponds to
        the actual data content, but then can be odd (e.g. 07H, 14H...).
        The filename start time is rounded to the hour.
        e.g.: `FNG000GLP_R_20242221800_06H_30S_MO.crx.gz`
        * 'exact': the  filename start time is strictly the one of the
        first epoch in the RINEX.
        Useful for some specific cases needing splicing.
        e.g.: `FNG000GLP_R_20242221829_06H_30S_MO.crx.gz`
        The default is 'basic'.
    return_lists : dict, optional
        Specific option for file distribution through a GLASS node.
        Store the rinexmoded RINEXs in a dictionary
        to activates it, give a dict as input (an empty one - dict() works)
        The default is None.
    station_info: str, optional
        Path of a GAMIT station.info file to obtain GNSS site
        metadata information (needs also lfile_apriori option)
    lfile_apriori: str, optional
        Path of a GAMIT apriori apr/L-File to obtain GNSS site
        position and DOMES information (needs also station_info option)
    force_fake_coords: bool, optional
        When using GAMIT station.info metadata without apriori coordinates
        in the L-File, gives fake coordinates at (0°,0°) to the site
    remove: bool, optional
        Remove input RINEX file if the output RINEX is correctly written
        The default is False.
    keep_rnx_rec: bool, optional
        Keep the RINEX receiver header record in the output RINEX.
        Metadata from the external source (e.g. sitelogs) will not be modded.
        The default is False.
    round_instru_dates: bool
        If True, instrumentation dates (for receiver & antenna)
        in the metadata (sitelogs...) are rounded to day boundaries.
        The default is False.

    Raises
    ------
    RinexModInputArgsError
        Something is wrong with the input arguments.
    RinexFileError
        Something is wrong with the input RINEX File.

    Returns
    -------
    outputfile : str
        the path of the rinexmoded RINEX

    OR

    return_lists : dict
        a dictionary of rinexmoded RINEXs for GLASS distribution.
    """

    now = datetime.now().astimezone()

    if verbose:
        logger = rimo_log.logger_define("DEBUG", logfile=None, level_logfile="DEBUG")
    else:
        logger = rimo_log.logger_define("INFO", logfile=None, level_logfile="INFO")

    logger.info("# Inp. file: %s", rinexfile)

    if relative:
        if not relative in rinexfile:
            errmsg = "{:110s} - {}".format(
                "The relative subfolder can not be reconstructed for RINEX file",
                rinexfile,
            )
            logger.error(errmsg)
            raise rimo_cor.RinexModInputArgsError(errmsg)

        # We construct the output path with relative path between file name and parameter
        relpath = os.path.relpath(os.path.dirname(rinexfile), relative)
        myoutputfolder = os.path.join(outputfolder, relpath)
        if not os.path.isdir(myoutputfolder):
            os.makedirs(myoutputfolder)
    elif os.path.basename(outputfolder) == "INPUT_FOLDER":
        myoutputfolder = os.path.dirname(rinexfile)
    else:
        myoutputfolder = outputfolder

    if not modif_kw:
        modif_kw = dict()

    if (
        os.path.abspath(os.path.dirname(rinexfile)) == myoutputfolder
        and not outputfolder == "IDEM"
    ):
        errmsg = "{:110s} - {}".format(
            "Input and output folders are the same!", rinexfile
        )
        logger.error(errmsg)
        raise rimo_cor.RinexFileError(errmsg)

    if outputfolder == "IDEM":
        logger.warning("The output folder is forced as the same one as the input one")

    if not os.path.exists(outputfolder):
        logger.debug("The output folder does not exists, creating it")
        os.makedirs(outputfolder)

    if longname and shortname:
        errmsg = "longname and shortname are mutually exclusive"
        logger.error(errmsg)
        raise rimo_cor.RinexModInputArgsError(errmsg)

    ###########################################################################
    ########## Open the rinex file as an object
    rnxobj = rimo_rnx.RinexFile(rinexfile, force_rnx_load=force_rnx_load)

    if rnxobj.status:
        errmsg = "{:110s} - {}".format(rnxobj.status, rinexfile)
        logger.error(errmsg)
        raise rimo_cor.RinexFileError(errmsg)

    logger.debug("RINEX Origin Metadata :\n" + rnxobj.get_header()[0])

    # apply tolerant / strict (per default) file period
    if filename_style == "basic":
        rnxobj.mod_file_period_basic()

    # Check that the provided marker is a 4-char site name
    if marker and (len(marker) != 4 and len(marker) != 9):
        errmsg = "The site name provided is not 4 or 9-char valid: " + marker
        logger.error(errmsg)
        raise rimo_cor.RinexModInputArgsError(errmsg)

    # Get the 4 char > 9 char dictionnary from the input list
    nine_char_dict = dict()  # in any case, nine_char_dict is initialized
    if ninecharfile:
        if not os.path.isfile(ninecharfile):
            errmsg = "The specified 9-chars. list file does not exists: " + ninecharfile
            logger.error(errmsg)
            raise rimo_cor.RinexModInputArgsError(errmsg)

        nine_char_dict = rimo_cor.read_ninecharfile(ninecharfile)

    # set the marker as Rinex site, if any
    # This preliminary set_site is for th research of the right sitelog
    # a second set_site will take place a just after with more details
    if marker:
        # We store the old site name to add a comment in rinex file's header
        ## modif_marker = rnxobj.get_site(True,False) ### Useless...
        rnxobj.set_site(marker)

    ## warning if no metadata at all is not provided
    if not sitelog and not modif_kw and (not station_info or not lfile_apriori):
        logger.warning(
            "No sitelog nor keywords nor station.info+lfile provided. "
            "Per default rec.'s header will remain & no new "
            "metdata will be written!"
        )

    # initialize the metadata object list (to avoid linter warning)
    mdaobjs_lis = []
    ## sitelogs
    if sitelog:
        mdaobjs_lis = rimo_cor.metadata_input_manage(sitelog, force=force_sitelog)
    ## GAMIT files
    # We read the GAMIT files only if no input 'sitelog' variable is given.
    # Indeed, the GAMIT files might have been read outside this function
    # (most likely actually). The already read GAMIT files are then stored
    # in the 'sitelog' variable as a list of MetaData objects

    if (station_info and not lfile_apriori) or (not station_info and lfile_apriori):
        errmsg = "station_info and lfile_apriori must be provided together"
        logger.critical(errmsg)
        raise rimo_cor.RinexModInputArgsError(errmsg)

    ### load the metadata from sitelog or GAMIT files if any
    if (station_info and lfile_apriori) and not sitelog:
        mdaobjs_lis = rimo_cor.gamit2mda_objs(
            station_info, lfile_apriori, force_fake_coords=force_fake_coords
        )

    ### find the right MetaData object corresponding to the RINEX
    if sitelog or (station_info and lfile_apriori):
        mdaobj = rimo_cor.find_mda4site(rnxobj, mdaobjs_lis, force=force_sitelog)
        logger.debug("metadata used: %s", mdaobj)
    else:
        mdaobj = None

    ###########################################################################
    ########## Handle the similar options to set the site code
    ### Priority for the Country source
    # 0) if --country is given it overrides everything,
    #    but at the end of the tests
    # 1) the marker option if 9 char are given
    # 2) the nine_char_dict from the ninecharfile option
    # 3) the MetaData object (most useful actually),
    #    but we maintain a fallback mechanism here if the sitelog is wrong
    # 4) last chance: test if the country code we get from the input 9-char
    #    code is not XXX. If so, we keep it
    # Finally, set default value for the monument & country codes
    #
    rnx_4char = rnxobj.get_site(True, True)
    rnx_9char = rnxobj.get_site(False, False)

    if marker and len(marker) == 9:
        monum = marker[4:6]
        cntry = marker[6:]
    elif ninecharfile:
        if not rnx_4char in nine_char_dict:
            logger.warning(
                "Site's missing in the input 9-char. file: %s", rinexfile
            )
            monum = "00"
            cntry = "XXX"
        else:
            monum = nine_char_dict[rnx_4char].upper()[4:6]
            cntry = nine_char_dict[rnx_4char].upper()[6:]
    elif mdaobj:
        monum = "00"
        cntry = mdaobj.get_country()
    elif rnx_9char[6:] != "XXX":
        monum = rnx_9char[4:6]
        cntry = rnx_9char[6:]
    else:
        monum = "00"
        cntry = "XXX"

    if country:
        if len(country) == 3:
            cntry = country
        else:
            logger.warning(
                "Input country code is not 3 chars. RINEX will not be properly renamed: %s",
                rinexfile,
            )

    if cntry == "XXX":
        logger.warning(
            "Site's country not retrieved. RINEX will not be properly renamed: %s",
            rinexfile,
        )

    rnxobj.set_site(rnx_4char, monum, cntry)

    ###########################################################################
    ########## Remove previous comments
    if mdaobj or modif_kw or (station_info and lfile_apriori):
        rnxobj.clean_rinexmod_comments(clean_history=True)

    ###########################################################################
    ########## Apply the MetaData object on the RinexFile object
    if mdaobj:
        rnxobj = rimo_cor.apply_mda2rnxobj(
            rnxobj, mdaobj,
            ignore=ignore,
            keep_rnx_rec=keep_rnx_rec,
            round_instru_dates=round_instru_dates,
        )
        logger.debug("RINEX Sitelog-Modified Metadata :\n" + rnxobj.get_header()[0])
        modif_source_metadata = mdaobj.filename
    else:
        modif_source_metadata = ""

    ###########################################################################
    ########## Apply the modif_kw dictionnary on the RinexFile object
    if modif_kw:
        # Checking input keyword modification arguments
        rimo_cor.modif_kw_check(modif_kw)

        modif_source_kw = "keywords:" + " ".join(modif_kw.keys())
        rnxobj = rimo_cor.apply_modifkw2rnxobj(rnxobj, modif_kw)
        logger.debug(
            "RINEX Manual Keywords-Modified Metadata:\n" + rnxobj.get_header()[0]
        )
    else:
        modif_source_kw = ""

    ###########################################################################
    ########## Apply the site as the MARKER NAME within the RINEX
    # Must be after apply_mda2rnxobj and apply_modifkw2rnxobj
    # apply only is modif_kw does not overrides it (it is the overwhelming case)
    if "marker_name" not in modif_kw.keys():
        rnxobj.mod_marker(rnxobj.get_site(False, False, True))

    ###########################################################################
    ########## Correct the first and last time obs
    rnxobj.mod_time_obs(rnxobj.start_date, rnxobj.end_date)

    ###########################################################################
    ########## Add comment in the header
    githash = rimo_cor.get_git_hash() # git hash is desactivated
    vers_num = rimo.__version__ # + " " + githash[-3:]
    vers_num = vers_num.replace("beta", "b")
    rnxobj.add_prg_run_date_comment("RinexMod " + vers_num, "METADATA UPDATE")
    if githash != "xxxxxxx":
        rnxobj.add_comment("RinexMod Git commit hash: " + githash)
    rnxobj.add_comment("RinexMod / IPGP-OVS (github.com/IPGP/rinexmod)")
    rnxobj.add_comment(
        "rinexmoded on {}".format(datetime.strftime(now, "%Y-%m-%d %H:%M%z"))
    )
    if mdaobj:
        rnxobj.add_comment("rinexmoded with {}".format(modif_source_metadata))
    if modif_kw:
        rnxobj.add_comment("rinexmoded with {}".format(modif_source_kw))
    # if marker: ##### Useless...
    #    rnxobj.add_comment('filename assigned from {}'.format(modif_marker))

    ###########################################################################
    ########## Write the station history in the header
    if mdaobj and full_history:
        title = ["- - - - - - - - - - - -", "SITE FULL HISTORY"]
        rnxobj.add_comments(title + mdaobj.rinex_full_history_lines())

    ###########################################################################
    ########## Sort the header
    rnxobj.sort_header()

    ###########################################################################
    ########## we regenerate the filenames
    if shortname or (rnxobj.name_conv == "SHORT" and not longname):
        apply_longname = False
    elif longname or (rnxobj.name_conv == "LONG" and not shortname):
        apply_longname = True
    else:
        apply_longname = True

    if apply_longname:
        rnxobj.get_longname(
            inplace_set=True,
            compression="",
            filename_style=filename_style,
            data_source=rnxobj.data_source,
        )
    else:
        rnxobj.get_shortname(
            inplace_set=True, compression="", filename_style=filename_style
        )

    # NB: here the compression type must be forced to ''
    #     it will be added in the next step in write_to_path

    ###########################################################################
    ########## We convert the file back to Hatanaka Compressed Rinex

    # NB: this test is complcated, ambiguous and not very useful => disabled 2025-01-05

    # if apply_longname and not compression:
    #     # If not specified, we set compression to gz when file changed to longname
    #     output_compression = "gz"
    # elif not compression:
    #     output_compression = rnxobj.compression
    # else:
    #     output_compression = compression

    output_compression = compression

    ###########################################################################
    ########## Writing output file
    try:
        outputfile = rnxobj.write_to_path(
            myoutputfolder, compression=output_compression, no_hatanaka=no_hatanaka
        )
        logger.info("# Out. file: " + outputfile)
    except hatanaka.hatanaka.HatanakaException as e:
        errmsg ="{:110s} - {}".format("File could not be written - hatanaka exception", rinexfile)
        logger.error(errmsg)
        outputfile = None
        raise e

    if remove and os.path.isfile(outputfile):
        logger.info("Input file removed: %s", rinexfile)
        os.remove(rinexfile)

    ###########################################################################
    # Construct return dict by adding key if doesn't exists
    # and appending file to corresponding list
    if type(return_lists) is dict:
        return_lists = rimo_cor.rtun_lsts_make(rnxobj, return_lists)
        final_return = return_lists
    else:
        ###########################################################################
        # if no return dict given, return simply the path of the outputfile
        final_return = outputfile

    return final_return
