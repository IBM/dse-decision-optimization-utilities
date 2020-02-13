# DSE_DO_Utils Installation

## Installation on CPDv2.5
For Cloud Pak for Data v2.5.
See also the notebook `Install_DSE_DO_Utils_ReadMe.ipynb`.

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
Then run the following to make the file visible in the WS Data Assets UI:
```
file_name = 'dse_do_utils-0.3.0.0.tar.gz'
file_path = '/project_data/data_asset/' + file_name
with open(file_path, 'rb') as f:
    from project_lib import Project
    project = Project.access()
    project.save_data(file_name=file_name, data=f, overwrite=True)
```
Once it is in the data assets, the project can be exported and moved to the air-gapped system

Next, set the environment customization to:
```
- pip:
    - dse-do-utils --no-index --find-links=/project_data/data_asset/dse_do_utils-0.3.0.0.tar.gz
```

### Installation as package in JupyterLab
If you want to make changes to the dse-do-utils, you can download the package folder and copy into a folder in JupyterLab.
For instance in `/packages/python/`. 
Or pip install in the folder:
```
!pip install dse-do-utils==0.3.0.0 --target='/packages/python'
```

Then add this folder to the Python path by adding the following in a cell in a notebook:
```
import sys, os
for folder in ['packages/python', 'scripts']:
    path = os.path.join(os.environ['PWD'], folder)
    if path not in sys.path:
        sys.path.insert(0, path)
```

### Installation as modules in Jupyter
In CPDv2.5 and working with Jupyter, there is no longer a `scripts` or `packages/python` directory.
The work-around to work with modules is to use a notebook to write a file to a local (hidden) file system.

Two options:
1. In a notebook, copy the contents of a module in a cell and add the following as the first line in the cell:
```
%%writefile mymodule.py
```
Run the cell. It writes a module `mymodule` in a location that is on the default Python path

2. Upload the modules of the dse-do-utils package as Data Assets.
Then run the something like following to write the contents as a file on the Python path.
```
from project_lib import Project
project = Project.access()
# Read module from data assets:
my_module = project.get_file(asset_name)
my_module.seek(0)
# Write module in 'current directory to allow import'
f = open(asset_name, 'wb')
f.write(my_module.read())
```

### Import from the dse_do_utils package
The `__init__.py` maps definitions from the various internal modules to the package level.<br>
This allows import directly from the package. For instance:
```
from dse_do_utils import ScenarioManager
```

This works when:
* The package has been installed as a whole (either throught the customized environment or as a directory in JupyterLab)
* No need to make changes to the code

###Import from the dse_do_utils modules within the package
Directly import the definitions from the internal modules. For instance:
```
from dse_do_utils.scenariomanager import ScenarioManager
```

This approach is necessary when actively making changes to the code of the package.
After a change, the module needs to me reloaded:
1. Either explicitly using reload:
```
import imp, dse_do_utils
imp.reload(dse_do_utils.scenariomanager)
```
2. Or indirectly via autoreload jupyter extension:
```
%load_ext autoreload
%autoreload 2
```
Both autoreload and imp.reload will reload the internal module. But that will only update the definition if it was directly imported from the module itself (and not indirectly via the `__init__.py` at the package level). 

### Import from a module as part of a set of modules
In case the package was extracted into a set of individual modules, like when attaching the modules to a DO model, we need to import directly from the stand-alone module:
```
from scenariomanager import ScenarioManager
```

This would apply to a solver notebook. But when testing the notebook, it needs to load from the installed package, we need to be flexible. First try to import from the package. if that fails, import from the module:
```
try:
    from dse_do_utils.datamanager import DataManager
    from dse_do_utils.optimizationengine import OptimizationEngine
except:
    from datamanager import DataManager
    from optimizationengine import OptimizationEngine
```


# Installation (CPDv2.1, WSLv1.2.3)
(For Cloud Pak for Data v2.1 or Watson Studio Local v 1.2.3)
Recommend to install in the `../packages/python` folder by running the following in a notebook cell: <br>
Regular install:
```
!pip install dse-do-utils --target='../packages/python'
```
Force a released version to ensure compatibility (advised):
```
!pip install dse-do-utils==0.2.2.1 --target='../packages/python'
```
Force a clean re-install of a released version:
```
!pip install --force-reinstall dse-do-utils==0.2.2.1 --target='../packages/python' --upgrade
```

Install from TestPyPI (deprecated, version on TestPyPI is not updated):
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

