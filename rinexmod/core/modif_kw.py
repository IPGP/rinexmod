import re
import rinexmod.logger as rimo_log
import rinexmod.exceptions as rimo_exc
logger = rimo_log.logger_define("INFO")

# *****************************************************************************
# modification keyword dictionary functions

def modif_kw_check(modif_kw):
    """
    Check if acceptable modification keywords have been provided

    Raise a RinexModInputArgsError Exception if not
    """

    acceptable_keywords = [
        "station",
        "marker_name",
        "marker_number",
        "marker_type",
        "receiver_serial",
        "receiver_type",
        "receiver_fw",
        "antenna_serial",
        "antenna_type",
        "antenna_X_pos",
        "antenna_Y_pos",
        "antenna_Z_pos",
        "antenna_H_delta",
        "antenna_E_delta",
        "antenna_N_delta",
        "operator",
        "agency",
        "sat_system",
        "observables",
        "interval",
        "filename_data_freq",
        "filename_file_period",
        "filename_data_source",
        "comment(_[0-9]+)?",
    ]
    ### comment is a regex, bc several comments are possible
    # suffix _N is added by ParseKwargs
    # but comment without suffix must remain possible (for API mode)

    for kw in modif_kw:
        if not any([re.match(akw, kw) for akw in acceptable_keywords]):
            logger.error(
                "'{}' is not an acceptable keyword for header modification.".format(kw)
            )
            return rimo_exc.RinexModInputArgsError

    return None


def apply_modifkw2rnxobj(rnxobj, modif_kw):
    """
    apply a modification keywords on a RinexFile object
    to modify this RinexFile with the rights metadata
    """

    def __keys_in_modif_kw(keys_in):
        return all([e in modif_kw.keys() for e in keys_in])

    rnxobj.mod_marker(modif_kw.get("marker_name"), modif_kw.get("marker_number"))
    rnxobj.mod_marker_type(modif_kw.get("marker_type"))

    # legacy keyword, 'marker_name' should be used instead
    rnxobj.mod_marker(modif_kw.get("station"))

    rnxobj.mod_receiver(
        modif_kw.get("receiver_serial"),
        modif_kw.get("receiver_type"),
        modif_kw.get("receiver_fw"),
    )

    rnxobj.mod_antenna(modif_kw.get("antenna_serial"), modif_kw.get("antenna_type"))

    rnxobj.mod_antenna_pos(
        modif_kw.get("antenna_X_pos"),
        modif_kw.get("antenna_Y_pos"),
        modif_kw.get("antenna_Z_pos"),
    )

    rnxobj.mod_antenna_delta(
        modif_kw.get("antenna_H_delta"),
        modif_kw.get("antenna_E_delta"),
        modif_kw.get("antenna_N_delta"),
    )

    rnxobj.mod_agencies(modif_kw.get("operator"), modif_kw.get("agency"))

    rnxobj.mod_sat_system(modif_kw.get("sat_system"))
    # legacy keyword, 'sat_system' should be used instead
    rnxobj.mod_sat_system(modif_kw.get("observables"))

    rnxobj.mod_interval(modif_kw.get("interval"))

    # for the filename
    rnxobj.mod_filename_file_period(modif_kw.get("filename_file_period"))
    rnxobj.mod_filename_data_freq(modif_kw.get("filename_data_freq"))
    rnxobj.mod_filename_data_source(modif_kw.get("filename_data_source"))

    # comment
    # special case: several keys comment_1, comment_2, comment_N are possible
    # number are added automatically by ParseKwargs
    comment_keys = [k for k in modif_kw.keys() if "comment" in k]
    for ck in comment_keys:
        rnxobj.add_comment(modif_kw.get(ck).split("_")[0])

    return rnxobj
