## Changelog

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
- add an option `-nh/--no_hatanaka`
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
