#  rinexmod

<img src="./logo_rinexmod.png" width="300">

_rinexmod_ is a tool to batch modify the headers of GNSS data files in RINEX format and rename them correctly.  
It supports Hatanaka-compressed and non-compressed files, RINEX versions 2 and 3/4, and short and long naming conventions.  
It is developed in Python 3, and can be run from the command line or directly in API mode by calling a python function.  
The required input metadata can come from a sitelog file, or be manually entered as arguments to the command line or the called function.  
It is available under the GNU license on the following GitHub repository: https://github.com/IPGP/rinexmod  

v2+ - 2023-05-15 - Pierre Sakic - sakic@ipgp.fr  
v1  - 2022-02-07 - Félix Léger  - leger@ipgp.fr  

Version: 3.7.5
Date: 2025-07-01

**GitHub repository:** [https://github.com/IPGP/rinexmod](https://github.com/IPGP/rinexmod)  
**PyPi project:** [https://pypi.org/project/rinexmod](https://pypi.org/project/rinexmod)

## Tools overview

### Main tool

* `rinexmod_run` takes a list of RINEX Hatanaka compressed files (.d.Z or .d.gz or .rnx.gz),
loops the rinex files list to modify the file's headers. It then writes them back to Hatanaka
compressed format in an output folder. It also permits to rename the files, changing
the four first characters of the file name with another station code. It can write
those files with the long name naming convention with the --longname option.

### Annex tools

They are stored in `bin/misc_tools` folder.

* `get_m3g_sitelogs.py` will get the last version of site logs from the M3G repository
and write them in an observatory-dependent subfolder.

* `crzmeta.py` will extract RINEX file's header information and prompt the result. 
This permits to quickly access the header information without uncompressing the file manually. 
It's a teqc-free equivalent of teqc +meta.

## Installation

### Assisted installation 
The tool is designed in Python 3, and you must have it installed on your machine.  

Since version 3.4.0, the frontend program `rinexmod_run` is available directly when you call it in your console.

#### Install the last *stable* version 
You can use `pip` to install the last stable version from the [Python Package Index (PyPI)](https://pypi.org/project/rinexmod):  
```pip install rinexmod```

#### Install the latest *developpement* version
You can use `pip` to install the latest [GitHub-hosted](https://github.com/IPGP/rinexmod) version:  
```pip install git+https://github.com/IPGP/rinexmod```


### Required external modules

*NB*: Following the assisted installation procedure above, the required external modules will be automatically installed.

You need:
 * _Python_ `hatanaka` library from M. Valgur
 * `pycountry` to associate country names with their ISO abbreviations (facultative but recommended):  
 * `matplotlib` for plotting samples intervals with crzmeta  
 * `colorlog` to get the pretty colored log outputs
 * `pandas` to for internal low-level data management  

You can install them with: 
```
pip install hatanaka pycountry matplotlib colorlog pandas
```

## _rinexmod_ in command lines interface

### rinexmod_run

This is the main frontend function. It takes a list of RINEX Hatanaka compressed files (.d.Z or .d.gz or .rnx.gz),
loop over the RINEX files list to modify the file's header. It then writes them back to Hatanaka-compressed
format in an output folder. It also allows to rename the files, changing
the four first characters of the file name with another site code. It can write
those files with the long name naming convention with the --longname option.

Three ways of passing parameters to modify headers are possible: `sitelog`, `modification_kw` and `station_info`/`lfile_apriori` (from GAMIT/GLOBK software).

* ```
   --sitelog : you pass sitelogs file. The argument must be a sitelog path or the path of a folder
               containing sitelogs. You then have to pass a list of files and the script will
               assign sitelogs to correspondig files, based on the file's name.
               The script will take the start and end time of each proceeded file
               and use them to extract from the sitelog the station instrumentation
               of the corresponding period and fill file's header with following infos:  
                       Four Character ID
                       X coordinate (m)
                       Y coordinate (m)
                       Z coordinate (m)
                       Receiver Type
                       Serial Number
                       Firmware Version
                       Satellite System (will translate this info to one-letter code,
                                         see RinexFile.set_observable_type())
                       Antenna Type
                       Serial Number
                       Marker->ARP Up Ecc. (m)
                       Marker->ARP East Ecc(m)
                       Marker->ARP North Ecc(m)
                       On-Site Agency Preferred Abbreviation
                       Responsible Agency Preferred Abbreviation

* ```
  --modification_kw : you pass as argument the field(s) that you want to modifiy and its value.
                      Acceptable_keywords are:
                              marker_name,
                              marker_number,
                              station (legacy alias for marker_name),
                              receiver_serial,
                              receiver_type,
                              receiver_fw,
                              antenna_serial,
                              antenna_type,
                              antenna_X_pos,
                              antenna_Y_pos,
                              antenna_Z_pos,
                              antenna_H_delta,
                              antenna_E_delta,
                              antenna_N_delta,
                              operator,
                              agency,
                              sat_system, 
                              observables (legacy alias for sat_system),
                              interval,
                              filename_file_period (01H, 01D...),
                              filename_data_freq (30S, 01S...),
                              filename_data_source (R, S, U) 
* ```
  -sti STATION_INFO, --station_info STATION_INFO
                        Path of a GAMIT station.info file to obtain GNSS site
                        metadata information (needs also -lfi option)
  -lfi LFILE_APRIORI, --lfile_apriori LFILE_APRIORI
                        Path of a GAMIT apriori apr/L-File to obtain GNSS site
                        position and DOMES information (needs also -sti
                        option)
`--modification_kw` values will orverride the ones obtained with `--sitelog` and `--station_info`/`--lfile_apriori`.

_rinexmod_ will add two comment lines, one indicating the source of the modification
(sitelog or arguments) and the other the modification timestamp.


### Synopsis
```
rinexmod_run [-h] -i RINEXINPUT [RINEXINPUT ...] -o OUTPUTFOLDER
             [-s SITELOG] [-k KEY=VALUE [KEY=VALUE ...]] [-m MARKER]
             [-co COUNTRY] [-n NINECHARFILE] [-sti STATION_INFO]
             [-lfi LFILE_APRIORI] [-r RELATIVE] [-nh] [-c {gz,Z,none}]
             [-l] [-fs] [-fc] [-fr] [-ig] [-a] [-ol OUTPUT_LOGS] [-w]
             [-v] [-t] [-u] [-fns {basic,flex,exact}]
             [-mp MULTI_PROCESS] [-d] [-rm]

RinexMod takes RINEX files (v2 or v3/4, compressed or not), rename them and modifiy their headers, and write them back to a destination directory

options:
  -h, --help            show this help message and exit

required arguments:
  -i RINEXINPUT [RINEXINPUT ...], --rinexinput RINEXINPUT [RINEXINPUT ...]
                        Input RINEX file(s). It can be: 
                        1) a list file of the RINEX paths to process (generated with find or ls command for instance) 
                        2) several RINEX files paths 
                        3) a single RINEX file path (see -a/--alone for a single input file)
  -o OUTPUTFOLDER, --outputfolder OUTPUTFOLDER
                        Output folder for modified RINEX files

optional arguments:
  -s SITELOG, --sitelog SITELOG
                        Get the RINEX header values from file's site's sitelog. Provide a single sitelog path or a folder contaning sitelogs.
  -k KEY=VALUE [KEY=VALUE ...], --modif_kw KEY=VALUE [KEY=VALUE ...]
                        Modification keywords for RINEX's header fields and/or filename.
                        Format: -k keyword_1='value1' keyword2='value2'.
                        Will override the information from the sitelog.
                        Acceptable keywords: comment, marker_name, marker_number, station (legacy alias for marker_name), receiver_serial, receiver_type, receiver_fw, antenna_serial, antenna_type, antenna_X_pos, antenna_Y_pos, antenna_Z_pos, antenna_H_delta, antenna_E_delta, antenna_N_delta, operator, agency, sat_system, observables (legacy alias for sat_system), interval, filename_file_period (01H, 01D...), filename_data_freq (30S, 01S...), filename_data_source (R, S, U)
  -m MARKER, --marker MARKER
                        A four or nine-character site code that will be used to rename input files.(apply also to the header's MARKER NAME, but a custom -k marker_name='XXXX' overrides it)
  -co COUNTRY, --country COUNTRY
                        A three-character string corresponding to the ISO 3166 Country code that will be used to rename input files. It overrides other country code sources (sitelog, --marker...). List of ISO country codes: https://en.wikipedia.org/wiki/List_of_ISO_3166_country_codes
  -n NINECHARFILE, --ninecharfile NINECHARFILE
                        Path of a file that contains 9-char. site names (e.g. from the M3G database)
  -sti STATION_INFO, --station_info STATION_INFO
                        Path of a GAMIT station.info file to obtain GNSS site metadata information (needs also -lfi option)
  -lfi LFILE_APRIORI, --lfile_apriori LFILE_APRIORI
                        Path of a GAMIT apriori apr/L-File to obtain GNSS site position and DOMES information (needs also -sti option)
  -r RELATIVE, --relative RELATIVE
                        Reconstruct files relative subfolders.You have to indicate the common parent folder, that will be replaced with the output folder
  -nh, --no_hatanaka    Skip high-level RINEX-specific Hatanaka compression (performed per default). See also -c 'none'
  -c {gz,Z,none}, --compression {gz,Z,none}
                        Set low-level RINEX file compression (acceptable values : 'gz' (recommended to fit IGS standards), 'Z', 'none')
  -l, --longname        Rename file using long name RINEX convention (force gzip compression).
  -fs, --force_sitelog  If a single sitelog is provided, force sitelog-based header values when RINEX's header and sitelog site name do not correspond. 
                         If several sitelogs are provided, skip badly-formated sitelogs.
  -fc, --force_fake_coords
                        When using GAMIT station.info metadata without apriori coordinates in the L-File, gives fake coordinates at (0??,0??) to the site
  -fr, --force_rnx_load
                        Force the loading of the input RINEX. Useful if its name is not standard
  -ig, --ignore         Ignore firmware changes between instrumentation periods when getting header values info from sitelogs
  -a, --alone           INPUT is a single/alone RINEX file (and not a list file of RINEX paths)
  -ol OUTPUT_LOGS, --output_logs OUTPUT_LOGS
                        Folder where to write output logs. If not provided, logs will be written to OUTPUTFOLDER
  -w, --write           Write (RINEX version, sample rate, file period) dependant output lists
  -v, --verbose         Print file's metadata before and after modifications.
  -t, --sort            Sort the input RINEX list.
  -u, --full_history    Add the full history of the station in the RINEX's 'header as comment.
  -fns {basic,flex,exact}, --filename_style {basic,flex,exact}
                        Set the RINEX filename style.
                        acceptable values : 'basic' (per default), 'flex', 'exact'.
                        * 'basic': a simple mode to apply a strict filename period (01H or 01D), being compatible with the IGS conventions.
                        e.g.: FNG000GLP_R_20242220000_01D_30S_MO.crx.gz
                        * 'flex': the filename period is tolerant and corresponds tothe actual data content, 
                        but then can be odd (e.g. 07H, 14H...). The filename start time is rounded to the hour.
                        e.g.: FNG000GLP_R_20242221800_06H_30S_MO.crx.gz
                        * 'exact': the filename start time is strictly the one of the first epoch in the RINEX. 
                        Useful for some specific cases needing splicing.
                        e.g.: FNG000GLP_R_20242221829_06H_30S_MO.crx.gz
                        (default: basic)
  -mp MULTI_PROCESS, --multi_process MULTI_PROCESS
                        Number of parallel multiprocesing (default: 1, no parallelization)
  -d, --debug           Debug mode, stops if something goes wrong (default: False)
  -rm, --remove         Remove input RINEX file if the output RINEX is correctly written. Use it as your own risk. (default: False)

RinexMod 3.3.0 - GNU Public Licence v3 - P. Sakic et al. - IPGP-OVS - https://github.com/IPGP/rinexmod
```

### Examples

```
./rinexmod_run -i RINEXLIST -o OUTPUTFOLDER (-k antenna_type='ANT TYPE' antenna_X_pos=9999 agency=AGN) (-m AGAL) (-r ./ROOTFOLDER/) (-f) (-v)
```
```
./rinexmod_run (-a) -i RINEXFILE -o OUTPUTFOLDER (-s ./sitelogsfolder/stationsitelog.log) (-i) (-w) (-o ./LOGFOLDER) (-v)
```

## _rinexmod_ in API mode

_rinexmod_ can be launched directly as a Python function:

```
import rinexmod.rinexmod_api as rimo_api

rimo_api.rinexmod(rinexfile, outputfolder, sitelog=None, modif_kw=dict(), marker='',
             country='', longname=False, force_rnx_load=False, force_sitelog=False,
             ignore=False, ninecharfile=None, no_hatanaka=False, compression=None,
             relative='', verbose=True, full_history=False, filename_style=False,
             return_lists=None, station_info=None, lfile_apriori=None,
             force_fake_coords=False):
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
        Rename file using long name RINEX convention (force gzip compression).
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
        acceptable values : gz (recommended to fit IGS standards), 'Z', None.
        The default is None.
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
        in the L-File, gives fake coordinates at (0??,0??) to the site
    remove: bool, optional
        Remove input RINEX file if the output RINEX is correctly written
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
```
## Other command line functions

### crzmeta

Extract metadata from crz file.

With -p option, will plot the file's samples intervals
```
EXAMPLE:
./crzmeta  RINEXFILE (-p)
```

### get_m3g_sitelogs

This script will get the last version of sitelogs from M3G repository and write them
in an observatory dependent subfolder set in 'observatories'.
The -d --delete option will delete the old version to get only the last version even
in a name-changing case.

```
USE :

* OUTPUTFOLDER : Folder where to write the downloaded sitelogs.

OPTION :

* -d : delete : Delete old sitelogs in storage folder. This permits to have only the last version, as version changing sitelogs changes of name.

EXAMPLE:

	./get_m3g_sitelogs OUTPUTFOLDER (-d)
```

## _rinexmod_ error messages

_rinexmod_ will prompt errors when arguments are wrong. Apart from this, it will prompt and save to file errors and waring
occurring on specific files from the rinex list. Here are the error codes :

`01 - The specified file does not exists`

That means that the input file containing a list of rinex files is wrong and references a file that is not present. It can also mean that the file was deleted between the list generation and the script launch, but this case should be quite rare.

`02 - Not an observation Rinex file`

The file name does not correspond to the classic pattern (it doesn't match the regular expression for new and old convention naming model ). Most of time, it's because it is not a d rinex file (for example, navigation file).

`03 - Invalid  or empty Zip file`

The Zip file is corrupted or empty

`04 - Invalid Compressed Rinex file`

The CRX Hatanaka file is corrupted.

`05 - Less than two epochs in the file, reject`

Not enought data in the file to extract a sample rate, and data not relevant because insufficient. Reject the file.

`30 - Input and output folders are the same !`

The file will not be proceeded as rinexmod does not modify files inplace. Check your outputfolder.

`31 - The subfolder can not be reconstructed for file`

The script tries to find the 'reconstruct' subfolder in the file's path to replace it with outputfolder, and does not find it.

`32 - Station's country not retrevied, will not be properly renamed`

When using --name option, that will rename file with rinex long name convention, it needs to retrieve the file's country.
It tries to do so using an external file of list of 9 char ids. the concerned rinex file's station seems to be absent
from this station list file.

`33 - File\'s station does not correspond to provided sitelog - use -f option to force`

The station name retrieved from the provided sitelog does not correspond to the station's name retrieved from
the file's headers. Do not process.

`34 - File's station does not correspond to provided sitelog, processing anyway`

The station name retrieved from the provided sitelog does not correspond to the station's name retrieved from
the file's headers. As the --force option was provided, the file has been processed.

`35 - No instrumentation corresponding to the data period on the sitelog`

There is no continuous instrumentation period in the sitelog taht corresponds to the rinex file's dates. We can thus not fill the header.

`36 - Instrumentation cames from merged periods of sitelog with different firmwares, processing anyway`

We provided the --ignore option, so the consecutive periods of instrumentation for witch only the firmware version of the receiver has changed have been merged. We used this period to fill this file's header.
