#  rinexmod

Tool to batch modify headers of RINEX Hatakana compressed files.

2019-12-13 Félix Léger - leger@ipgp.fr

# Project Overview

This script takes a list of RINEX Hanakata compressed files (.d.Z), extract the rinex files and allows to pass to teqc parameters to modify headers, then put them back to Hanakata Z format. It permits also to rename the  files changing the four first characters with another station code.

USAGE :

* RINEXLIST : Rinex list file
* OUTPUTFOLDER : Folder where to write the modified files. This is a compulsory argument, you can not modify files inplace.

OPTIONS :

* -t : teqcargs :     Teqc modification command between double quotes (eg "-O.mn 'AGAL' -O.rt 'LEICA GR25'"). You can refer to teqc -help to see which arguments can be passed to teqc. Here, the pertinent ones are mostly  those starting with O, that permits to modifiy rinex headers.                 
* -n : name : A four characater station code that will be used to rename input files.
* -s : single : Option to provide if you want to run this script on a single rinex file and not on a list of files.
* -r : reconstruct :  Reconstruct files subdirectory. You have to indicate the part of the path that is common to all files in the list and that will be replaced with output folder.
* -v : verbose:       Increase output verbosity. Will prompt teqc +meta of each file before and after teqc modifications.

EXAMPLE:

	./rinexmod.py  RINEXLIST OUTPUTFOLDER (-t "-O.mo 'Abri_du_Gallion' -O.mn 'AGAL' -O.o OVSG") (-n AGAL)  (-s) (-r /ROOTFOLDER/) (-vv)


In addition to the main script, rinexmod.py, crzmeta.py is provided, that permits to extract a crz file'smetadata with crz2rnx and teqc.

USAGE :

	./crzmeta.py RINEXFILE

# Requirements

The tool is in Python 3, your must have it installed on your machine.

You have to have RNX2CRZ and CRZ2RNX installed and declared in your path. The RNXCMP program package must be present on the machine, if not, available there :
http://terras.gsi.go.jp/ja/crx2rnx.html

To declare it in your path, run on linux :

	ln -s FULL_PATH_TO_RNXCMP_PACKAGE/rnx2crz ~/bin/rnx2crz
	ln -s FULL_PATH_TO_RNXCMP_PACKAGE/crz2rnx ~/bin/crz2rnx

You have to have teqc installed and declared in your path. The program must be present on the machine, if not, available there :
https://www.unavco.org/software/data-processing/teqc/teqc.html#executables

To declare it in your path, run on linux :

	 ln -s FULL_PATH_TO_TEQC/teqc ~/bin/teqc
