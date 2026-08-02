import os
import re
import string
from datetime import datetime, timedelta
import subprocess


import rinexmod.logger as rimo_log
logger = rimo_log.logger_define("INFO")

# *****************************************************************************
# low level functions originaly from RinexFile class
def search_idx_val(data, field):
    """
    find the index (line number) of a researched field in the RINEX data
    return None if nothing has beeen found
    """
    idx = -1
    out_idx = None
    for e in data:
        idx += 1
        if field in e:
            out_idx = idx
            break
    return out_idx


def slice_list(seq, num):
    """make sublist of num elts of a list"""
    # http://stackoverflow.com/questions/4501636/creating-sublists
    return [seq[i : i + num] for i in range(0, len(seq), num)]


def round_time(dt=None, date_delta=timedelta(minutes=60), to="average"):
    """
    Round a datetime object to a multiple of a timedelta
    dt : datetime.datetime object, default now.
    dateDelta : timedelta object, we round to a multiple of this, default 1 minute.
    to : up / down / average
    from:  http://stackoverflow.com/questions/3463930/how-to-round-the-minute-of-a-datetime-object-python
    """
    round_to = date_delta.total_seconds()
    if dt is None:
        dt = datetime.now()
    seconds = (dt - dt.min).seconds

    if seconds % round_to == 0 and dt.microsecond == 0:
        rounding = (seconds + round_to / 2) // round_to * round_to
    else:
        if to == "up":
            # // is a floor division, not a comment on following line (like in javascript):
            rounding = (
                (seconds + dt.microsecond / 1000000 + round_to) // round_to * round_to
            )
        elif to == "down":
            rounding = seconds // round_to * round_to
        else:
            rounding = (seconds + round_to / 2) // round_to * round_to

    return dt + timedelta(0, rounding - seconds, -dt.microsecond)


def regex_pattern_rinex_filename():
    """
    return a dictionnary with the different REGEX patterns to describe a RIENX filename
    """
    pattern_dic = dict()
    # pattern_dic["shortname"] = "....[0-9]{3}(\d|\D)\.[0-9]{2}(o|d)(|\.(Z|gz))"
    pattern_dic["shortname"] = (
        r"....[0-9]{3}(\d|\D)([0-9]{2}\.|\.)[0-9]{2}(o|d)(|\.(Z|gz))"  ### add subhour starting min
    )
    pattern_dic["longname"] = (
        r".{4}[0-9]{2}.{3}_(R|S|U)_[0-9]{11}_([0-9]{2}\w)_[0-9]{2}\w_\w{2}\.\w{3}(\.gz|)"
    )
    pattern_dic["longname_gfz"] = (
        r".{4}[0-9]{2}.{3}_[0-9]{8}_.{3}_.{3}_.{2}_[0-9]{8}_[0-9]{6}_[0-9]{2}\w_[0-9]{2}\w_[A-Z]*\.\w{3}(\.gz)?"
    )

    return pattern_dic


def dates_from_rinex_filename(rnx_inp):
    """
    determine the start epoch, the end epoch and the period of a RINEX
    file based on its name only.
    The RINEX is not readed. This function is much faster but less reliable
    than the RinexFile.start_date and RinexFile.end_date attribute

    return the start epoch and end epoch as datetime
    and the period as timedelta
    """
    pattern_dic = regex_pattern_rinex_filename()

    pattern_shortname = re.compile(pattern_dic["shortname"])
    pattern_longname = re.compile(pattern_dic["longname"])
    pattern_longname_gfz = re.compile(pattern_dic["longname_gfz"])

    rinexname = os.path.basename(rnx_inp)

    def _period_to_timedelta(peri_inp):
        peri_val = int(peri_inp[0:2])
        peri_unit = str(peri_inp[2])

        if peri_unit == "S":
            unit_sec = 1
        elif peri_unit == "M":
            unit_sec = 60
        elif peri_unit == "H":
            unit_sec = 3600
        elif peri_unit == "D":
            unit_sec = 86400
        else:
            logger.warn("odd RINEX period: %s, assume it as 01D", peri_inp)
            unit_sec = 86400

        return timedelta(seconds=peri_val * unit_sec)

    ##### LONG rinex name
    if re.search(pattern_longname, rinexname):
        date_str = rinexname[12:23]  # rinexname.split("_")[2]
        period_str = rinexname[24:27]  # rinexname.split("_")[3]

        yyyy = int(date_str[:4])
        doy = int(date_str[4:7])
        hh = int(date_str[7:9])
        mm = int(date_str[9:11])
        dt_srt = datetime(yyyy, 1, 1) + timedelta(
            days=doy - 1, seconds=hh * 3600 + mm * 60
        )
        period = _period_to_timedelta(period_str)
        dt_end = dt_srt + period

        return dt_srt, dt_end, period

    ##### LONG rinex name -- GFZ's GODC internal name
    elif re.search(pattern_longname_gfz, rinexname):
        date_str = rinexname.split("_")[5]
        time_str = rinexname.split("_")[6]
        period_str = rinexname.split("_")[7]

        yyyy = int(date_str[:4])
        mo = int(date_str[4:6])
        dd = int(date_str[6:8])

        hh = int(time_str[0:2])
        mm = int(time_str[2:4])
        ss = int(time_str[4:6])

        dt_srt = datetime(yyyy, mo, dd, hh, mm, ss)
        period = _period_to_timedelta(period_str)
        dt_end = dt_srt + period

        return dt_srt, dt_end, period

    ##### SHORT rinex name
    elif re.search(pattern_shortname, rinexname):
        alphabet = list(string.ascii_lowercase)

        doy = int(rinexname[4:7])
        yy = int(rinexname[9:11])

        if yy > 80:
            year = yy + 1900
        else:
            year = yy + 2000

        if rinexname[7] in alphabet:
            h = alphabet.index(rinexname[7])
            period = timedelta(seconds=3600)
        else:
            h = 0
            period = timedelta(seconds=86400)

        dt_srt = datetime(year, 1, 1) + timedelta(days=doy - 1, seconds=h * 3600)
        dt_end = dt_srt + period
        return dt_srt, dt_end, period

    else:
        logger.error("%s has not a RINEX name well formatted", rinexname)
        return None, None, None


def file_period_from_timedelta(start_date, end_date):
    """
    return the RINEX file period (01H, 01D, 15M...) based on a
    start and end date

    Parameters
    ----------

    Returns
    -------
    file_period : str
        file period (01H, 01D, 15M...)
    session : bool
        True if the timedelta refers to a session (<01D)
        False otherwise (01D).

    """
    rndtup = lambda x, t: round_time(x, timedelta(minutes=t), "up")
    rndtdown = lambda x, t: round_time(x, timedelta(minutes=t), "down")
    rndtaver = lambda x, t: round_time(x, timedelta(minutes=t), "average")

    # end date minus 1sec is necessary to avoid a side effect for HH:30:00
    end_date_m1s = end_date - timedelta(seconds=1)

    # rounded at the hour
    # maximum and average delta between start and end date
    delta_max = rndtup(end_date, 60) - rndtdown(start_date, 60)
    delta_ave = rndtaver(end_date_m1s, 60) - rndtaver(start_date, 60)

    hours_ave = int(delta_ave.total_seconds() / 3600)
    delta_sec = (end_date - start_date).total_seconds()

    # first, the special case : N *full* hours
    if delta_max <= timedelta(seconds=86400 - 3600) and hours_ave > 0:  ## = 23h max
        # delta_ave is a more precise delta than delta_max (average)
        file_period = str(hours_ave).zfill(2) + "H"
        session = True
    # more regular cases : 01H, 01D, nnM, or Unknown
    elif delta_max <= timedelta(seconds=3600):
        # Here we consider sub hourly cases
        session = True
        file_period = None
        for m in [5, 10, 15, 20, 30]:
            if (m * 60 - 1) <= delta_sec <= (m * 60 + 1):
                file_period = str(m).zfill(2) + "M"
        if not file_period:
            # NB: this test is useless, it is treated by the previous test
            file_period = "01H"
    elif hours_ave == 0 and delta_max > timedelta(seconds=3600):  # Note 2
        hours_max = int(delta_max.total_seconds() / 3600)
        file_period = str(hours_max).zfill(2) + "H"
        session = True
    elif (
        timedelta(seconds=3600) < delta_max <= timedelta(seconds=86400 + 3600)
    ):  # Note1
        file_period = "01D"
        session = False
    else:
        file_period = "00U"
        session = False
    # Note1: a tolerance of +/- 1 hours is given because old ashtech RINEXs
    #        includes the epoch of the next hour/day
    #        and then the present delta_max value reach 25
    #        it justifies also the necessity of the delta_ave variable

    # Note 2: very rare (but possible) case --' :
    #         very short file, riding in between* two hours ("a cheval sur 2 heures")
    #         met e.g. for "2024-08-13 11:54:00" > "2024-08-13 12:04:00"
    #         then the delta_max is 2H and the delta_ave is 0
    #         and we must introduce hours_max rather than hours_ave

    return file_period, session

def get_git_hash():
    """
    Gives the Git hash to have a tracking of the used version

    Returns
    -------
    7 characters Git hash
    """
    script_path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

    cmd = ["git", "--git-dir", script_path + "/.git", "rev-parse", "--short", "HEAD"]
    try:
        githash = (
            subprocess.check_output(cmd, stderr=subprocess.DEVNULL)
            .decode("ascii")
            .strip()[:7]
        )
    except Exception:
        # logger.warn("unable to get the git commit version")
        githash = "xxxxxxx"

    ####NB: 2msec to run this fuction
    return githash

