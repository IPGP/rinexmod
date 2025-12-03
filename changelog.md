## Changelog

### after v3.4.0
Get the changelog directly in:
https://github.com/IPGP/rinexmod/releases

### v3.4.0 (Dec, 2024)

- shell programs are now in a `bin` folder and are set as executable in the `setup.py`
- **the frontend command line interface program has been renamed `rinexmod_run.py` to avoid conflict with the module name**
- add `shortname` option to force RINEX file renaming with short name convention, and modify `longname` option to force RINEX file renaming with long name convention
  (Behavior of previous `longname` option was ambiguous.)
`shortname` is mutually exclusive with `longname`.

### v3.3.0 (Sep 4, 2024)

* `--tolerant_file_period/-tol` is replaced by a more flexible --filename_style/-fns option.
  * it takes now one string argument with 3 acceptable values: 'basic' (per default), 'flex', and 'exact'.
        see help for more details 
  * misc. improvements and bug corrections

### v3.2.0 (Aug 15, 2024)

Misc improvements:

* Enhanced log messages
* Some exception handling when reading RINEX
* RINEX version attribute is now also float
* you can now remove your input RINEXs with -rm, but be carful of what you are doing!


### v3.1.0 (Jun 5, 2024)

make rinexmod compliant with IGSMAIL-8458, i.e. nine characters site in sitelogs, and Country or Region field instead of Country.

### v3.0.0 (Mar 15, 2024)

- **important user interface change**
  - The arguments ``RINEXINPUT`` and ``OUTPUTFOLDER`` are now positional and require options  ``-i/--rinexinput`` and ``-o/--outputfolder``, i.e.:
    - ``-i RINEXINPUT [RINEXINPUT ...], --rinexinput RINEXINPUT [RINEXINPUT ...]`` 
    - ``-o OUTPUTFOLDER, --outputfolder OUTPUTFOLDER`` 
  - previous ``-i`` and ``-o`` are now:
    - ``-ig, --ignore``
    - ``-ol OUTPUT_LOGS, --output_logs OUTPUT_LOGS``
- import of GAMIT's files _station.info_ & _apr/L-file_ is now possible with `-sti` and `-lfi` options
- Refactoring: `SiteLog` class becomes `MetaData` class for more versatility. Many functions and variables have been renamed accordingly.
- add an option `-nh/--no_hatanaka` and `-co/--country`
- Misc. bugs correction

### v2.2.1 (Jan 13, 2024)

_Under the hood_ improvements:
- add the `rinexmod` module (folder)
- add `setup.py` for assisted installation

:warning: inform the developer if you meet import troubles

NB: present v2.2.1 corrects an import bug for front-end programs

### v2.2 (Jan 12, 2024)

_Under the hood_ improvements:
- add the `rinexmod` module (folder)
- add `setup.py` for assisted installation

:warning: inform the developer if you meet import troubles

### v2.1 (Nov 5, 2023)

**v2.1 release features**
-  allows multiprocessing to fasten RINEX modifications (option `-mp`)
- new debug mode (option `-d`)
- ` -tol, --tolerant_file_period` option
the RINEX file period is tolerant and stick to the actual data content, but then can be odd (e.g. 07H, 14H...). A strict file period is applied per default (01H or 01D), being compatible with the IGS conventions
- `filename_data_source` (R, S, U) as modification keywords
- several miscellaneous bugs corrected

### v2.0 (May 15, 2023)

Add modularity in the behavior of rinexmod:

- a new module `rinexmod_api` has been created
- better RINEX3 handling
- several bug corrections
(a detailed help and tutorial will come in a future release ;) )

### v1.1 (Feb 27, 2023)

Misc. modifications in the options.

A bigger update is in preparation to allows to run rinexmod in an API mode.

### v1.0 (Apr 20, 2022)
