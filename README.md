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

## Installation on CPDv4.5
For Cloud Pak for Data v4.5.

### Install in customized environment
CPDv4.5 allows for easy customization of environments.
Add the following to the customization configuration:

```
channels:
dependencies:
  - pip
  - pip:
    - dse-do-utils==0.5.5.0
    - decision-optimization-client==1.1.0
```
This automatically downloads dse-do-utils from PyPI and installs the package.


For air-gapped systems that have no access to PyPI:
1. Download the package from PyPI/Conda from an internet connected system as a wheel/zip file
2. Upload the wheel/zip as a data asset, or place in any location in the JupyterLab file system
3. Add a pip dependency in the environment yaml:

```
dependencies:
  - pip:
    - file:///userfs/packages/dse_do_utils-0.5.4.5b4-py3-none-any.whl
```

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
1. CP4D on-prem v4.0 and up
4. CP4DaaS / WS Cloud (version 0.4.0.0 and up)

## DO Model Builder and WML environments
When developing and using optimization models, there are 3 different environments the Python DO model might run in:
1. A notebook environment. 
2. The DO Model Builder environment.
3. The WML deployment environment.

From CP4D 4.6, all environments can be customized from PyPI packages and wheel files

## Scope of classes/modules
The classes `OptimizationEngine` and  `DataManager` are intended to be used within the optimization model code 
that will run in the Model Builder and WML deployment. All other classes, in particular the `ScenarioManager` are 
designed to be used outside of the Model Builder or WML, e.g. within `#dd-ignore` cells.

## Requirements
This package requires:
1. [decision-optimization-client](https://ibmdecisionoptimization.github.io/decision-optimization-client-doc/). This package provides an interface to the DO scenarios. 
This package is available in PyPI, however it only runs within CP4D/CP4DaaS.
2. [docplex](http://ibmdecisionoptimization.github.io/docplex-doc/mp/index.html). This package interfaces with the CPLEX and CP Optimizer optimization engines.
3. [folium](https://github.com/python-visualization/folium). Map visualization. Only for the MapManager.