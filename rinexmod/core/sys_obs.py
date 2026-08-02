import rinexmod.logger as rimo_log
logger = rimo_log.logger_define("INFO")

def map_sys_obs(sys_obs_dic, map_sys_obs_dic, force=False):
    """
    Maps GNSS observation codes to standardized codes based on a provided mapping dictionary.

    This function processes a dictionary of GNSS satellite system observation codes and applies
    a mapping to standardize them according to receiver-specific conventions. It attempts to map
    observation codes either directly or by their frequency band number.

    Parameters
    ----------
    sys_obs_dic : dict
        Dictionary of GNSS satellite systems and their observation codes.
        Structure: {system: [obs_codes]}
        where system is a single character (e.g., "G", "E", "R", "S") and
        obs_codes are strings representing observation types (e.g., "C1C", "L1", "L2W").

    map_sys_obs_dic : dict
        Mapping dictionary for observation codes.
        Structure: {system: {band_or_obs: mapped_code}}
        where band_or_obs can be either an integer (frequency band) or a string (observation code),
        and mapped_code is the standardized observation code to use.

    force : bool, optional
        If True, forces mapping even for 3-character observation codes that normally would be skipped.
        Default is False.

    Returns
    -------
    sys_obs_dic_new : dict
        A new dictionary with the same structure as sys_obs_dic, containing mapped observation codes.
        Structure: {system: [mapped_obs_codes]}

    Notes
    -----
    sys_obs_dic_new will be used by RinexFile.mod_sys_obs_types()
    map_sys_obs_dic_default function provides a default mapping dictionary for specific receiver types.

    Exemple
    -------
    For Septentrio POLARX5 receiver, the mapping dictionary could be:
            map_sys_obs_dic = {"E": {1: "C", 5 : "Q", 6: "B", 7 : "Q", 8: "Q"},
                               "S": {5: "I", 1: "C"},
                               "G": {5: "Q", "L1": "L1C", "L2" : "L2W"},
                               "R": {5: "Q", 1: "C", "L1" : "L1C", "L2" : "L2P"}
                               }
    """

    sys_obs_dic_new = dict()

    for sys in sys_obs_dic.keys():
        if sys not in map_sys_obs_dic.keys():
            logger.warning(
                f"Sys {sys} not in mapping dict. Keeping original obs for this sys."
            )
            sys_obs_dic_new[sys] = sys_obs_dic[sys]
            continue

        sys_obs_dic_new[sys] = []

        for obs in sys_obs_dic[sys]:
            typ = obs[0]
            ban = int(obs[1])
            cha = obs[2] if len(obs) == 3 else " "

            if len(obs) == 3 and not force:
                logger.debug(
                    f"sys {sys} obs {obs} has 3 characters. Skipping mapping for this obs. (use force to override)"
                )
                sys_obs_dic_new[sys].append(obs)
                continue

            if obs in map_sys_obs_dic[sys].keys():
                obs_new = map_sys_obs_dic[sys][obs]
                logger.debug(f"Mapping sys {sys} obs {obs} to {obs_new}.")
                sys_obs_dic_new[sys].append(obs_new)
            elif ban in map_sys_obs_dic[sys].keys():
                obs_new = typ + str(ban) + map_sys_obs_dic[sys][ban][-1]
                logger.debug(
                    f"Mapping sys {sys} obs {obs} to {obs_new} based on band {ban}."
                )
                sys_obs_dic_new[sys].append(obs_new)
            else:
                logger.debug(f"No mapping for sys {sys} obs {obs}. Keeping original.")
                sys_obs_dic_new[sys].append(obs)

    return sys_obs_dic_new


def map_sys_obs_dic_default(rec="SEPT POLARX5"):
    """
    Returns a default mapping dictionary for GNSS observation codes based on receiver type.

    This function provides a predefined mapping for GNSS satellite system observation codes
    to standardize observable codes for specific receiver types. The mapping is used to convert
    receiver-specific observation codes to standardized RINEX 3 observation codes.

    Parameters
    ----------
    rec : str, optional
        Receiver type identifier. Default is 'SEPT POLARX5'.
        Currently only 'SEPT POLARX5' is supported.

    Returns
    -------
    dict
        A nested dictionary mapping GNSS satellite systems to observation code mappings.
        Structure: {system: {band_or_obs: mapped_code}}

        Keys represent GNSS systems:
        - "E": Galileo
        - "S": SBAS
        - "G": GPS
        - "R": GLONASS

        Values are dictionaries mapping band numbers or observation codes to their
        standardized counterparts (e.g., band 1 -> "C", "L1" -> "L1C").

    Raises
    ------
    NotImplementedError
    """
    if rec == "SEPT POLARX5":
        map_sys_obs_dic = {
            "E": {1: "C", 5: "Q", 6: "B", 7: "Q", 8: "Q"},
            "S": {5: "I", 1: "C"},
            "G": {5: "Q", "L1": "L1C", "L2": "L2W"},
            "R": {5: "Q", 1: "C", "L1": "L1C", "L2": "L2P"},
        }

    else:
        raise NotImplementedError(f"Mapping for receiver {rec} not implemented.")

    return map_sys_obs_dic
