"""A setuptools based setup module.

See:
https://packaging.python.org/guides/distributing-packages-using-setuptools/
https://github.com/pypa/sampleproject
"""

import pathlib

# Always prefer setuptools over distutils
from setuptools import setup, find_packages

here = pathlib.Path(__file__).parent.resolve()

# Get the long description from the README file
long_description = (here / 'README.md').read_text(encoding='utf-8')


# Load the requirements from the requirements.txt file
# Frederick Brennan answer on stackoverflow
# https://stackoverflow.com/questions/14399534/reference-requirements-txt-for-the-install-requires-kwarg-in-setuptools-setup-py
with open(here / 'requirements.txt') as f:
    required = f.read().splitlines()

# Arguments marked as "Required" below must be included for upload to PyPI.
# Fields marked as "Optional" may be commented out.

setup(
    # This is the name of your project. The first time you publish this
    # package, this name will be registered for you. It will determine how
    # users can install this project, e.g.:
    #
    # $ pip install sampleproject
    #
    # And where it will live on PyPI: https://pypi.org/project/sampleproject/
    #
    # There are some restrictions on what makes a valid project name
    # specification here:
    # https://packaging.python.org/specifications/core-metadata/#name
    name='rinexmod',  # Required

    # Versions should comply with PEP 440:
    # https://www.python.org/dev/peps/pep-0440/
    #
    # For a discussion on single-sourcing the version across setup.py and the
    # project code, see
    # https://packaging.python.org/en/latest/single_source_version.html

    version=str('3.6.3'),  # Required ## CHANGE IT ALSO IN __init__ and readme !!!!

    # This is a one-line description or tagline of what your project does. This
    # corresponds to the "Summary" metadata field:
    # https://packaging.python.org/specifications/core-metadata/#summary
    description=' Tool to batch modify headers of RINEX Hatanaka compressed files. ',  # Optional

    # This is an optional longer description of your project that represents
    # the body of text which users will see when they visit PyPI.
    #
    # Often, this is the same as your README, so you can just read it in from
    # that file directly (as we have already done above)
    #
    # This field corresponds to the "Description" metadata field:
    # https://packaging.python.org/specifications/core-metadata/#description-optional
    long_description="""rinexmod is a tool to batch modify the headers of GNSS data files in RINEX format, as well as to rename them correctly.
It supports Hatakana-compressed and non-compressed files, RINEX versions 2 and 3, as well as short and long naming conventions.
It is developed in python3, and can be run from the command line or directly in API mode by calling a python function.
The required input metadata can come from a sitelogs file, or be manually entered as arguments to the command line or the called function.
It is available under the GNU license on the following GitHub repository: https://github.com/IPGP/rinexmod
""",  # Optional

    # Denotes that our long_description is in Markdown; valid values are
    # text/plain, text/x-rst, and text/markdown
    #
    # Optional if long_description is written in reStructuredText (rst) but
    # required for plain-text or Markdown; if unspecified, "applications should
    # attempt to render [the long_description] as text/x-rst; charset=UTF-8 and
    # fall back to text/plain if it is not valid rst" (see link below)
    #
    # This field corresponds to the "Description-Content-Type" metadata field:
    # https://packaging.python.org/specifications/core-metadata/#description-content-type-optional
    # long_description_content_type='text/markdown',  # Optional (see note above)
    long_description_content_type='text/x-rst',  # Optional (see note above)
    # This should be a valid link to your project's main homepage.
    #
    # This field corresponds to the "Home-Page" metadata field:
    # https://packaging.python.org/specifications/core-metadata/#home-page-optional
    url='https://github.com/IPGP/rinexmod',  # Optional

    # This should be your name or the name of the organization which owns the
    # project.
    author='Pierre Sakic',  # Optional

    # This should be a valid email address corresponding to the author listed
    # above.
    author_email='sakic@ipgp.fr',  # Optional

    # Classifiers help users find your project by categorizing it.
    #
    # For a list of valid classifiers, see https://pypi.org/classifiers/
    classifiers=[  # Optional
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 5 - Production/Stable',

        # Indicate who your project is intended for
        'Intended Audience :: Science/Research',

        # Pick your license as you wish
        'License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)',

        # Specify the Python versions you support here. In particular, ensure
        # that you indicate you support Python 3. These classifiers are *not*
        # checked by 'pip install'. See instead 'python_requires' below.
        # 'Programming Language :: Python :: 3',
        # 'Programming Language :: Python :: 3.5',
        # 'Programming Language :: Python :: 3.6',
        # 'Programming Language :: Python :: 3.7',
        # 'Programming Language :: Python :: 3.8',
        # 'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3 :: Only',
    ],
    # This field adds keywords for your project which will appear on the
    # project page. What does your project relate to?
    #
    # Note that this is a list of additional keywords, separated
    # by commas, to be used to assist searching for the distribution in a
    # larger catalog.
    keywords='geodesy, gnss, rinex, header, metadata, positioning',  # Optional

    # When your source code is in a subdirectory under the project root, e.g.
    # `src/`, it is necessary to specify the `package_dir` argument.
    ##package_dir={'': 'geodezyx/'},  # Optional

    # You can just specify package directories manually here if your project is
    # simple. Or you can use find_packages().
    #
    # Alternatively, if you just want to distribute a single Python file, use
    # the `py_modules` argument instead as follows, which will expect a file
    # called `my_module.py` to exist:
    #
    #   py_modules=["my_module"],
    #
    packages=find_packages(where='.'),  # Required

    # Specify which Python versions you support. In contrast to the
    # 'Programming Language' classifiers above, 'pip install' will check this
    # and refuse to install the project if the version does not match. See
    # https://packaging.python.org/guides/distributing-packages-using-setuptools/#python-requires
    python_requires='>=3.5, <4',

    # This field lists other packages that your project depends on to run.
    # Any package you put here will be installed by pip when your project is
    # installed, so they must be valid existing projects.
    #
    # For an analysis of "install_requires" vs pip's requirements files see:
    # https://packaging.python.org/en/latest/requirements.html

    # requirements.txt is read at the beginning of the setup.py file
    # and the required packages are stored in the list 'required'
    install_requires=required,  # Optional

    # List additional groups of dependencies here (e.g. development
    # dependencies). Users will be able to install these using the "extras"
    # syntax, for example:
    #
    #   $ pip install sampleproject[dev]
    #
    # Similar to `install_requires` above, these must be valid existing
    # projects.
    extras_require={  # Optional
    #    'dev': ['check-manifest'],
    #    'test': ['coverage'],
         # 'full': ['netCDF4',
                  # 'kepler.py',
                  # 'ncompress'],

    },

    # If there are data files included in your packages that need to be
    # installed, specify them here.
    #package_data={  # Optional
    #    'sample': ['package_data.dat'],
    #},

    # Although 'package_data' is the preferred approach, in some case you may
    # need to place data files outside of your packages. See:
    # http://docs.python.org/distutils/setupscript.html#installing-additional-files
    #
    # In this case, 'data_file' will be installed into '<sys.prefix>/my_data'
    #data_files=[('my_data', ['data/data_file'])],  # Optional

    # To provide executable scripts, use entry points in preference to the
    # "scripts" keyword. Entry points provide cross-platform support and allow
    # `pip` to create the appropriate form of executable for the target
    # platform.
    #
    # For example, the following would provide a command called `sample` which
    # executes the function `main` from this package when invoked:
    entry_points={  # Optional
       'console_scripts': [
           'rinexmod_run=rinexmod.bin.rinexmod_run:main',
           'crzmeta=rinexmod.bin.misc_tools.crzmeta:main',
           'get_m3g_sitelogs=rinexmod.bin.misc_tools.get_m3g_sitelogs:main',
           'rinexrename=rinexmod.bin.misc_tools.rinexrename:main'
       ],
    },

    # scripts = ['bin/rinexmod_run.py',
    #            'bin/misc_tools/rinexrename.py',
    #            'bin/misc_tools/get_m3g_sitelogs.py',
    #            'bin/misc_tools/crzmeta.py'],

    # List additional URLs that are relevant to your project as a dict.
    #
    # This field corresponds to the "Project-URL" metadata fields:
    # https://packaging.python.org/specifications/core-metadata/#project-url-multiple-use
    #
    # Examples listed include a pattern for specifying where the package tracks
    # issues, where the source is hosted, where to say thanks to the package
    # maintainers, and where to support the project financially. The key is
    # what's used to render the link text on PyPI.
    #project_urls={  # Optional
    #    'Bug Reports': 'https://github.com/pypa/sampleproject/issues',
    #    'Funding': 'https://donate.pypi.org',
    #    'Say Thanks!': 'http://saythanks.io/to/example',
    #    'Source': 'https://github.com/GeodeZYX/geodezyx-toolbox' #,
    #}
)
