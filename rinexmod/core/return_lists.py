import os
from datetime import datetime
import rinexmod.classes.rinexfile as rimo_rnx

import rinexmod.logger as rimo_log
logger = rimo_log.logger_define("INFO")

# *****************************************************************************
# dictionnary as output for gnss_delivery workflow

def rtun_lsts_make(rnxobj_or_dict, return_lists=dict()):
    """
    Construct the so called ``return_lists`` (which are actually dictionnaries)

    return_lists have the structure:

    ```
    return_lists[major_rinex_version][sample_rate_string][file_period]
    ```

    the input ``return_lists`` is populated with the content of the input
    ``rnxobj_or_dict``

    Parameters
    ----------
    rnxobj_or_dict : RinexFile object or dict

        The input new information which will populate the return_lists

        if a dict is provided, we assume it is a singleton with a standard
        return_lists structure to be merged in a bigger return_lists

    return_lists : dict, optional
        A potential pre-exisiting return_lists.
        Per default it is a brand-new return_lists for scratch.
        The default is dict().

    Returns
    -------
    return_lists : dict
        The input return_lists populated with the input rnxobj_or_dict.

    Note
    ----
    Specific usage for the IPGP's gnss_delivery workflow

    """

    if isinstance(rnxobj_or_dict, rimo_rnx.RinexFile):
        rnxobj = rnxobj_or_dict
        major_rinex_version = rnxobj.version[0]
        sample_rate_string = rnxobj.sample_rate_string
        file_period = rnxobj.file_period
        path_output = rnxobj.path_output
    elif isinstance(rnxobj_or_dict, dict):
        rtrnlst = rnxobj_or_dict
        major_rinex_version = list(rtrnlst.keys())[0]
        sample_rate_string = list(rtrnlst[major_rinex_version].keys())[0]
        file_period = list(rtrnlst[major_rinex_version][sample_rate_string].keys())[0]
        path_output = rtrnlst[major_rinex_version][sample_rate_string][file_period][0]
    else:
        logger.error(
            "Wrong Input, must be RinexFile object or dict. Input given: %s, %s",
            rnxobj_or_dict,
            type(rnxobj_or_dict),
        )
        raise ReturnListError

    # Dict ordered as : RINEX_VERSION, SAMPLE_RATE, FILE_PERIOD
    if major_rinex_version not in return_lists:
        return_lists[major_rinex_version] = {}
    if sample_rate_string not in return_lists[major_rinex_version]:
        return_lists[major_rinex_version][sample_rate_string] = {}
    if file_period not in return_lists[major_rinex_version][sample_rate_string]:
        return_lists[major_rinex_version][sample_rate_string][file_period] = []

    return_lists[major_rinex_version][sample_rate_string][file_period].append(
        path_output
    )

    return return_lists


def rtun_lsts_write(return_lists, logfolder, now_dt=None):
    # Writing an output file for each RINEX_VERSION, SAMPLE_RATE, FILE_PERIOD lists
    if not now_dt:
        now_dt = datetime.now()

    this_outputfile = ""

    for rinex_version in return_lists:
        for sample_rate in return_lists[rinex_version]:
            for file_period in return_lists[rinex_version][sample_rate]:
                this_outputfile = "_".join(
                    [
                        "RINEX" + rinex_version,
                        sample_rate,
                        file_period,
                        datetime.strftime(now_dt, "%Y%m%d%H%M"),
                        "delivery.lst",
                    ]
                )
                this_outputfile = os.path.join(logfolder, this_outputfile)

                # Writting output to temporary file and copying it them to target files
                with open(this_outputfile, "w") as f:
                    f.writelines(
                        "{}\n".format(line)
                        for line in return_lists[rinex_version][sample_rate][
                            file_period
                        ]
                    )
                    logger.debug("Output rinex list written to " + this_outputfile)

    return this_outputfile
