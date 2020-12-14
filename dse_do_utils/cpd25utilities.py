# Copyright IBM All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

# -----------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------
# Utility functions for CPD v2.5
# -----------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------

import os


def add_file_path_as_data_asset_cpd25(file_path: str, asset_name: str = None) -> None:
    """Add a data file to the Watson Studio project.
    Applies to CPDv2.5. Works for any file. Allows the file to be viewed and downloaded from Watson Studio UI.
    Needs to be called after the file has been saved regularly in the file system.
    Typically, that would be in `/project_data/data_asset/`.
    Ensures the file is visible in the Data Assets of the Watson Studio UI.

    Usage::

        # Write some file as an example:
        file_path = '/project_data/data_asset/myfile.csv'
        with open(file_path, 'w+') as f:
             f.write("Hello World")
        # Add file as a data asset:
        add_file_as_data_asset_cpd25(file_path)

    Beware that the same data now exists in 2 different places:
        * In the Cloud Object Storage (COS)
        * As a file in `/project_data/data_asset/`

    Changing any of the 2 independently can cause inconsistencies.

    Args:
        file_path (str): full file path, including the file name and extension
        asset_name (str): name of data asset. Default is None. If None, the asset_name will be extracted from the file_path.
    """
    if asset_name is None:
        asset_name = os.path.basename(file_path)
    with open(file_path, 'rb') as f:
        from project_lib import Project
        project = Project.access()
        project.save_data(file_name=asset_name, data=f, overwrite=True)


def add_file_as_data_asset_cpd25(file_name: str) -> None:
    """Adds a file located in `/project_data/data_asset/` as a Data Asset to the Watson Studio project.
    So that it appears in the UI and can be exported.

    Args:
        file_name (str): name of file, including extension
    """
    file_path = os.path.join('/project_data/data_asset/', file_name)
    with open(file_path, 'rb') as f:
        from project_lib import Project
        project = Project.access()
        project.save_data(file_name=file_name, data=f, overwrite=True)


def write_data_asset_as_file_cpd25(asset_name: str, path: str = '/project_data/data_asset/') -> str:
    """Writes a named data asset to file.
    Assumes a data asset with `asset_name` exists.
    Makes the file accessible for things like:

        * Load from disk
        * Pip install
        * Module import

    Args:
        asset_name (str): name of the asset
        path (str, Optional): Default is '/project_data/data_asset/'. Use path='' for current directory.
    """
    from project_lib import Project
    project = Project.access()
    file_path = os.path.join(path, asset_name)
    with open(file_path, "wb") as f:
        f.write(project.get_file(asset_name).read())
    return file_path


def write_data_asset_as_file_wsc(asset_name: str, path: str = '/home/dsxuser/work/', project=None) -> str:
    """Writes a named data asset to file (for WS Cloud).
    Assumes a data asset with `asset_name` exists.
    Makes the file accessible for things like:

        * Load from disk
        * Pip install
        * Module import

    Args:
        asset_name (str): name of the asset
        path (str, Optional): Default (for WS Cloud) is '/home/dsxuser/work/'. Use path='' for current directory.
        project (project_lib.Project): required for WS Cloud. For CPD, leave as None.
    """
    if project is None:
        from project_lib import Project
        project = Project.access()
    file_path = os.path.join(path, asset_name)
    with open(file_path, "wb") as f:
        f.write(project.get_file(asset_name).read())
    return file_path


def add_file_path_as_data_asset_wsc(file_path: str, asset_name: str = None, project=None) -> None:
    """Add a data file to the Watson Studio project.
    Applies to WS Cloud and CPDv2.5. Works for any file. Allows the file to be viewed and downloaded from Watson Studio UI.
    Needs to be called after the file has been saved regularly in the file system.
    Typically, that would be in:

        * CPDv2.5: `/project_data/data_asset/`
        * WS Cloud: `/home/dsxuser/work/`, or `os.environ['PWD']`, or `./`, or no path

    Ensures the file is visible in the Data Assets of the Watson Studio UI.

    Args:
        project (project_lib.Project): required for WS Cloud
        file_path (str): full file path, including the file name and extension
        asset_name (str): name of data asset. Default is None. If None, the asset_name will be extracted from the file_path.

    Usage::

        # Write some file as an example:
        file_path = '/project_data/data_asset/myfile.csv'
        with open(file_path, 'w+') as f:
             f.write("Hello World")
        # Add file as a data asset:
        add_file_as_data_asset_cpd25(file_path)
    """
    if project is None:
        from project_lib import Project
        project = Project.access()
    if asset_name is None:
        asset_name = os.path.basename(file_path)
    with open(file_path, 'rb') as f:
        project.save_data(file_name=asset_name, data=f, overwrite=True)
