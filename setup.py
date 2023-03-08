# Copyright IBM All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import os
import setuptools
# import dse_do_utils

with open("README.md", "r") as fh:
    long_description = fh.read()

"""
Versions: beware to keep the version in `setup.py` in sync with the version in `dse_do_utils.version.py`
For work-arounds eee https://stackoverflow.com/questions/458550/standard-way-to-embed-version-into-python-package
Also: https://packaging.python.org/guides/single-sourcing-package-version/
TODO: test the following to get the version automatically from version.py (see https://packaging.python.org/guides/single-sourcing-package-version/):

import dse_do_utils
setuptools.setup(
    ...
    version=dse_do_utils.__version__,
    ...
)
This may NOT work, because when setup runs, the package is not available and cannot be imported?
Work around is to read the version.py file
Although in https://packaging.python.org/guides/single-sourcing-package-version/ this is one of the suggestions.
VT-20200222: Seems to work fine
"""
###############################################################################
# To get the __version__.
# See https://packaging.python.org/guides/single-sourcing-package-version/
# This avoids doing an `import dse_do_supply_chain`, which is causing problems
# installing in a WML DO deployment
###############################################################################
def read(rel_path: str) -> str:
    here = os.path.abspath(os.path.dirname(__file__))
    # intentionally *not* adding an encoding option to open, See:
    #   https://github.com/pypa/virtualenv/issues/201#issuecomment-3145690
    with open(os.path.join(here, rel_path)) as fp:
        return fp.read()

def get_version(rel_path: str) -> str:
    for line in read(rel_path).splitlines():
        if line.startswith("__version__"):
            delim = '"' if '"' in line else "'"
            return line.split(delim)[1]
    raise RuntimeError("Unable to find version string.")
###############################################################################

setuptools.setup(
    name="dse_do_utils",
    # version="0.2.2",
    # version=dse_do_utils.__version__,
    version=get_version("dse_do_utils/version.py"),
    author="Victor Terpstra",
    author_email="vterpstra@us.ibm.com",
    description="Decision Optimization utilities for IBM Watson Studio projects",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/IBM/dse-decision-optimization-utilities",
    # packages=setuptools.find_packages(),
    packages=['dse_do_utils', 'dse_do_utils.core'],

    classifiers=[
        "Development Status :: 4 - Beta",
        # "Development Status :: 5 - Production/Stable",
        "Programming Language :: Python :: 3.6",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        "Topic :: Documentation :: Sphinx"
    ],
    project_urls={  # Optional
        'Source': 'https://github.com/IBM/dse-decision-optimization-utilities',
        'Documentation': 'https://ibm.github.io/dse-decision-optimization-utilities/',
        'IBM Decision Optimization': 'https://www.ibm.com/analytics/decision-optimization',
    },
)