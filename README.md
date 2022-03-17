#  rinexmod

Tool to batch modify headers of RINEX Hatakana compressed files from the command line or a sitelog and optionnaly batch rename them.

2021-02-07 Félix Léger - leger@ipgp.fr

# Project Overview

This project is composed of 4 scripts.

* rinexmod.py takes a list of RINEX Hanakata compressed files (.d.Z or .d.gz or .rnx.gz), loop the rinex files and modifiy the file's header. It then write them back to Hanakata compressed format in an output folder. It also allows renaming the files by changing the four first characters with another station code.  It can write those files with the long name naming convention. Two ways of passing parameters to modifiy headers are possible, passing the headers fields values args as an argument, or passing a sitelog as an argument. In this case, the script will treat only files corresponding to the same station as the provided sitelog, and will take the start and end time of each proceeded file and use them to extract the right station instrumentation from the sitelog.

* get_m3g_sitelogs.py will get last version of sitelogs from M3G repository and write them in an observatory dependent subfolder.

* batch_rinexmod.py will read a folder and extract rinex files, or read directly a file containing a list of rinex files. It will then identify the corresponding sitelogs, and launch rinexmod.py for each of the sitelog and station rinex file pairs. It can also launch get_m3g_sitelogs.py as an option to be sure to use last sitelogs version.

* crzmeta.py will extract rinex file's header information and prompt the result. This permits to access quickly the header information without uncompressing manually the file.

# rinexmod.py

Two ways of passing parameters to modifiy headers are possible:

* --modification_kw : you pass as argument the field(s) that you want to modifiy and its value.
                      Acceptable_keywords are : station, receiver_serial, receiver_type, receiver_fw,
                      antenna_serial, antenna_type, antenna_X_pos, antenna_Y_pos, antenna_Z_pos,
                      antenna_X_delta, antenna_Y_delta, antenna_Z_delta,
                      operator, agency, observables


* --sitelog  : you pass a sitelog file. The script will treat only files corresponding to
               the same station as the provided sitelog. You then have to pass a list
               of files comming from the right station. If not, they will be rejected.
               The script will take the start and end time of each proceeded file
               and use them to extract from the sitelog the station instrumentation
               of the corresponding period and fill file's header with following infos :
                       Four Character ID
                       X coordinate (m)
                       Y coordinate (m)
                       Z coordinate (m)
                       Receiver Type
                       Serial Number
                       Firmware Version
                       Satellite System (will translate this info to one-letter code, see RinexFile.set_observable_type())
                       Antenna Type
                       Serial Number
                       Marker->ARP Up Ecc. (m)
                       Marker->ARP East Ecc(m)
                       Marker->ARP North Ecc(m)
                       On-Site Agency Preferred Abbreviation
                       Responsible Agency Preferred Abbreviation

You can not provide both --modification_kw and --sitelog options.

USE :

* RINEXLIST : Rinex list file
* OUTPUTFOLDER : Folder where to write the modified files. This is a compulsory argument, you can not modify files inplace.

OPTIONS :

* -k : --modification_kw :    Header fields that you want to modify.
* -s : --sitelog :            Sitelog file in witch rinexmod will find file's period's
                              instrumentation informations, or folder containing sitelogs.
                              The sitelogs must be valid as the script does not check it.
* -f : --force :              Force appliance of sitelog based header arguments when
                              station name within file does not correspond to sitelog.
* -i : --ignore :             Ignore firmware changes between instrumentation periods
                              when getting headers args info from sitelogs.
* -m : --marker :             A four characater station code that will be used to rename
                              input files.
* -n : --ninecharfile :       path a of a list file containing 9-char. site names from
                              the M3G database generated with get_m3g_stations.
                              Not mandatory, but nessessary to get the country code to rename
                              files to long name standard. If not provided the country code will be XXX.
* -a : --alone :              Option to provide if you want to run this script on a lone
                              rinex file and not on a list of files.
* -c : --compression :        Set file's compression (acceptables values : 'gz' (recommended
                              to fit IGS standards), 'Z'. Default value will retrieve
                              the actual compression of the input file.
* -l : --longname             Rename file using long name rinex convention.
* -r : --reconstruct :        Reconstruct files subdirectory. You have to indicate the
                              part of the path that is common to all files in the list and
                              that will be replaced with output folder.
* -v : --verbose:             Will prompt file's metadata before and after modifications.

EXAMPLES:

./rinexmod.py  RINEXLIST OUTPUTFOLDER (-k antenna_type='ANT TYPE' antenna_X_pos=9999 agency=AGN) (-m AGAL) (-s) (-r /ROOTFOLDER/) (-v)
./rinexmod.py  RINEXLIST OUTPUTFOLDER (-l ./sitelogsfolder/stationsitelog.log) (-m AGAL) (-s) (-r /ROOTFOLDER/) (-f) (-i) (-v)

# get_m3g_sitelogs.py

This script will get last version of sitelogs from M3G repository and write them in an observatory dependent subfolder set in 'observatories'.

USE :

* OUTPUTFOLDER : Folder where to write the downloaded sitelogs.

OPTION :

* -d : delete : Delete old sitelogs in storage folder. This permits to have only the last version, as version changing sitelogs changes of name.

EXAMPLE:

	./get_m3g_sitelogs.py OUTPUTFOLDER (-d)

# batch_rinexmod.py

This script will read a folder and extract rinex files, or read directly a file containing a list of files. For each of those files, it will lauch rinexmod function, that will fill the file's header with informations gathered from the corresponding sitelog, read in the 'sitelogsfolder' folder.
Sitelogs can be updated during the process using --update option. The corrected files will be written to 'outputfolder' folder, and subfolders will be reconstructed. The part of the path that is common to all files must be indictaed in 'reconstruct' and this part of the path will be replaced with output folder.
All those 3 variables ('sitelogsfolder', 'outputfolder' and 'reconstruct') are stored in the batch_rinexmod.cfg ini file.

USE:

* RINEXFOLDER : folder where rinexfiles will be scanned.
* RINEXLIST : list of rinex files.

OPTION :

* -u : update : Update sitelogs in corresponding folder using get_m3g_sitelogs.py script.

EXAMPLES:

	./batch_rinexmod.py  RINEXLIST (-u)
	./batch_rinexmod.py  RINEXFOLDER (-u)

# crzmeta.py

The script will permit to extract a crz file's metadata.

USE :

	./crzmeta.py RINEXFILE

# Requirements

The tool is in Python 3, you must have it installed on your machine. Install Hatanaka for RINEX decompression.

 pip install hatanaka

# rinexmod error messages

Rinexmod will prompt errors when arguments are wrong. Appart from this, it will prompt and save to file errors and waring
occuring on specific files from the rinex list. Here are the error codes :


01 - The specified file does not exists

That means that the input file containing list of rinex files is wrong and references a file that is not present. It can also mean that the file has been deleteted between the list generation and the script launch, but this case should be quite rare.

02 - Not an observation Rinex file

The file name does not correspond to the classic pattern (it doesn't match the regular expression for new and old convention namming model ). Most of time, it's because it is not a d rinex file (for example, navigation file).

03 - Invalid  or empty Zip file

The Zip file is corrupted or empty

04 - Invalid Compressed Rinex file

The CRX Hatanaka file is corrupted.

30 - Input and output folders are the same !

The file will not be proceeded as rinexmod does not modify files inplace. Check your outputfolder.

31 - The subfolder can not be reconstructed for file

The script tries to find the 'reconstruct' subfolder in the file's path to replace it with outputfolder, and does not find it.

32 - Station's country not retrevied, will not be properly renamed

When using --name option, that will rename file with rinex long name convention, it needs to retrieve the file's country.
It tries to do so using an externa file of list of 9 char ids. the concerned rinex file's station seems to be absent
from this station list file.

33 - File\'s station does not correspond to provided sitelog - use -f option to force

The station name retrieved from the provided sitelog does not correspond to the station's name retrieved from
the file's headers. Do not process.

34 - File's station does not correspond to provided sitelog, processing anyway

The station name retrieved from the provided sitelog does not correspond to the station's name retrieved from
the file's headers. As the --force option was provided, the file has been processed.

35 - No instrumentation corresponding to the data period on the sitelog

There is no continuous instrumentation period in the sitelog taht corresponds to the rinex file's dates. We can thus not fill the header.

36 - Instrumentation cames from merged periods of sitelog with different firmwares, processing anyway

We provided the --ignore option, so the consecutive periods of instrumentation for witch only the firmave version of the receiver has changed have been merged. We used this period to fill this file's header.
