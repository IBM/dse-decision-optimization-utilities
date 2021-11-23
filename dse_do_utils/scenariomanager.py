# Copyright IBM All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

# -----------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------
# ScenarioManager - for CPD4.0 using decision_optimization_client instead of dd_scenario
# -----------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------
import os
import glob

import docplex
import pandas as pd
from typing import Sequence, List, Dict, Tuple, Optional

#  Typing aliases
Inputs = Dict[str, pd.DataFrame]
Outputs = Dict[str, pd.DataFrame]
InputsOutputs = Tuple[Inputs, Outputs]


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
                 local_root: Optional[str] = None, project_id: Optional[str] = None, project_access_token: Optional[str] = None, project=None,
                 template_scenario_name: Optional[str] = None):
        """Create a ScenarioManager.

        Template_scenario_name: name of a scenario with an (empty but) valid model that has been successfully run at least once.
        When creating a new scenario, will copy the template scenario. This ensures the new scenario can be updated with output generated from running the Jupyter notebook.
        This is a work-around for the problem that the DO Experiment will not show outputs updated/generated from a notebook unless the scenario has at least been solved successfully once.

        Args:
            model_name (str):
            scenario_name (str):
            local_root (str): Path of root when running on a local computer
            project_id (str): Project-id, when running in WS Cloud, also requires a project_access_token
            project_access_token (str): When running in WS Cloud, also requires a project_id
            project (project_lib.Project): alternative for project_id and project_access_token for WS Cloud
            template_scenario_name (str): If scenario doesn't exists: create new one. If template_scenario_name is specified, use that as template.
        """
        self.model_name = model_name
        self.scenario_name = scenario_name
        self.local_root = local_root
        self.project_id = project_id
        self.project_access_token = project_access_token
        self.project = project
        self.inputs = None
        self.outputs = None
        self.template_scenario_name = template_scenario_name

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
        if ScenarioManager.env_is_cpd40():
            from ibm_watson_studio_lib import access_project_or_space
            wslib = access_project_or_space()
            data_dir = wslib.mount.get_base_dir()
        elif self.env_is_wscloud():
            data_dir = '/home/dsxuser/work'  # or use os.environ['PWD'] ?
        elif ScenarioManager.env_is_cpd25():
            # Note that the data dir in CPD25 is not an actual real directory and is NOT in the hierarchy of the JupyterLab folder
            data_dir = '/project_data/data_asset'  # Do NOT use the os.path.join!
        elif ScenarioManager.env_is_dsx():
            data_dir = os.path.join(self.get_root_directory(), 'datasets')  # Do we need to add an empty string at the end?
        else:  # Local file system
            data_dir = os.path.join(self.get_root_directory(), 'datasets')
        return data_dir

    def get_root_directory(self) -> str:
        """Return the root directory of the file system.
        If system is WS, it will return the DSX root, otherwise the directory specified in the local_root.
        Raises:
            ValueError if root directory doesn't exist.
        """
        if ScenarioManager.env_is_cpd25():
            root_dir = '.'
        elif ScenarioManager.env_is_dsx():  # Note that this is False in DO! So don't run in DO
            root_dir = os.environ['DSX_PROJECT_DIR']
        else:
            if self.local_root is None:
                raise ValueError('The local_root should be specified if loading from a file from outside of WS')
            root_dir = self.local_root
        # Assert that root_dir actually exists
        if not os.path.isdir(root_dir):
            raise ValueError("Root directory `{}` does not exist.".format(root_dir))
        return root_dir

    def add_data_file_using_project_lib(self, file_path: str, file_name: Optional[str] = None) -> None:
        """Add a data file to the Watson Studio project.
        Applies to CP4Dv2.5 and WS Cloud
        Needs to be called after the file has been saved regularly in the file system in
        `/project_data/data_asset/` (for CPD2.5) or `/home/dsxuser/work/` in WS Cloud.
        Ensures the file is visible in the Data Assets of the Watson Studio UI.

        Args:
            file_path (str): full file path, including the file name and extension
            file_name (str): name of data asset. Default is None. If None, the file-name will be extracted from the file_path.
        """
        # Add to Project
        if self.project is None:
            from project_lib import Project
            self.project = Project.access()
        if file_name is None:
            file_name = os.path.basename(file_path)
        with open(file_path, 'rb') as f:
            self.project.save_data(file_name=file_name, data=f, overwrite=True)

    def add_data_file_using_ws_lib(self, file_path: str, file_name: Optional[str] = None) -> None:
        """Add a data file to the Watson Studio project using the ibm_watson_studio_lib .
        Applies to CP4Dv4.0
        TODO: where should the file be written?
        Needs to be called after the file has been saved regularly in the file system in
        `/project_data/data_asset/` (for CPD2.5) or `/home/dsxuser/work/` in WS Cloud.
        Ensures the file is visible in the Data Assets of the Watson Studio UI.

        Args:
            file_path (str): full file path, including the file name and extension
            file_name (str): name of data asset. Default is None. If None, the file-name will be extracted from the file_path.
        """
        # Add to Project
        from ibm_watson_studio_lib import access_project_or_space
        wslib = access_project_or_space()
        # BUG / TODO: this works fine if the asset doesn't yet exist. However, if so, it trows an error, i.e. the overwrite=True flag doesn't seem to work.
        wslib.upload_file(file_path=file_path, file_name=file_name, overwrite=True)

        # if file_name is None:
        #     file_name = os.path.basename(file_path)
        # with open(file_path, 'rb') as f:
        #     # wslib.save_data(asset_name_or_item=file_name, data=f, overwrite=True)
        #     wslib.upload_file(file_path=file_path, overwrite=True)

    @staticmethod
    def add_data_file_using_ws_lib_s(file_path: str, file_name: Optional[str] = None) -> None:
        """Add a data file to the Watson Studio project using the ibm_watson_studio_lib .
        Applies to CP4Dv4.0
        TODO: where should the file be written?
        Needs to be called after the file has been saved regularly in the file system in
        `/project_data/data_asset/` (for CPD2.5) or `/home/dsxuser/work/` in WS Cloud.
        Ensures the file is visible in the Data Assets of the Watson Studio UI.

        Args:
            file_path (str): full file path, including the file name and extension
            file_name (str): name of data asset. Default is None. If None, the file-name will be extracted from the file_path.
        """
        # Add to Project
        from ibm_watson_studio_lib import access_project_or_space
        wslib = access_project_or_space()
        # BUG / TODO: this works fine if the asset doesn't yet exist. However, if so, it trows an error, i.e. the overwrite=True flag doesn't seem to work.
        wslib.upload_file(file_path=file_path, file_name=file_name, overwrite=True)

    @staticmethod
    def add_data_file_to_project_s(file_path: str, file_name: Optional[str] = None) -> None:
        """Add a data file to the Watson Studio project.
        Applies to CP4Dv2.5.
        Needs to be called after the file has been saved regularly in the file system in `/project_data/data_asset/`.
        Ensures the file is visible in the Data Assets of the Watson Studio UI.

        Args:
            file_path (str): full file path, including the file name and extension
            file_name (str): name of data asset. Default is None. If None, the file-name will be extracted from the file_path.
        """
        # Add to Project
        if file_name is None:
            file_name = os.path.basename(file_path)
        with open(file_path, 'rb') as f:
            from project_lib import Project
            project = Project.access()
            project.save_data(file_name=file_name, data=f, overwrite=True)

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
                # Existing scenario probabaly already has solver code, so maintain that.
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
        # root_dir = self.get_root_directory()
        datasets_dir = self.get_data_directory()
        excel_file_path = os.path.join(datasets_dir, excel_file_name + '.xlsx')
        xl = pd.ExcelFile(excel_file_path)
        # Read data from Excel
        self.inputs, self.outputs = ScenarioManager.load_data_from_excel_s(xl)
        return self.inputs, self.outputs

    def write_data_to_excel(self, excel_file_name: str = None, copy_to_csv: bool = False) -> None:
        """Write inputs and/or outputs to an Excel file in datasets.
        The inputs and outputs as in the attributes `self.inputs` and `self.outputs` of the ScenarioManager

        The copy_to_csv is a work-around for the WS limitation of not being able to download a file from datasets that is not a csv file.
        Creates a copy of the Excel file as a file named `<excel_file_name>_xlxs.csv` in the datasets folder. This is *not* a csv file!
        Download this file to your local computer and rename to `<excel_file_name>.xlxs`

        If the excel_file_name is None, it will be generated from the model_name and scenario_name: MODEL_NAME + "_" + SCENARIO_NAME + "_output"

        Args:
            excel_file_name (str): The file name for the Excel file.
            copy_to_csv (bool): If true, will create a copy of the file with the extension `.csv`.
        """

        if excel_file_name is None:
            if self.model_name is not None and self.scenario_name is not None:
                excel_file_name = "{}_{}_output".format(self.model_name, self.scenario_name)
            else:
                raise ValueError("The argument excel_file_name can only be 'None' if both the model_name '{}' and the scenario_name '{}' have been specified.".format(self.model_name, self.scenario_name))

        # root_dir = self.get_root_directory()
        # Save the regular Excel file:
        data_dir = self.get_data_directory()
        excel_file_path_1 = os.path.join(data_dir, excel_file_name + '.xlsx')
        writer_1 = pd.ExcelWriter(excel_file_path_1, engine='xlsxwriter')
        ScenarioManager.write_data_to_excel_s(writer_1, inputs=self.inputs, outputs=self.outputs)
        writer_1.save()
        if ScenarioManager.env_is_cpd40():
            self.add_data_file_using_ws_lib(excel_file_path_1, excel_file_name + '.xlsx')
        elif ScenarioManager.env_is_cpd25():
            self.add_data_file_using_project_lib(excel_file_path_1, excel_file_name + '.xlsx')
        # # Save the csv copy (no longer supported in CPD25 because not necessary)
        # elif copy_to_csv:
        #     excel_file_path_2 = os.path.join(data_dir, excel_file_name + 'to_csv.xlsx')
        #     csv_excel_file_path_2 = os.path.join(data_dir, excel_file_name + '_xlsx.csv')
        #     writer_2 = pd.ExcelWriter(excel_file_path_2, engine='xlsxwriter')
        #     ScenarioManager.write_data_to_excel_s(writer_2, inputs=self.inputs, outputs=self.outputs)
        #     writer_2.save()
        #     os.rename(excel_file_path_2, csv_excel_file_path_2)
        return excel_file_path_1

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
                df.to_excel(writer, sheet_name, index=False)
                # Store row in table_index
                table_index.append({'table_name': table_name, 'sheet_name': sheet_name, 'category': 'input'})
        if (outputs is not None) and (type(outputs) is dict):
            for table_name, df in outputs.items():
                # truncate table name to 31 characters due to sheet name limit in Excel:
                sheet_name = ScenarioManager._create_unique_abbreviated_name(table_name, 31,
                                                                             sheet_names)
                sheet_names.add(sheet_name)
                df.to_excel(writer, sheet_name, index=False)
                # Store row in table_index
                table_index.append({'table_name': table_name, 'sheet_name': sheet_name, 'category': 'output'})

        # Add table_index sheet if applicable:
        if (len(table_index) > 0) & (table_index_sheet is not None):
            index_df = pd.DataFrame(table_index)
            index_df.to_excel(writer, table_index_sheet, index=False)

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
        # Read data from Excel
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
            head, tail = os.path.split(file_path)
            table_name = tail[:-4]  # remove the '.csv'
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
        if inputs is not None:
            for table_name, df in inputs.items():
                file_path = os.path.join(csv_directory, table_name + ".csv")
                print("Writing {}".format(file_path))
                df.to_csv(file_path, index=False)
                if ScenarioManager.env_is_cpd40():
                    ScenarioManager.add_data_file_using_ws_lib_s(file_path)
                elif ScenarioManager.env_is_cpd25():
                    ScenarioManager.add_data_file_to_project_s(file_path, table_name + ".csv")
        if outputs is not None:
            for table_name, df in outputs.items():
                file_path = os.path.join(csv_directory, table_name + ".csv")
                print("Writing {}".format(file_path))
                df.to_csv(file_path, index=False)
                if ScenarioManager.env_is_cpd40():
                    ScenarioManager.add_data_file_using_ws_lib_s(file_path)
                elif ScenarioManager.env_is_cpd25():
                    ScenarioManager.add_data_file_to_project_s(file_path, table_name + ".csv")

    # -----------------------------------------------------------------
    # Utils
    # -----------------------------------------------------------------

    @staticmethod
    def env_is_cpd40() -> bool:
        """Return true if environment is CPDv4.0.2 and in particular supports ibm_watson_studio_lib to get access to data assets"""
        try:
            from ibm_watson_studio_lib import access_project_or_space
            # wslib = access_project_or_space()
            # wslib.mount.get_base_dir()
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

    def env_is_wscloud(self) -> bool:
        """Return true if environment is WS Cloud"""
        return 'PWD' in os.environ and os.environ['PWD'] == '/home/dsxuser/work'

    def get_dd_client(self):
        """Return the Client managing the DO scenario.
        Returns: new decision_optimization_client.Client
        """
        from decision_optimization_client import Client
        if self.project is not None:
            pc = self.project.project_context
            return Client(pc=pc)
        elif (self.project_id is not None) and (self.project_access_token is not None):
            # When in WS Cloud:
            from project_lib import Project
            # The do_optimization project token is an authorization token used to access project resources like data sources, connections, and used by platform APIs.
            project = Project(project_id=self.project_id,
                              project_access_token=self.project_access_token)
            pc = project.project_context
            return Client(pc=pc)
        else:
            #  In WSL/CPD:
            return Client()

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
        if ScenarioManager.env_is_cpd40():
            self.add_data_file_using_ws_lib(lp_file_path)
        if self.env_is_cpd25():
            self.add_data_file_using_project_lib(lp_file_path, lp_file_name)
        return lp_file_path
