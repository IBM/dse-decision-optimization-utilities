# DSE_DO_Utils
Decision Optimization utilities for IBM Watson Studio projects.

This repository contains:
1. A package `dse_do_utils`. This can be installed using pip.
2. A module `dse_do_utils_module/dse_do_utils.py`. Same code as package, but bundled in a single module file.
3. Misc modules.

## Package
Package is intended to be installable from pip.
Currently, this package is here to test Python packaging and installing via GitHub.
The package is in the folder `dse_do_utils`.
Installation in WSL:
1. Generate a Personal Access Token in IBM GitHub.<br>
Settings->Developper Settings->Personal access tokens.<br>
Generate new token. Use default settings, i.e. do not add any privileges (no need).

2. In notebook use
`!pip install 'git+https://<username>:<accesstoken>@github.ibm.com/vterpstra/DSE_DO_Utils.git#egg=DSE_DO_Utils' --upgrade pip`<br>
Where `<username>` = `vterpstra%40us.ibm.com` if email is `vterpstra@us.ibm.com`<br>
Example of `<accesstoken>` = `a1234a5a6abc78abcdefgh901a234567a89a01f2` (Not a real access token)<br>

For an example, see the notebook `GitHub_Package_Install` in https://github.ibm.com/vterpstra/DSX_Code_Reuse_Test:
https://github.ibm.com/vterpstra/DSX_Code_Reuse_Test/blob/master/jupyter/GitHub_Package_Install.jupyter.ipynb

## Module
The file `dse_do_utils.py` bundles all definitions from the package in a single module.
Copy-and-paste the contents into a WSL script and import
For now, this is the reference implementation.

For an example, see the notebook `Reuse_From_Local_Library` in https://github.ibm.com/vterpstra/DSX_Code_Reuse_Test:
https://github.ibm.com/vterpstra/DSX_Code_Reuse_Test/blob/master/jupyter/Reuse_From_Local_Library.jupyter.ipynb

## Misc
Other modules. In particular:
* `map_manager`: Utility for making folium maps. Since it requires installation of folium (which is not installed in WSL by default), this code is kept out of the regular dse_do_utils.

