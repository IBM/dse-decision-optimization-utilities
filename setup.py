# Copyright IBM All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import setuptools
import dse_do_utils

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

setuptools.setup(
    name="dse_do_utils",
    # version="0.2.2",
    version=dse_do_utils.__version__,
    author="Victor Terpstra",
    author_email="vterpstra@us.ibm.com",
    description="Decision Optimization utilities for IBM Watson Studio projects",
    # long_description=long_description,
    # long_description_content_type="text/markdown",
    url="https://github.com/IBM/dse-decision-optimization-utilities",
    packages=setuptools.find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
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