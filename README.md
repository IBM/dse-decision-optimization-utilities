# DSE_DO_Utils
Decision Optimization utilities for IBM Watson Studio Local and ICPd projects.

[Source (GitHub)](https://github.com/IBM/dse-decision-optimization-utilities)<br>
[Documentation (GitHubPages)](https://ibm.github.io/dse-decision-optimization-utilities/)

This repository contains the package `dse_do_utils`. This can be installed using pip.

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
6. DeployedDOModel. Interfacing from Python to a deployed DO model.


## Installation
Recommend to install in the `../packages/python` folder by running the following in a notebook cell: 
```
!pip install -i https://test.pypi.org/simple/dse-do-utils --target='../packages/python'
```
See also [Installing packages and modules for Decision Optimization projects in Watson Studio Local](https://medium.com/@vjterpstracom/installing-packages-and-modules-for-decision-optimization-projects-in-watson-studio-local-69abc934ef32)
## Import
Import the `dse_do_utils` from the `../packages/python` folder.<br>
First add the folder to the Python path:
```
import sys, os
for folder in ['packages/python', 'scripts']:
    path = os.path.join(os.environ['DSX_PROJECT_DIR'], folder)
    if path not in sys.path:
        sys.path.insert(0, path)
```
Then import the required classes from the package:
```
from dse_do_utils import ScenarioManager, DataManager
```

## Requirements
This package requires:
1. [dd-scenario](https://pages.github.ibm.com/IBMDecisionOptimization/dd-scenario-api/dd-scenario-client-python/doc/build/html/). This package provides an interface to the DO scenarios. 
This package is only available within WSL and ICPd. It cannot be pip installed in other environments.
2. [docplex](http://ibmdecisionoptimization.github.io/docplex-doc/mp/index.html). This package interfaces with the CPLEX and CP Optimizer optimization engines.
3. [folium](https://github.com/python-visualization/folium). Map visualization. Only for the MapManager.