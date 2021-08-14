# DSE_DO_Utils
Decision Optimization utilities for IBM Watson Studio Local and ICPd projects.

[Source (GitHub)](https://github.com/IBM/dse-decision-optimization-utilities)<br>
[Documentation (GitHubPages)](https://ibm.github.io/dse-decision-optimization-utilities/)

This repository contains the package `dse_do_utils`. This can be installed using pip.

## Important
From v0.5.0.0, the dse-do-utils require the package decision-optimization-client==1.0.0 and no longer the former dd-scenario.
This package is NOT installed by default, neither in CPD3.5 not CPD4.0.
DSE-DO-Utils v0.5.0.0 works in both CPD 3.5 and 4.0.
dd-scenario works in CPDv3.5, but NOT in CPDv4.0.

## Main classes:
1. ScenarioManager. Reads and writes table data from and to all combinations of csv-files, Excel spreadhseet and DO scenario.
2. DataManager. A DataManager is mostly a container for data and functions for pre- and post-processing. 
Can be subclassed and stored in a script to be able to share code between multiple notebooks. 
Also contains some utilities for data manipulation, like the crossjoin.
3. OptimizationEngine. Also mostly a container for functions around creating an optimization model and using the docplex APIs. 
Can be subclassed and stored in a script to be able to share code between multiple notebooks.
Also contains some functions to create dvars and export .lp files.
4. ScenarioPicker. Interactively pick an existing scenario from a drop-down menu in a notebook. Typically used in visualization notebooks. 
5. MapManager. For creating map visualizations using Folium.

## Installation on CPDv4.0
For Cloud Pak for Data v4.0.

### Install in customized environment
CPDv4.0 allows for easy customization of environments.
Add the following to the customization configuration:

```
channels:
  - fake     # or empty
  - nodefaults

dependencies:
  - pip
  - pip:
    - dse-do-utils==0.5.0.0
    - decision-optimization-client==1.0.0
```
This automatically downloads dse-do-utils from PyPI and installs the package.
(Note: the `fake` / `nodefaults` is a hack to avoid installation of pip itself. This will greatly improve the installation performance.)


## Installation (CPDv2.5)
(For Cloud Pak for Data v2.5)

CPDv2.5 is very different from the previous versions and it has a significant impact on how the dse-do-utils can be installed and used.

Options:
1. Install using pip in a customized environment. This applies to both Jupyter and JupyterLab.
2. Install as a package in JupyterLab.
3. Install as modules in Jupyter
4. Install/use as modules in the DO Model Builder

### Install in customized environment
CPDv2.5 allows for easy customization of environments.
Add the following to the customization configuration:
```
- pip:
    - dse-do-utils=0.3.0.0
```
This automatically downloads dse-do-utils from PyPI and installs the package.

For air-gapped systems that have no access to PyPI:
1. Download the package from PyPI/Conda from an internet connected system as a wheel/zip file
2. Upload the wheel/zip as a data asset
3. Install package from wheel/zip

This downloads the package as a wheel/zip and puts it in the data assets
```
!pip download dse-do-utils -d /project_data/data_asset/
```
Then move the wheel/zip to the Data Assets. 
See the `InstallationReadMe.md` for more details on installation and usage in other cases.

## Import
Then import the required classes from  `dse_do_utils`:
```
from dse_do_utils import ScenarioManager, DataManager
```
This is the basics. For many ore details on other usage, see `InstallationReadMe.md` 

## Target environments
To be used within:
1. CPDv2.1 (version 0.2.2.3 is preferred. But version 0.3.0.0 should be backwards compatible.)
2. CPDv2.5 (version 0.3.0.0 and up)
3. WSLv1.2.3 with Python 2.7 (version 0.2.2.3 only)
4. WS Cloud (version 0.4.0.0 and up)

## DO Model Builder and WML environments
When developing and using optimization models, there are 3 different environments the Python DO model might run in:
1. A notebook environment. 
2. The DO Model Builder environment.
3. The WML deployment environment.

In CPDv2.5:
* Only the notebook environment can be regularly customized with the dse-do-utils.
* The Model Builder environment cannot be customized. But, it has a feature to add 'files'. 
The dse-do-utils internal modules have been refactored to be able to be uploaded separately as individual modules.
* The WML environment cannot be customized. But the same work-around for adding modules/files to the MB model can be used.

In CPDv3.0:
* The WML environment can be customized using APIs.

In future releases of CPD:
* The DO Model Builder will also allow for environment customization

## Scope of classes/modules
The classes `OptimizationEngine` and  `DataManager` are intended to be used within the optimization model code 
that will run in the Model Builder and WML deployment. All other classes, in particular the `ScenarioManager` are 
designed to be used outside of the Model Builder or WML, e.g. within `#dd-ignore` cells.

Therefore, the limitations in customizing environments can, for the moment, be avoided by not using 
the classes `OptimizationEngine` and  `DataManager`.

## Requirements
This package requires:
1. [dd-scenario](https://pages.github.ibm.com/IBMDecisionOptimization/dd-scenario-api/dd-scenario-client-python/doc/build/html/). This package provides an interface to the DO scenarios. 
This package is only available within WSL and ICPd. It cannot be pip installed in other environments.
2. [docplex](http://ibmdecisionoptimization.github.io/docplex-doc/mp/index.html). This package interfaces with the CPLEX and CP Optimizer optimization engines.
3. [folium](https://github.com/python-visualization/folium). Map visualization. Only for the MapManager.