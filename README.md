#  rinexmod

Tool to batch modify headers of RINEX Hatakana compressed files from a teqc command or a sitelog and optionnaly batch rename them.

2021-02-07 Félix Léger - leger@ipgp.fr

# Project Overview

This script takes a list of RINEX Hanakata compressed files (.d.Z), extract the rinex files and allows to pass to teqc parameters to modify headers, then put them back to Hanakata Z format. It permits also to rename the  files changing the four first characters with another station code.

Two ways of passing parameters to teqc are possible:

* --teqcargs : you pass as argument the command that teqc has to execute.
               E.g. : --teqcargs "-O.mn 'AGAL' -O.rt 'LEICA GR25'"

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
                       Antenna Type
                       Serial Number
                       Marker->ARP Up Ecc. (m)
                       Marker->ARP East Ecc(m)
                       Marker->ARP North Ecc(m)

You can not provide both --teqcargs and --sitelog options.

USAGE :

* RINEXLIST : Rinex list file
* OUTPUTFOLDER : Folder where to write the modified files. This is a compulsory argument, you can not modify files inplace.

OPTIONS :

* -t : teqcargs :     Teqc modification command between double quotes (eg "-O.mn 'AGAL' -O.rt 'LEICA GR25'"). You can refer to teqc -help to see which arguments can be passed to teqc. Here, the pertinent ones are mostly  those starting with O, that permits to modifiy rinex headers.        
* -l : --sitelog :    Sitelog file in with rinexmod will find file's period's instrumentation informations. The sitelog must be valid as the script does not check it.         
* -f : force :        Force appliance of sitelog based teqc arguments when station name within file does not correspond to sitelog.
* -i : ignore :       Ignore firmware changes between instrumentation periods when getting teqc args info from sitelogs.
* -n : name :         A four characater station code that will be used to rename input files.
* -s : single :       Option to provide if you want to run this script on a single rinex file and not on a list of files.
* -r : reconstruct :  Reconstruct files subdirectory. You have to indicate the part of the path that is common to all files in the list and that will be replaced with output folder.
* -v : verbose:       Increase output verbosity. Will prompt teqc +meta of each file before and after teqc modifications.

EXAMPLES:

	./rinexmod.py  RINEXLIST OUTPUTFOLDER (-t "-O.mo 'Abri_du_Gallion' -O.mn 'AGAL' -O.o OVSG") (-n AGAL)  (-s) (-r /ROOTFOLDER/) (-vv)
	./rinexmod.py  RINEXLIST OUTPUTFOLDER (-l ./sitelogsfolder/stationsitelog.log) (-n AGAL) (-s) (-r /ROOTFOLDER/) (-vv)

In addition to the main script, rinexmod.py, crzmeta.py is provided. It permits to extract a crz file's metadata with crz2rnx and teqc.

USAGE :

	./crzmeta.py RINEXFILE

# Batch_rinexmod

This script will read a folder and extract rinex files, or read directly a file containing a list of files. For each of those files, it will lauch rinexmod function, that will fill the file's header with informations gathered from the corresponding sitelog, read in the 'sitelogsfolder' folder.
Sitelogs can be updated during the process using --update option. The corrected files will be written to 'outputfolder' folder, and subfolders will be reconstructed. The part of the path that is common to all files must be indictaed in 'reconstruct' and this part of the path will be replaced with output folder.
All those 3 variables ('sitelogsfolder', 'outputfolder' and 'reconstruct') are stored in the batch_rinexmod.cfg ini file.

# Requirements

The tool is in Python 3, your must have it installed on your machine.

You have to have RNX2CRZ, CRZ2RNX, RNX2CRX and CRX2RNX installed and declared in your path. The RNXCMP program package must be present on the machine, if not, available there :
http://terras.gsi.go.jp/ja/crx2rnx.html

To declare it in your path, run on linux :

	ln -s FULL_PATH_TO_RNXCMP_PACKAGE/rnx2crz ~/bin/rnx2crz
	ln -s FULL_PATH_TO_RNXCMP_PACKAGE/crz2rnx ~/bin/crz2rnx
	ln -s FULL_PATH_TO_RNXCMP_PACKAGE/rnx2crx ~/bin/rnx2crx
	ln -s FULL_PATH_TO_RNXCMP_PACKAGE/crx2rnx ~/bin/crx2rnx

You may encounter problems with case of those symlinks as the executables are in upper case or lower case depending to the version.

You have to have teqc installed and declared in your path. The program must be present on the machine, if not, available there :
https://www.unavco.org/software/data-processing/teqc/teqc.html#executables

To declare it in your path, run on linux :

	 ln -s FULL_PATH_TO_TEQC/teqc ~/bin/teqc
