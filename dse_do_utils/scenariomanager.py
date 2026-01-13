# Copyright IBM All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

# -----------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------
# ScenarioManager - for CPD4.0 using decision_optimization_client instead of dd_scenario
# -----------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------
import os
import glob
import pathlib
import zipfile
import tempfile

import docplex
import pandas as pd
from typing import Sequence, List, Dict, Tuple, Optional, Union

#  Typing aliases
from dse_do_utils.utilities import convert_size
from pathlib import Path

Inputs = Dict[str, pd.DataFrame]
Outputs = Dict[str, pd.DataFrame]
InputsOutputs = Tuple[Inputs, Outputs]

# Platform
# Different platform require different approaches for writing data assets
# ScenarioManager will try to detect platform automatically. However, these tests are sensitive and un-supported.
# Therefore, to allow better control and avoid dependency on underlying conditions, user can explicitly set the platform
import enum
class Platform(enum.Enum):
    CPDaaS = 1  # As of Nov 2021, CPDaaS uses project_lib
    CPD40 = 2  # CPD 4.0 uses ibm_watson_studio_lib
    CPD25 = 3  # CPD 2.5-3.5 uses project_lib (but differently from CPDaaS)  Support has been deprecated since v0.5.8
    Local = 4


class ScenarioManager(object):
    """
    A ScenarioManager is responsible for loading and storing the input and output DataFrame dictionaries.
    The data can be loaded from and stored into:

        * A DO scenario
        * An Excel spreadsheet
        * A set of csv files

    Excel. Stores one DataFrame per sheet. Creates a `__index__` sheet that keeps track which DataFrame
    is input or output, and it restores table names that longer than the maximum of 31 in Excel.

    Usage 1 - Load data from Excel and store into DO scenario.
    Assumes DO model `MyModel` and an Excel file `datasets/MyExcelFile.xlsx` exists.
    The scenario will be created if it doesn't exist or otherwise gets overwritten::

        sm = ScenarioManager(model_name='MyModel, scenario_name='Scenario_1)
        inputs, outputs = sm.load_data_from_excel('MyExcelFile')
        sm.write_data_into_scenario()

    Usage 2 - Load data from DO scenario.
    Assumes DO model `MyModel` and scenario exists. Typical use in a `#dd-ignore` cell in a solves notebook::

        sm = ScenarioManager(model_name='MyModel, scenario_name='Scenario_1)
        inputs, outputs = sm.load_data_from_scenario()

    Usage 3 - Load data from all csv files in datasets into Excel.<br>
    Stores into `/datasets/excel_test.xlsx`.::

        excel_output_file_name = 'excel_test'
        csv_directory = os.path.join(os.environ['DSX_PROJECT_DIR'], 'datasets')
        sm = ScenarioManager()
        inputs, outputs = sm.load_data_from_csv(csv_directory)
        sm.write_data_to_excel(excel_output_file_name)

    Usage 4 - Load data from Excel and store into Excel.
    Assumes Excel file `datasets/MyExcelFile.xlsx` exists.
    Will create a file `datasets/MyExcelFileOutput.xlsx`.::

        sm = ScenarioManager()
        inputs, outputs = sm.load_data_from_excel('MyExcelFile')
        # Do something with the inputs or outputs
        sm.write_data_to_excel('MyExcelFileOutput')

    """

    def __init__(self, model_name: Optional[str] = None, scenario_name: Optional[str] = None,
                 local_root: Optional[Union[str, Path]] = None,
                 project_token: Optional[str] = None, wslib=None,
                 template_scenario_name: Optional[str] = None, platform: Optional[Platform] = None,
                 inputs: Inputs = None, outputs: Outputs = None,
                 local_relative_data_path: str = 'assets/data_asset', data_directory: Optional[Union[str, Path]] = None,
                 ):
        """Create a ScenarioManager.

        Template_scenario_name: name of a scenario with an (empty but) valid model that has been successfully run at least once.
        When creating a new scenario, will copy the template scenario. This ensures the new scenario can be updated with output generated from running the Jupyter notebook.
        This is a work-around for the problem that the DO Experiment will not show outputs updated/generated from a notebook unless the scenario has at least been solved successfully once.

        The way files are added as data assets in CPD/CPDaaS is different for different platforms and has been changing frequently with newer versions.
        The ScenarioManager will try and detect the platform to choose the appropriate method.
        However, these checks are sensitive and not supported by the platform.
        Therefore, the ScenarioManager allows explicit control via the argument `platform`.
        Valid choices are: `CPDaaS`, `CPD40`,  and `Local` (`CPD25` is deprecated)

        To specify project_token or wslib: only one of the two is needed. See https://dataplatform.cloud.ibm.com/docs/content/wsj/analyze-data/ws-lib-python.html?context=cpdaas

        Args:
            model_name (str):
            scenario_name (str):
            local_root (str): Path of root when running on a local computer
            project_token (str): When running in WS Cloud/CPDaaS, the project token to get wslib.
            wslib: alternative for project_token for WS Cloud
            template_scenario_name (str): If scenario doesn't exist: create new one. If template_scenario_name is specified, use that as template.
            platform (Platform): Optionally control the platform (`CPDaaS`, `CPD40`, and `Local`). If None, will try to detect automatically.
            local_relative_data_path (str): relative directory from the local_root. Used as default data_directory
            data_directory (str): Full path of data directory. Will override the platform dependent process.
        """
        self.model_name = model_name
        self.scenario_name = scenario_name
        self.local_root = local_root
        # self.project_id = project_id
        # self.project_access_token = project_access_token
        # self.project = project
        self.project_token = project_token
        self.wslib = wslib
        self.inputs = inputs
        self.outputs = outputs
        self.template_scenario_name = template_scenario_name
        self.local_relative_data_path = local_relative_data_path
        self.data_directory = data_directory
        if platform is None:
            platform = ScenarioManager.detect_platform()
        self.platform = platform

    # def __init__(self, model_name: Optional[str] = None, scenario_name: Optional[str] = None, local_root: Optional[str] = None):
    #     self.model_name = model_name
    #     self.scenario_name = scenario_name
    #     self.local_root = local_root
    #     self.inputs = None
    #     self.outputs = None

    def load_data(self, load_from_excel=False, excel_file_name=None):
        """Load data from either the DO scenario, or an Excel spreadsheet.
        The Excel spreadsheet is expected to be in the `datasets` folder, either in WS or local.

        Returns:
            inputs, outputs (tuple of dicts): the inputs and outputs dictionary of DataFrames
        """
        if load_from_excel:
            self.inputs, self.outputs = self.load_data_from_excel(excel_file_name)
        else:
            scenario = ScenarioManager.get_do_scenario(self.model_name, self.scenario_name)
            self.inputs, self.outputs = self.load_data_from_scenario_s(scenario)
        return self.inputs, self.outputs

    def get_data_directory(self) -> str:
        """Returns the path to the datasets folder.

        :return: path to the datasets folder
        """
        # Added in v0.5.4.3 to force the data_directory on any platform, e.g. when using StorageVolumes
        if self.data_directory is not None:
            return self.data_directory

        if self.platform == Platform.CPDaaS:
            data_dir = os.environ['PWD']  # '/home/wsuser/work' or use os.environ['PWD']
        elif self.platform == Platform.CPD40:
            from ibm_watson_studio_lib import access_project_or_space
            wslib = access_project_or_space()
            data_dir = wslib.mount.get_base_dir()
        elif self.platform == Platform.CPD25:
            # Note that the data dir in CPD25 is not an actual real directory and is NOT in the hierarchy of the JupyterLab folder
            data_dir = '/project_data/data_asset'  # Do NOT use the os.path.join!
        elif self.platform == Platform.Local:
            if self.local_root is None:
                raise ValueError('The local_root should be specified if loading from a file from outside of Watson Studio')
            data_dir = os.path.join(self.local_root, self.local_relative_data_path)
        else:  # TODO: get_root_directory requires updates
            data_dir = os.path.join(self.get_root_directory(), self.local_relative_data_path)
        return data_dir

    def get_root_directory(self) -> str:
        """Return the root directory of the file system.
        If system is WS, it will return the DSX root, otherwise the directory specified in the local_root.
        Raises:
            ValueError if root directory doesn't exist.

        TODO: review the options other than Local
        """
        if self.platform == Platform.CPDaaS:
            root_dir = '.'  # '/home/wsuser/work' or use os.environ['PWD']
        elif self.platform == Platform.CPD40:
            root_dir = "/userfs"
        elif self.platform == Platform.CPD25:
            root_dir = '.'  # Do NOT use the os.path.join!
        elif self.platform == Platform.Local:
            if self.local_root is None:
                raise ValueError('The local_root should be specified if loading from a file from outside of Watson Studio')
            root_dir = self.local_root
        else:
            root_dir = '.'

        # if ScenarioManager.env_is_cpd25():
        #     root_dir = '.'
        # elif ScenarioManager.env_is_dsx():  # Note that this is False in DO! So don't run in DO
        #     root_dir = os.environ['DSX_PROJECT_DIR']
        # else:
        #     if self.local_root is None:
        #         raise ValueError('The local_root should be specified if loading from a file from outside of WS')
        #     root_dir = self.local_root

        # Assert that root_dir actually exists
        if not os.path.isdir(root_dir):
            raise ValueError("Root directory `{}` does not exist.".format(root_dir))
        return root_dir

    # def add_data_file_using_project_lib(self, file_path: str, file_name: Optional[str] = None) -> None:
    #     #     """Add a data file to the Watson Studio project.
    #     #     Applies to CP4Dv2.5 and WS Cloud/CP4DaaS
    #     #     Needs to be called after the file has been saved regularly in the file system in
    #     #     `/project_data/data_asset/` (for CPD2.5) or `/home/wsuser/work/` in CPDaaS.
    #     #     Ensures the file is visible in the Data Assets of the Watson Studio UI.
    #     #
    #     #     Args:
    #     #         file_path (str): full file path, including the file name and extension
    #     #         file_name (str): name of data asset. Default is None. If None, the file-name will be extracted from the file_path.
    #     #     """
    #     #     # Add to Project
    #     #     if self.project is None:
    #     #         from project_lib import Project
    #     #         self.project = Project.access()
    #     #     if file_name is None:
    #     #         file_name = os.path.basename(file_path)
    #     #     with open(file_path, 'rb') as f:
    #     #         self.project.save_data(file_name=file_name, data=f, overwrite=True)

    def add_data_file_using_ws_lib(self, file_path: str, file_name: Optional[str] = None) -> None:
        """Add a data file to the Watson Studio project using the ibm_watson_studio_lib .
        Applies to CP4Dv4.0 and CP4DSaaS
        TODO: where should the file be written?
        Needs to be called after the file has been saved regularly in the file system in
        `/project_data/data_asset/` (for CPD2.5) or `/home/wsuser/work/` in WS Cloud.
        Ensures the file is visible in the Data Assets of the Watson Studio UI.

        Args:
            file_path (str): full file path, including the file name and extension
            file_name (str): name of data asset. Default is None. If None, the file-name will be extracted from the file_path.
        """
        # Add to Project
        if file_name is None:
            file_name = os.path.basename(file_path)

        with open(file_path, 'rb') as f:
            # from ibm_watson_studio_lib import access_project_or_space
            # wslib = access_project_or_space()
            wslib = self.get_wslib()
            wslib.save_data(asset_name_or_item=file_name, data=f.read(), overwrite=True)

        # Notes:
        # * wslib.upload_file(file_path=file_path, file_name=file_name, overwrite=True) CANNOT(!) overwrite an existing asset
        # * Unlike with project_lib, we need to do a f.read()
        # * ibm_watson_studio_lib is not (yet?) available in CPDaaS, but if so similar to project_lib it may need a handle to the self.project. Thus this non-static method.

    def get_wslib(self):
        """Returns the wslib object for the project.

        If already set in the constructor, returns that.
        Otherwise, creates it using the project_token or wslib.

        Returns:
            wslib object
        """
        if self.wslib is not None:
            return self.wslib
        else:
            from ibm_watson_studio_lib import access_project_or_space
            if self.project_token is not None:
                wslib = access_project_or_space({'token': self.project_token})
            else:
                wslib = access_project_or_space()
            return wslib

    @staticmethod
    def add_data_file_using_ws_lib_s(file_path: str, file_name: Optional[str] = None) -> None:
        """Add a data file to the Watson Studio project using the ibm_watson_studio_lib .
        Applies to CP4Dv4.0 only
        TODO: can probably be replaced by more generic, non-static, add_data_file_using_ws_lib().
        Needs to be called after the file has been saved regularly in the file system in
        `/project_data/data_asset/` (for CPD2.5) or `/home/dsxuser/work/` in WS Cloud.
        Ensures the file is visible in the Data Assets of the Watson Studio UI.

        Args:
            file_path (str): full file path, including the file name and extension
            file_name (str): name of data asset. Default is None. If None, the file-name will be extracted from the file_path.
        """
        # Add to Project
        if file_name is None:
            file_name = os.path.basename(file_path)

        with open(file_path, 'rb') as f:
            from ibm_watson_studio_lib import access_project_or_space
            wslib = access_project_or_space()
            wslib.save_data(asset_name_or_item=file_name, data=f.read(), overwrite=True)

        # Note that wslib.upload_file(file_path=file_path, file_name=file_name, overwrite=True) CANNOT(!) overwrite an existing asset
        # Unlike with project_lib, we need to do a f.read()


    # @staticmethod
    # def add_data_file_to_project_s(file_path: str, file_name: Optional[str] = None) -> None:
    #     """DEPRECATED: will never work on CP4DaaS since it requires the project_lib.Project
    #     Add a data file to the Watson Studio project.
    #     Applies to CP4Dv2.5.
    #     Needs to be called after the file has been saved regularly in the file system in `/project_data/data_asset/`.
    #     Ensures the file is visible in the Data Assets of the Watson Studio UI.
    #
    #     Args:
    #         file_path (str): full file path, including the file name and extension
    #         file_name (str): name of data asset. Default is None. If None, the file-name will be extracted from the file_path.
    #     """
    #     # Add to Project
    #     if file_name is None:
    #         file_name = os.path.basename(file_path)
    #
    #     with open(file_path, 'rb') as f:
    #         from project_lib import Project
    #         project = Project.access()
    #         project.save_data(file_name=file_name, data=f, overwrite=True)

    # -----------------------------------------------------------------
    # Read and write from/to DO scenario - value-added
    # -----------------------------------------------------------------
    def load_data_from_scenario(self) -> InputsOutputs:
        """Loads the data from a DO scenario"""
        self.inputs, self.outputs = self.load_data_from_scenario_s(self.model_name, self.scenario_name)
        return self.inputs, self.outputs

    def write_data_into_scenario(self):
        """Writes the data into a DO scenario. Create new scenario and write data."""
        return self.write_data_into_scenario_s(self.model_name, self.scenario_name, self.inputs, self.outputs, self.template_scenario_name)
    # def write_data_into_scenario(self):
    #     """Writes the data into a DO scenario. Create new scenario and write data."""
    #     return self.write_data_into_scenario_s(self.model_name, self.scenario_name, self.inputs, self.outputs)

    def add_data_into_scenario(self, inputs=None, outputs=None):
        """Adds data to a DO scenario. If table exists, does an overwrite/replace."""
        return ScenarioManager.add_data_into_scenario_s(self.model_name, self.scenario_name, inputs, outputs)

    def replace_data_in_scenario(self, inputs=None, outputs=None):
        """Replaces all input, output or both.
        Note: you will need to specify the inputs or outputs you want to replace explicitly as input arguments.
        It will NOT get them from self.inputs or self.outputs!
        In this way, you can control which to update. E.g. after a solve, only update the outputs, not the inputs.
        """
        return self.replace_data_into_scenario_s(self.model_name, self.scenario_name, inputs, outputs)

    def update_solve_output_into_scenario(self, mdl, outputs):
        """Replaces all output and KPIs table in the scenario.

        Assumes the scenario exists.
        Will not change the inputs of the scenario.
        Generates the KPI table.

        Limitations:
            * Does NOT update the objective
            * Does NOT update the log

        Args:
            mdl (docplex.mp.model): the model that has been solved
            outputs (Dict): dictionary of DataFrames
        """
        outputs['kpis'] = ScenarioManager.get_kpis_table_as_dataframe(mdl)
        self.outputs = outputs  # Not necessary for the update!
        self.replace_data_in_scenario(inputs=None, outputs=outputs)

    # -----------------------------------------------------------------
    # Read and write from/to DO scenario - base functions
    # -----------------------------------------------------------------
    def get_do_scenario(self, model_name, scenario_name):
        """Returns a DO scenario.

        Args:
            model_name (str): the name of the DO model
            scenario_name (str): the name of the scenario

        Returns:
            A dd-scenario.Container of type `scenario`

        Raises:
            ValueError: When either the model_name or the scenario_name doesn't match an existing entity.
        """
        client = ScenarioManager.get_dd_client(self)
        dd_model_builder = client.get_experiment(name=model_name)
        if dd_model_builder is None:
            raise ValueError('No DO model with name `{}` exists'.format(model_name))
        scenario = dd_model_builder.get_scenario(name=scenario_name)
        if scenario is None:
            raise ValueError('No DO scenario with name `{}` exists in model `{}`'.format(scenario_name, model_name))
        return scenario

    # @staticmethod
    def load_data_from_scenario_s(self, model_name: str, scenario_name: str) -> InputsOutputs:
        """Loads the data from a DO scenario.
        Returns empty dict if no tables."""
        # scenario = ScenarioManager.get_do_scenario(model_name, scenario_name)
        scenario = self.get_do_scenario(model_name, scenario_name)
        # Load all input data as a map { data_name: data_frame }
        inputs = scenario.get_tables_data(category='input')
        outputs = scenario.get_tables_data(category='output')
        return (inputs, outputs)

    # @staticmethod
    def write_data_into_scenario_s(self, model_name: str, scenario_name: str,
                                   inputs: Optional[Inputs] = None,
                                   outputs: Optional[Outputs] = None,
                                   template_scenario_name: Optional[str] = None) -> None:
        """Create new scenario and write data.

        If scenario exists: clears all existing data.
        If scenario doesn't exists: create new one. If template_scenario_name is specified, use that as template.
        If the existing scenario has a model, it keeps the model.
        If there is no existing scenario, the user needs to add a model manually in DO.
        Tested: works reliably.

        TODO: one small issue: if scenario exists and has been solved before, it clears all inputs and outputs
        (including the KPIs), but not the objective value. The DO UI shows as if the model has been solved.
        """
        # Create scenario
        client = ScenarioManager.get_dd_client(self)
        dd_model_builder = client.get_experiment(name=model_name)
        if dd_model_builder is None:
            raise ValueError('No DO model with name `{}` exists'.format(model_name))
        scenario = ScenarioManager.create_new_scenario(client, dd_model_builder, new_scenario_name=scenario_name,
                                                       template_scenario_name=template_scenario_name)

        if inputs is not None:
            for table in inputs:
                scenario.add_table_data(table, inputs[table], category='input')
        if outputs is not None:
            for table in outputs:
                scenario.add_table_data(table, outputs[table], category='output')

    # @staticmethod
    def add_data_into_scenario_s(self, model_name: str, scenario_name: str,
                                 inputs: Optional[Inputs] = None,
                                 outputs: Optional[Outputs] = None) -> None:
        """Adds tables in existing scenario.

        Replaces table, if table exists.
        Assumes scenario exists. Does not explicitly clear existing tables.
        Could be used in post-processing.
        """
        scenario = self.get_do_scenario(model_name, scenario_name)
        if inputs is not None:
            for table in inputs:
                scenario.add_table_data(table, inputs[table], category='input')
        if outputs is not None:
            for table in outputs:
                scenario.add_table_data(table, outputs[table], category='output')

    # @staticmethod
    def replace_data_into_scenario_s(self, model_name: str, scenario_name: str,
                                     inputs: Optional[Inputs] = None,
                                     outputs: Optional[Outputs] = None) -> None:
        """Replaces all input, output or both.

        If input/output are not None, clears inputs/outputs first
        Assumes scenario exists. Does explicitly clear all existing input/output tables.
        """
        client = self.get_dd_client()
        scenario = self.get_do_scenario(model_name, scenario_name)
        if inputs is not None:
            ScenarioManager.clear_scenario_data(client, scenario, category='input')
            for table in inputs:
                scenario.add_table_data(table, inputs[table], category='input')
        if outputs is not None:
            ScenarioManager.clear_scenario_data(client, scenario, category='output')
            for table in outputs:
                scenario.add_table_data(table, outputs[table], category='output')

    # -----------------------------------------------------------------
    # Scenario operations
    # -----------------------------------------------------------------
    @staticmethod
    def clear_scenario_data(client, scenario, category=None):
        """Clears all input and output tables from a scenario.

        Current API requires the client.

        Args:
            client
            scenario
            category (string ['input','output']): If None, clears all tables.
        """
        for table in scenario.get_tables(category):
            client.delete_table(scenario, table)  # API on Client-only for now

    # TODO: test
    @staticmethod
    def create_new_scenario(client, model_builder, new_scenario_name: str, template_scenario_name=None):
        """
        Creates a new scenario from a template. The template is found either from the template_scenario_name,
        or if this is None, from the new_scenario_name. If a scenario with the new name already exists,
        all input and output tables are cleared. Thereby keeping the solve code.
        Creates a new blank scenario if a scenario with this name doesn't exist.

        Args:
            client (decision_optimization_client.Client): Client managing the DO model
            model_builder (decision_optimization_client.Experiment): The DO model
            new_scenario_name (str): Name for the new scenario
            template_scenario_name (str): Name of an existing scenario

        Returns:
            A decision_optimization_client.Container of type scenario
        Raises:
            ValueError: new_scenario_name is None
            ValueError: new_scenario_name is the same as template_scenario_name
        """
        if new_scenario_name is None: raise ValueError('The new_scenario_name cannot be None')
        if template_scenario_name is not None:
            if (new_scenario_name == template_scenario_name): raise ValueError(
                'The new_scenario_name `{}` must be different from the template_scenario_name `{}`'.format(
                    new_scenario_name, template_scenario_name))
            # Copy and clear data from template scenario
            template_scenario = model_builder.get_scenario(name=template_scenario_name)
            if template_scenario is not None:
                # Delete existing target scenario if it exists
                scenario = model_builder.get_scenario(name=new_scenario_name)
                if scenario is not None:
                    model_builder.delete_container(scenario)
                    # Copy scenario from template
                scenario = template_scenario.copy(new_scenario_name)
                # Clear the data in the scenario
                ScenarioManager.clear_scenario_data(client, scenario)
            else:
                raise ValueError(
                    "No scenario with template_scenario_name `{}` exists in model".format(template_scenario_name))
        else:
            # If scenario does not already exists: create a new blank scenario. Else: clear the data
            scenario = model_builder.get_scenario(name=new_scenario_name)
            if (scenario == None):
                # Create a new scenario (does not have solve code)
                scenario = model_builder.create_scenario(name=new_scenario_name)
            else:
                # Existing scenario probably already has solver code, so maintain that.
                ScenarioManager.clear_scenario_data(client, scenario)
        return scenario

    @staticmethod
    def get_kpis_table_as_dataframe(mdl) -> pd.DataFrame:
        """Return a DataFrame with the KPI names and values in the mdl.
        This table is compatible with the representation in DO4WS and can be updated in the scenario.

        Args:
            mdl (docplex.mp.model.Model)

        Returns:
            pd.DataFrame with columns NAME and VALUE: the KPIs in the mdl

        """
        if mdl.solution is not None:
            all_kpis = [(kp.name, kp.compute()) for kp in mdl.iter_kpis()]
        else:
            all_kpis = []
        df_kpis = pd.DataFrame(all_kpis, columns=['NAME', 'VALUE'])
        return df_kpis

    # def get_input_output_data(self):
    #     """Returns the loaded input and output data as dictionaries of DataFrames.
    #     Can also be accessed as `inputs` and `outputs` properties of the ScenarioManager. """
    #     return self.inputs, self.outputs

    # -----------------------------------------------------------------
    # Read and write from/to Excel - value added-functions
    # -----------------------------------------------------------------
    def load_data_from_excel(self, excel_file_name: str) -> InputsOutputs:
        """Load data from an Excel file located in the `datasets` folder of the root directory.
        Convenience method.
        If run not on WS, requires the `root_dir` property passed in the ScenarioManager constructor
        """
        if pathlib.Path(excel_file_name).suffix == '.xlsx':
            file_name = excel_file_name
        else:
            file_name = excel_file_name + '.xlsx'

        if self.platform == Platform.CPDaaS:
            # VT_20260113: since v0.5.8, use wslib to load the data asset in CPDaaS (instead of project_lib)
            wslib = self.get_wslib()
            buffer = wslib.load_data(excel_file_name)
            xl = pd.ExcelFile(buffer)
        else:
            datasets_dir = self.get_data_directory()
            excel_file_path = os.path.join(datasets_dir, file_name)
            xl = pd.ExcelFile(excel_file_path)

        # Read data from Excel
        self.inputs, self.outputs = ScenarioManager.load_data_from_excel_s(xl)
        return self.inputs, self.outputs

    # def load_data_from_excel(self, excel_file_name: str) -> InputsOutputs:
    #     """Load data from an Excel file located in the `datasets` folder of the root directory.
    #     Convenience method.
    #     If run not on WS, requires the `root_dir` property passed in the ScenarioManager constructor
    #     """
    #     # root_dir = self.get_root_directory()
    #     datasets_dir = self.get_data_directory()
    #     excel_file_path = os.path.join(datasets_dir, excel_file_name + '.xlsx')
    #     xl = pd.ExcelFile(excel_file_path)
    #     # Read data from Excel
    #     self.inputs, self.outputs = ScenarioManager.load_data_from_excel_s(xl)
    #     return self.inputs, self.outputs

    def write_data_to_excel(self, excel_file_name: str = None, unique_file_name: bool = True, copy_to_csv: bool = False) -> str:
        """Write inputs and/or outputs to an Excel file in datasets.
        The inputs and outputs as in the attributes `self.inputs` and `self.outputs` of the ScenarioManager

        If the excel_file_name is None, it will be generated from the model_name and scenario_name: MODEL_NAME + "_" + SCENARIO_NAME + "_output"

        If Excel has a file with the same name opened, it will throw a PermissionError.
        If so and the flag `unique_file_name` is set to True, it will save the new file with a unique name.
        I.e., if the file is not opened by Excel, the file is overwritten.

        Args:
            excel_file_name (str): The file name for the Excel file.
            unique_file_name (bool): If True, generates a unique file name in case the existing file is opened(!) by Excel
            copy_to_csv (bool): If true, will create a copy of the file with the extension `.csv`. DEPRECATED, NON-FUNCTIONAL
        Returns:
            excel_file_path (str): fill path of the exported Excel file
        """

        if excel_file_name is None:
            if self.model_name is not None and self.scenario_name is not None:
                excel_file_name = "{}_{}_output".format(self.model_name, self.scenario_name)
            else:
                raise ValueError("The argument excel_file_name can only be 'None' if both the model_name '{}' and the scenario_name '{}' have been specified.".format(self.model_name, self.scenario_name))

        # root_dir = self.get_root_directory()
        # Save the Excel file:
        if pathlib.Path(excel_file_name).suffix != '.xlsx':
            excel_file_name = excel_file_name + '.xlsx'

        data_dir = self.get_data_directory()
        excel_file_path_1 = os.path.join(data_dir, excel_file_name)
        if unique_file_name:
            try:
                writer_1 = pd.ExcelWriter(excel_file_path_1, engine='xlsxwriter')
            except PermissionError:
                excel_file_path_1 = self.get_unique_file_name(excel_file_path_1)
                writer_1 = pd.ExcelWriter(excel_file_path_1, engine='xlsxwriter')
        else:
            writer_1 = pd.ExcelWriter(excel_file_path_1, engine='xlsxwriter')

        ScenarioManager.write_data_to_excel_s(writer_1, inputs=self.inputs, outputs=self.outputs)
        writer_1.close()  # .save()

        self.add_file_as_data_asset(excel_file_path_1, excel_file_name)

        # if self.platform == Platform.CPDaaS:
        #     self.add_data_file_using_project_lib(excel_file_path_1, excel_file_name + '.xlsx')
        # elif self.platform == Platform.CPD40:
        #     self.add_data_file_using_ws_lib(excel_file_path_1, excel_file_name + '.xlsx')
        # elif self.platform == Platform.CPD25:
        #     self.add_data_file_using_project_lib(excel_file_path_1, excel_file_name + '.xlsx')
        # # Save the csv copy (no longer supported in CPD25 because not necessary)
        # elif copy_to_csv:
        #     excel_file_path_2 = os.path.join(data_dir, excel_file_name + 'to_csv.xlsx')
        #     csv_excel_file_path_2 = os.path.join(data_dir, excel_file_name + '_xlsx.csv')
        #     writer_2 = pd.ExcelWriter(excel_file_path_2, engine='xlsxwriter')
        #     ScenarioManager.write_data_to_excel_s(writer_2, inputs=self.inputs, outputs=self.outputs)
        #     writer_2.save()
        #     os.rename(excel_file_path_2, csv_excel_file_path_2)
        return excel_file_path_1

    @staticmethod
    def get_unique_file_name(path):
        filename, extension = os.path.splitext(path)
        counter = 1

        while os.path.exists(path):
            path = filename + "(" + str(counter) + ")" + extension
            counter += 1

        return path

    def add_file_as_data_asset(self, file_path: str, asset_name: str = None):
        """Register an existing file as a data asset in CPD.

        :param file_path: full path of the file
        :param asset_name: name of asset. If None, will get the name from the file
        :return:
        """
        if asset_name is None:
            asset_name = os.path.basename(file_path)

        if self.platform in [Platform.CPDaaS]:
            self.add_data_file_using_ws_lib(file_path, asset_name)
        if self.platform in [Platform.CPD40]:
            # VT_20260113: for now keep this as is, but could be replaced by non-static add_data_file_using_ws_lib() to make it the same as CPDaaS.
            self.add_data_file_using_ws_lib_s(file_path, asset_name)
        elif self.platform in [Platform.CPD25]:
            raise NotImplementedError("The method add_file_as_data_asset is not implemented for CPD25. Support for CPD25 has been deprecated and has been removed.")
            # self.add_data_file_using_project_lib(file_path, asset_name)
        else:  # i.e Local: do not register as data asset
            pass

    # def add_file_as_data_asset(self, file_path: str, asset_name:str = None):
    #     """Register an existing file as a data asset in CPD.
    #
    #     :param file_path: full path of the file
    #     :param asset_name: name of asset. If None, will get the name from the file
    #     :return:
    #     """
    #     ScenarioManager.add_file_as_data_asset_s(file_path, asset_name, self.platform)



    @staticmethod
    def add_file_as_data_asset_s(file_path: str, asset_name: str = None, platform: Platform = None):
        """Register an existing file as a data asset in CPD.
        VT 2022-01-21: this method is incorrect for CPDaaS. Should use project_lib.

        :param file_path: full path of the file
        :param asset_name: name of asset. If None, will get the name from the file
        :param platform: CPD40, CPD25, CPSaaS, or Local. If None, will autodetect.
        :return:
        """
        if asset_name is None:
            asset_name = os.path.basename(file_path)
        if platform is None:
            platform = ScenarioManager.detect_platform()

        if platform in [Platform.CPD40, Platform.CPDaaS]:
            ScenarioManager.add_data_file_using_ws_lib_s(file_path)
        elif platform == Platform.CPD25:
            ScenarioManager.add_data_file_to_project_s(file_path, asset_name)
        else:  # i.e Local: do not register as data asset
            pass


    # -----------------------------------------------------------------
    # Read and write from/to Excel - base functions
    # -----------------------------------------------------------------
    @staticmethod
    def load_data_from_excel_s(xl: pd.ExcelFile, table_index_sheet: str = '_table_index_', input_table_names:List[str]=None, output_table_names:List[str]=None) -> InputsOutputs:
        """
        Create dataFrames from the sheets of the Excel file.
        Store in dictionary df_dict with table_name as key.
        The table_name is either the name of the sheet, or the table_name as defined in the table_index_sheet.

        In the default case, when the input_table_names or output_table_names are None, the category of the table
        (i.e. input or output) is driven off the value in the table_index_sheet.
        If not listed in table_index_sheet, it is placed in the inputs.

        However, to reduce the load time for certain applications, we can restrict the tables it loads by specifying them in
        the input_table_names or output_table_names. If one of them is not None, it wil only load those tables
        and categorize them accordingly.

        Note that if either input_table_names or output_table_names is used, if applicable, they would refer to
        the *translated* tables names by the table_index_sheet. (I.e. not the abbreviated names used in the sheet names.)

        Args:
            xl (pandas.ExcelFile): Excel file
            table_index_sheet (str): Name of table index sheet
            input_table_names (List[str]): names of input tables to read
            output_table_names (List[str]): names of output tables to read

        Returns:
            (Dict[str,DataFrame], Dict[str,DataFrame]): A tuple of inputs and outputs dictionaries of DataFrames,
                one df per sheet
        """
        # Check for table_index sheet:
        table_index_df = None
        if (table_index_sheet is not None) and (table_index_sheet in xl.sheet_names):
            table_index_df = xl.parse(table_index_sheet)
            table_index_df.set_index('sheet_name', inplace=True)

        # Load all sheets:
        inputs = {}
        outputs = {}
        for sheet in xl.sheet_names:
            if sheet != table_index_sheet:  # Do not load the table_index as a df_dict DataFrame
                table_name = sheet  # default if no abbreviation
                category = 'input'
                # Translate table_name if possible:
                if (table_index_df is not None):
                    if (sheet in table_index_df.index.values):
                        table_name = table_index_df.loc[sheet].table_name
                    if ('category' in table_index_df.columns.values):
                        category = table_index_df.loc[sheet].category

                if input_table_names is None and output_table_names is None:
                    # Categorize according to the table_index_sheet
                    if category == 'output':
                        outputs[table_name] = xl.parse(sheet)
                    else:
                        inputs[table_name] = xl.parse(sheet)
                else:
                    # Categorize according to the input/output_table_names
                    if input_table_names is not None and table_name in input_table_names:
                        inputs[table_name] = xl.parse(sheet)
                    elif output_table_names is not None and table_name in output_table_names:
                        outputs[table_name] = xl.parse(sheet)

                # Original code (before adding input/output_table_names)
                # if category == 'output':
                #     outputs[table_name] = xl.parse(sheet)
                # else:
                #     inputs[table_name] = xl.parse(sheet)
        return inputs, outputs


    # def load_data_from_excel_s(xl: pd.ExcelFile, table_index_sheet: str = '_table_index_') -> InputsOutputs:
    #     """
    #     Create dataFrames from the sheets of the Excel file.
    #     Store in dictionary df_dict with table_name as key.
    #     The table_name is either the name of the sheet, or the table_name as defined in the table_index_sheet.
    #     TODO: Test allow for distinction between input and output via the index-sheet
    #
    #     Args:
    #         xl (pandas.ExcelFile): Excel file
    #         table_index_sheet (str): Name of table index sheet
    #
    #     Returns:
    #         (Dict[str,DataFrame], Dict[str,DataFrame]): A tuple of inputs and outputs dictionaries of DataFrames,
    #             one df per sheet
    #     """
    #     # Check for table_index sheet:
    #     table_index_df = None
    #     if (table_index_sheet is not None) and (table_index_sheet in xl.sheet_names):
    #         table_index_df = xl.parse(table_index_sheet)
    #         table_index_df.set_index('sheet_name', inplace=True)
    #
    #     # Load all sheets:
    #     inputs = {}
    #     outputs = {}
    #     for sheet in xl.sheet_names:
    #         if sheet != table_index_sheet:  # Do not load the table_index as a df_dict DataFrame
    #             table_name = sheet  # default if no abbreviation
    #             category = 'input'
    #             # Translate table_name if possible:
    #             if (table_index_df is not None):
    #                 if (sheet in table_index_df.index.values):
    #                     table_name = table_index_df.loc[sheet].table_name
    #                 if ('category' in table_index_df.columns.values):  # TODO: test!
    #                     category = table_index_df.loc[sheet].category
    #
    #             if category == 'output':
    #                 outputs[table_name] = xl.parse(sheet)
    #             else:
    #                 inputs[table_name] = xl.parse(sheet)
    #     return inputs, outputs

    @staticmethod
    def _create_truncted_post_fixed_name(long_name: str, max_length: int, index: int) -> str:
        """Create a trunced name post-fixed with '_<index>' where the total length of the string <= max_length"""
        post_fix = '_' + str(index)
        return long_name[:max_length - len(post_fix)] + post_fix

    @staticmethod
    def _create_unique_abbreviated_name(long_name: str, max_length: int, existing_names: Sequence[str]) -> str:
        """Create a unique, abbreviated name such that it is not a member of the existing_names set.
        Name is made unique by post-fixing '_<index>' where index is an increasing integer, starting at 0
        """
        name = long_name
        if len(name) > max_length:
            name = ScenarioManager._create_truncted_post_fixed_name(long_name, max_length, 0)
        for index in range(1, 9999):
            if name in existing_names:
                name = ScenarioManager._create_truncted_post_fixed_name(long_name, max_length, index)
            else:
                break
        return name

    @staticmethod
    def write_data_to_excel_s(writer: pd.ExcelWriter,
                              inputs: Optional[Inputs] = None,
                              outputs: Optional[Outputs] = None,
                              table_index_sheet: str = '_table_index_') -> None:
        """Writes all dataframes in the inputs and outputs to the Excel writer, with sheet-names based on
        the keys of the inputs/outputs. Due to the Excel limitation of maximum 31 characters for the sheet-name,
        tables names longer than the 31 characters will be abbreviated with a unique name. The mapping between
        the original table-name and abbreviated name is recorded in a separate sheet named by the table_index_sheet.

        Args:
            writer (pandas.ExcelWriter): The Excel writer to write the file
            inputs (Dict of DataFrames): inputs
            outputs (Dict of DataFrames): outputs
            table_index_sheet (str): name for the index sheet
        """

        table_index = []  # to hold dicts with keys 'table_name', 'sheet_name', 'category' (`input` or `output`)
        sheet_names = set()

        if (inputs is not None) and (type(inputs) is dict):
            for table_name, df in inputs.items():
                # truncate table name to 31 characters due to sheet name limit in Excel:
                sheet_name = ScenarioManager._create_unique_abbreviated_name(table_name, 31,
                                                                             sheet_names)
                sheet_names.add(sheet_name)
                df = ScenarioManager.remove_timezone_from_datetime_columns(df)  # Remove timezone from datetime columns
                df.to_excel(writer, sheet_name, index=False)
                # Store row in table_index
                table_index.append({'table_name': table_name, 'sheet_name': sheet_name, 'category': 'input'})
        if (outputs is not None) and (type(outputs) is dict):
            for table_name, df in outputs.items():
                # truncate table name to 31 characters due to sheet name limit in Excel:
                sheet_name = ScenarioManager._create_unique_abbreviated_name(table_name, 31,
                                                                             sheet_names)
                sheet_names.add(sheet_name)
                df = ScenarioManager.remove_timezone_from_datetime_columns(df)  # Remove timezone from datetime columns
                df.to_excel(writer, sheet_name, index=False)
                # Store row in table_index
                table_index.append({'table_name': table_name, 'sheet_name': sheet_name, 'category': 'output'})

        # Add table_index sheet if applicable:
        if (len(table_index) > 0) & (table_index_sheet is not None):
            index_df = pd.DataFrame(table_index)
            index_df.to_excel(writer, table_index_sheet, index=False)

    @staticmethod
    def remove_timezone_from_datetime_columns(df: pd.DataFrame) -> pd.DataFrame:
        """Remove timezone from all datetime columns in a DataFrame.
        This is necessary for the Excel writer, which does not support timezone-aware datetime columns.

        Args:
            df (pd.DataFrame): DataFrame with datetime columns

        Returns:
            pd.DataFrame: DataFrame with timezone removed from datetime columns
        """
        for col in df.select_dtypes(include=['datetime64[ns, UTC]']).columns:
            df[col] = df[col].dt.tz_localize(None)
        return df
    # -----------------------------------------------------------------
    # Load data from csv
    # -----------------------------------------------------------------
    def load_data_from_csv(self, csv_directory: str,
                           input_csv_name_pattern: str = "*.csv",
                           output_csv_name_pattern: Optional[str] = None, **kwargs) -> InputsOutputs:
        """Load data from matching csv files in a directory.
        Uses glob.glob() to pattern-match files in the csv_directory.
        If you want to load one file, specify the full name including the `.csv` extension.

        Args:
            csv_directory (str): Relative directory from the root
            input_csv_name_pattern (str): name pattern to find matching csv files for inputs
            output_csv_name_pattern (str): name pattern to find matching csv files for outputs
            **kwargs: Set of optional arguments for the pd.read_csv() function
        """
        root_dir = self.get_root_directory()
        csv_full_directory = os.path.join(root_dir, csv_directory)
        # Read data
        self.inputs = {}
        self.outputs = {}
        if input_csv_name_pattern is not None:
            self.inputs = ScenarioManager.load_data_from_csv_s(csv_full_directory, input_csv_name_pattern, **kwargs)
        if output_csv_name_pattern is not None:
            self.outputs = ScenarioManager.load_data_from_csv_s(csv_full_directory, output_csv_name_pattern, **kwargs)
        return self.inputs, self.outputs

    @staticmethod
    def load_data_from_csv_s(csv_directory: str, csv_name_pattern: str = "*.csv", **kwargs) -> Dict[str, pd.DataFrame]:
        """Read data from all matching .csv files in a directory.

        Args:
            csv_directory (str): the full path of a directory containing one or more .csv files.
            csv_name_pattern (str): name pattern to find matching csv files
            **kwargs: Set of optional arguments for the pd.read_csv() function

        Returns:
            data: dict of DataFrames. Keys are the .csv file names.
        """
        inputs = {}
        # outputs = {}
        for file_path in glob.glob(
                os.path.join(csv_directory, csv_name_pattern)):  # os.path.join is safe for both Unix and Win
            # Read csv
            df = pd.read_csv(file_path, **kwargs)
            table_name = pathlib.Path(file_path).stem
            # head, tail = os.path.split(file_path)
            # table_name = tail[:-4]  # remove the '.csv'
            inputs[table_name] = df
        return inputs  # , outputs

    def write_data_to_csv(self) -> None:
        """Write inputs and/or outputs to .csv files in the root/datasets folder.

        Args: None
        Returns: None
        """
        # root_dir = self.get_root_directory()
        # csv_directory = os.path.join(root_dir, 'datasets')
        csv_directory = self.get_data_directory()
        ScenarioManager.write_data_to_csv_s(csv_directory, inputs=self.inputs, outputs=self.outputs)

    @staticmethod
    def write_data_to_csv_s(csv_directory: str,
                            inputs: Optional[Inputs] = None,
                            outputs: Optional[Outputs] = None) -> None:
        """Write data to .csv files in a directory. Name as name of DataFrame.

        Args:
            csv_directory (str): the full path of a directory for the .csv files.
            inputs (Dict of DataFrames): inputs
            outputs (Dict of DataFrames): outputs

        Returns: None
        """
        platform = ScenarioManager.detect_platform()
        if inputs is not None:
            for table_name, df in inputs.items():
                file_path = os.path.join(csv_directory, table_name + ".csv")
                print("Writing {}".format(file_path))
                df.to_csv(file_path, index=False)
                # ScenarioManager.add_file_as_data_asset_s(file_path, table_name + ".csv", platform=platform)
        if outputs is not None:
            for table_name, df in outputs.items():
                file_path = os.path.join(csv_directory, table_name + ".csv")
                print("Writing {}".format(file_path))
                df.to_csv(file_path, index=False)
                # ScenarioManager.add_file_as_data_asset_s(file_path, table_name + ".csv", platform=platform)

    # -----------------------------------------------------------------
    # Load data from parquet
    # -----------------------------------------------------------------
    def load_data_from_parquet(self, directory: str,
                               input_name_pattern: str = "*.parquet",
                               output_name_pattern: Optional[str] = None, **kwargs) -> InputsOutputs:
        """Load data from matching parquet files in a directory.
        Uses glob.glob() to pattern-match files in the directory.
        If you want to load one file, specify the full name including the `.parquet` extension.

        Args:
            directory (str): Relative directory from the root
            input_name_pattern (str): name pattern to find matching parquet files for inputs
            output_name_pattern (str): name pattern to find matching parquet files for outputs
            **kwargs: Set of optional arguments for the pd.read_parquet() function
        """
        root_dir = self.get_root_directory()
        full_directory = os.path.join(root_dir, directory)
        # Read data from parquet
        if input_name_pattern is not None:
            self.inputs = ScenarioManager.load_data_from_parquet_s(full_directory, input_name_pattern, **kwargs)
        if output_name_pattern is not None:
            self.outputs = ScenarioManager.load_data_from_parquet_s(full_directory, output_name_pattern, **kwargs)
        return self.inputs, self.outputs

    @staticmethod
    def load_data_from_parquet_s(directory: str, file_name_pattern: str = "*.parquet", **kwargs) -> Dict[str, pd.DataFrame]:
        """Read data from all matching .parquet files in a directory.

        Args:
            directory (str): the full path of a directory containing one or more .parquet files.
            file_name_pattern (str): name pattern to find matching parquet files
            **kwargs: Set of optional arguments for the pd.read_parquet() function

        Returns:
            data: dict of DataFrames. Keys are the .parquet file names.
        """
        inputs = {}
        for file_path in glob.glob(
                os.path.join(directory, file_name_pattern)):  # os.path.join is safe for both Unix and Win
            # Read parquet
            df = pd.read_parquet(file_path, **kwargs)
            table_name = pathlib.Path(file_path).stem
            inputs[table_name] = df
        return inputs

    def write_data_to_parquet(self, directory: str,
                          inputs: Optional[Inputs] = None,
                          outputs: Optional[Outputs] = None) -> None:
        """Write inputs and/or outputs to .parquet files in the target folder.

        Args:
            directory (str): Relative directory from the root
        Returns: None
        """
        root_dir = self.get_root_directory()
        directory_path = os.path.join(root_dir, directory)
        ScenarioManager.write_data_to_parquet_s(directory_path, inputs=inputs, outputs=outputs)

    @staticmethod
    def write_data_to_parquet_s(directory: str,
                                inputs: Optional[Inputs] = None,
                                outputs: Optional[Outputs] = None) -> None:
        """Write data to .parquet files in a directory. Name as name of DataFrame.

        Args:
            directory (str): the full path of a directory for the .parquet files.
            inputs (Dict of DataFrames): inputs
            outputs (Dict of DataFrames): outputs

        Returns: None
        """
        if inputs is not None:
            for table_name, df in inputs.items():
                file_path = os.path.join(directory, table_name + ".parquet")
                print("Writing input {}".format(file_path))
                df.to_parquet(file_path, index=False)
        if outputs is not None:
            for table_name, df in outputs.items():
                file_path = os.path.join(directory, table_name + ".parquet")
                print("Writing output {}".format(file_path))
                df.to_parquet(file_path, index=False)

    # -----------------------------------------------------------------
    # Read from / write to zipped set of csv files
    # -----------------------------------------------------------------
    @staticmethod
    def load_data_from_zip_csv_s(zip_file_path: str, file_size_limit: int = None, **kwargs) -> Dict[str, pd.DataFrame]:
        """Read data from a zip file with .csv files.

        Args:
            zip_file_path (str): the full path of a zip file containing one or more .csv files.
            file_size_limit (int): maximum file size in bytes. None implies no limit.
            **kwargs: Set of optional arguments for the pd.read_csv() function

        Returns:
            data: dict of DataFrames. Keys are the .csv file names.
        """
        inputs = {}

        with zipfile.ZipFile(zip_file_path, "r") as f:
            for csv_file in f.infolist():
                if pathlib.Path(csv_file.filename).suffix.lower() == '.csv':
                    table_name = pathlib.Path(csv_file.filename).stem
                    # print(f"Reading table = {table_name}. File-size = {convert_size(csv_file.file_size)}")
                    if file_size_limit is None or csv_file.file_size <= file_size_limit:
                        df = pd.read_csv(f.open(csv_file.filename), **kwargs)
                        inputs[table_name] = df
                        #print(f"Read {table_name}: {df.shape[0]} rows and {df.shape[1]} columns")
                    else:
                        pass
                        #print(f"Read {table_name}: skipped")

        return inputs

    @staticmethod
    def write_data_to_zip_csv_s(zip_file_path: str, inputs: Inputs = None, outputs: Outputs = None, **kwargs):
        """Write data as a zip file with .csv files.
        inputs and outputs dictionaries are merged and written in same zip.

        Args:
            zip_file_path (str): the full path of a zip file.
            inputs: dict of input DataFrames
            outputs: dict of input DataFrames
            **kwargs: Set of optional arguments for the df.to_csv() function

        Returns:
            None
        """
        dfs = {}
        if inputs is not None:
            dfs = {**dfs, **inputs}
        if outputs is not None:
            dfs = {**dfs, **outputs}
        with zipfile.ZipFile(zip_file_path, 'w') as zipMe:
            with tempfile.TemporaryDirectory() as tmpdir:
                for table_name, df in dfs.items():
                    filename =  table_name + ".csv"
                    file_path = os.path.join(tmpdir, filename)
                    # print(f"Write table {table_name}, rows = {df.shape[0]} as {file_path}")
                    df.to_csv(file_path, index=False, **kwargs)
                    zipMe.write(file_path, arcname=filename, compress_type=zipfile.ZIP_DEFLATED)

    # -----------------------------------------------------------------
    # Utils
    # -----------------------------------------------------------------
    @staticmethod
    def detect_platform() -> Platform:
        if ScenarioManager.env_is_wscloud():
            platform = Platform.CPDaaS
        elif ScenarioManager.env_is_cpd40():
            platform = Platform.CPD40
        # elif ScenarioManager.env_is_cpd25():
        #     platform = Platform.CPD25
        else:
            platform = Platform.Local
        return platform


    @staticmethod
    def env_is_cpd40() -> bool:
        """Return true if environment is CPDv4.0.2 and in particular supports ibm_watson_studio_lib to get access to data assets.

        Notes:
            - The `import from ibm_watson_studio_lib import access_project_or_space` does NOT fail in CPDaaS
            - The `wslib = access_project_or_space()` does fail in CPDaaS, however with an ugly error message
            - Current ugly work-around is to always first test for CPDaaS using the environment variable
            - TODO: prevent error/warning in CPDaaS
        """
        try:
            from ibm_watson_studio_lib import access_project_or_space
            wslib = access_project_or_space()
            wslib.mount.get_base_dir()
            is_cpd40 = True
        except:
            is_cpd40 = False
        return is_cpd40

    @staticmethod
    def env_is_dsx() -> bool:
        """Return true if environment is DSX"""
        return 'DSX_PROJECT_DIR' in os.environ

    @staticmethod
    def env_is_cpd25() -> bool:
        """Return true if environment is CPDv2.5"""
        return 'PWD' in os.environ

    @staticmethod
    def env_is_wscloud() -> bool:
        """Return true if environment is WS Cloud"""
        # return 'PWD' in os.environ and os.environ['PWD'] == '/home/wsuser/work'
        return 'RUNTIME_ENV_APSX_URL' in os.environ and os.environ['RUNTIME_ENV_APSX_URL'] == 'https://api.dataplatform.cloud.ibm.com'

    # def get_dd_client(self):
    #     """Return the Client managing the DO scenario.
    #     Returns: new decision_optimization_client.Client
    #     """
    #     from decision_optimization_client import Client
    #     if self.project is not None:
    #         pc = self.project.project_context
    #         return Client(pc=pc)
    #     elif (self.project_id is not None) and (self.project_access_token is not None):
    #         # When in WS Cloud:
    #         from project_lib import Project
    #         # The do_optimization project token is an authorization token used to access project resources like data sources, connections, and used by platform APIs.
    #         project = Project(project_id=self.project_id,
    #                           project_access_token=self.project_access_token)
    #         pc = project.project_context
    #         return Client(pc=pc)
    #     else:
    #         #  In WSL/CPD:
    #         return Client()

    def get_dd_client(self):
        """Return the Client managing the DO scenario.
        Returns: new decision_optimization_client.Client
        """
        from decision_optimization_client import Client
        # VT_20260113: the samples for CP4D on-prem show to also pass the wslib to the Client, but without the token
        wslib = self.get_wslib()
        return Client(wslib=wslib)

    def print_table_names(self) -> None:
        """Print the names of the input and output tables. For development and debugging."""
        print("Input tables: {}".format(", ".join(self.inputs.keys())))
        print("Output tables: {}".format(", ".join(self.outputs.keys())))


    def export_model_as_lp(self, mdl, model_name: Optional[str] = None) -> str:
        """Exports the model as an .lp file in the data assets.

        Args:
            mdl (docplex.mp.model): the docplex model
            model_name (str): name of model (excluding the `.lp`). If no model_name, it uses the `mdl.name`

        Returns:
            (str): full file path of lp file

        Note: now a method of ScenarioManager (instead of OptimizationEngine),
        so this can be included in a dd-ignore notebook cell. Avoids the dependency on dse-do-utils in the ModelBuilder.
        """
        # Get model name:
        if model_name is None:
            model_name = mdl.name
        datasets_dir = self.get_data_directory()
        lp_file_name = model_name + '.lp'
        lp_file_path = os.path.join(datasets_dir, lp_file_name)
        mdl.export_as_lp(lp_file_path)  # Writes the .lp file

        self.add_file_as_data_asset(lp_file_path, lp_file_name)
        # if self.platform == Platform.CPDaaS:
        #     self.add_data_file_using_project_lib(lp_file_path, lp_file_name)
        # elif self.platform == Platform.CPD40:
        #     self.add_data_file_using_ws_lib(lp_file_path)
        # elif self.platform == Platform.CPD25:
        #     self.add_data_file_using_project_lib(lp_file_path, lp_file_name)
        return lp_file_path

    def insert_scenarios_from_zip(self, filepath: str):
        """Insert (or replace) a set of scenarios from a .zip file into the DO Experiment.
        Zip is assumed to contain one or more .xlsx files. Others will be skipped.
        Name of .xlsx file will be used as the scenario name."""
        with zipfile.ZipFile(filepath, 'r') as zip_file:
            for info in zip_file.infolist():
                scenario_name = pathlib.Path(info.filename).stem
                file_extension = pathlib.Path(info.filename).suffix
                if file_extension == '.xlsx':
                    #                 print(f"file in zip : {info.filename}")
                    xl = pd.ExcelFile(zip_file.read(info))
                    self.inputs, self.outputs = ScenarioManager.load_data_from_excel_s(xl)
                    self.print_table_names()
                    self.write_data_into_scenario_s(self.model_name, scenario_name, self.inputs, self.outputs, self.template_scenario_name)
                    print(f"Uploaded scenario: '{scenario_name}' from '{info.filename}'")
                else:
                    print(f"File '{info.filename}' in zip is not a .xlsx. Skipped.")
