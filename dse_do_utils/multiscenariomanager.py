# Copyright IBM All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

# -----------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------
# MultiScenarioManager
# -----------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------

import pandas as pd
import os
from typing import Sequence, List, Dict, Tuple, Optional

#  Typing aliases
Inputs = Dict[str, pd.DataFrame]
Outputs = Dict[str, pd.DataFrame]
InputsOutputs = Tuple[Inputs, Outputs]

try:
    # Import as part of package
    from .scenariomanager import ScenarioManager
except:
    # import as part of DO Model Builder
    from scenariomanager import ScenarioManager

# from dse_do_utils import ScenarioManager


class MultiScenarioManager(object):
    """Manages multiple scnearios from same DO Model/Experiment.
    Can export all scenarios in one Excel spreadsheet, where it adds the scenario_name as an additional column.
    Also adds an aditional 'Scenario' table. (This looks relevant for usage (filtering) in Cognos.)
    By default, writes an Excel file in datasets named "model_name + '_multi_output'.xlsx"

    Usage 1 - All scenarios from Model::

        model_name = 'My Model'
        msm = MultiScenarioManager(model_name=model_name)
        msm.get_multi_scenario_data()
        msm.write_data_to_excel()


    Usage 2 - Selected scenarios from Model::

        model_name = 'My Model'
        scenario_names = ['Scenario 1', 'Scenario 2']
        msm = MultiScenarioManager(model_name=model_name, scenario_names=scenario_names)
        msm.get_multi_scenario_data()
        msm.write_data_to_excel()

    """

    def __init__(self, model_name: Optional[str] = None, scenario_names: List[str] = [],
                 local_root: Optional[str] = None, project_id: Optional[str] = None,
                 project_access_token: Optional[str] = None, project=None):
        """Create a MultiScenarioManager.

        Args:
            model_name (str):
            scenario_names (List[str]): list of anmes of scenarios to export. If not specified or empty then it will select all scenarios in the model
            local_root (str): Path of root when running on a local computer
            project_id (str): Project-id, when running in WS Cloud, also requires a project_access_token
            project_access_token (str): When running in WS Cloud, also requires a project_id
            project (project_lib.Project): alternative for project_id and project_access_token for WS Cloud
        """
        self.model_name = model_name
        self.local_root = local_root
        self.project_id = project_id
        self.project_access_token = project_access_token
        self.project = project
        self.scenarios_df = self.get_scenarios_df(scenario_names)
        if scenario_names is None:
            #             self.scenario_names = self.get_all_scenario_names()
            self.scenario_names = list(self.scenarios_df.scenario_name)
        else:
            self.scenario_names = scenario_names
        self.inputs_by_scenario: Dict[str, Inputs] = {}
        self.outputs_by_scenario: Dict[str, Outputs] = {}
        self.inputs = None
        self.outputs = None

    def get_dd_client(self):
        """Return the Client managing the DO scenario.
        Returns: new dd_scenario.Client
        """
        from dd_scenario import Client
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

    def load_data_from_scenario(self, scenario_name):
        """TODO: see of by re-using a Client, this can be done faster"""
        sm = ScenarioManager(self.model_name, scenario_name, self.local_root, self.project_id,
                             self.project_access_token, self.project)
        inputs, outputs = sm.load_data_from_scenario()
        return inputs, outputs

    def env_is_wscloud(self) -> bool:
        """Return true if environment is WS Cloud"""
        return 'PWD' in os.environ and os.environ['PWD'] == '/home/dsxuser/work'

    def get_data_directory(self) -> str:
        """Returns the path to the datasets folder.

        :return: path to the datasets folder
        """
        if self.env_is_wscloud():
            data_dir = '/home/dsxuser/work'  # or use os.environ['PWD'] ?
        elif ScenarioManager.env_is_cpd25():
            # Note that the data dir in CPD25 is not an actual real directory and is NOT in the hierarchy of the JupyterLab folder
            data_dir = '/project_data/data_asset'  # Do NOT use the os.path.join!
        elif ScenarioManager.env_is_dsx():
            data_dir = os.path.join(self.get_root_directory(),
                                    'datasets')  # Do we need to add an empty string at the end?
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

    def add_data_file_to_project(self, file_path: str, file_name: Optional[str] = None) -> None:
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

    def get_multi_scenario_data(self, scenario_names: List[str] = None):
        if scenario_names is None:
            scenario_names = self.scenario_names
        for scenario_name in scenario_names:
            inputs, outputs = self.load_data_from_scenario(scenario_name)
            self.inputs_by_scenario[scenario_name] = inputs
            self.outputs_by_scenario[scenario_name] = outputs
        self.inputs = MultiScenarioManager.merge_scenario_data(self.inputs_by_scenario)
        self.inputs['Scenario'] = self.scenarios_df  # Adding the Scenarios as a reference table
        self.outputs = MultiScenarioManager.merge_scenario_data(self.outputs_by_scenario)

    def write_data_to_excel(self, excel_file_name: str = None) -> None:
        """Write inputs and/or outputs to an Excel file in datasets.
        The inputs and outputs as in the attributes `self.inputs` and `self.outputs` of the ScenarioManager

        If the excel_file_name is None, it will be generated from the model_name and scenario_name: MODEL_NAME + "_multi_output"

        Args:
            excel_file_name (str): The file name for the Excel file.
        """

        if excel_file_name is None:
            if self.model_name is not None:
                excel_file_name = f"{self.model_name}_multi_output"
            else:
                raise ValueError(
                    "The argument excel_file_name can only be 'None' if the model_name '{}' has been specified.".format(
                        self.model_name))

        # Save the regular Excel file:
        data_dir = self.get_data_directory()
        excel_file_path = os.path.join(data_dir, excel_file_name + '.xlsx')
        writer = pd.ExcelWriter(excel_file_path, engine='xlsxwriter')
        ScenarioManager.write_data_to_excel_s(writer, inputs=self.inputs, outputs=self.outputs)
        writer.save()
        if ScenarioManager.env_is_cpd25():
            self.add_data_file_to_project(excel_file_path, excel_file_name + '.xlsx')
        return excel_file_path

    @staticmethod
    def merge_scenario_data(data_by_scenario: Dict[str, Dict[str, pd.DataFrame]]) -> Dict[str, pd.DataFrame]:
        """Add scenario_name as column. Merge tables"""
        merged_data_dict = {}
        for scenario, data_dict in data_by_scenario.items():
            #             print(f"Merge scenario {scenario}")
            for table_name, df in data_dict.items():
                #                 print(f"Merge scenario {scenario} - table {table_name}")
                df['scenario_name'] = scenario
                if table_name in merged_data_dict.keys():
                    existing_df = merged_data_dict[table_name]
                    # TODO: what will happen if the 2 dataframes have different columns? A: you get both columns and NaN values
                    existing_df = existing_df.append(df, ignore_index=True, sort=False)
                    merged_data_dict[table_name] = existing_df
                else:
                    merged_data_dict[table_name] = df
        return merged_data_dict

    def get_all_scenario_names(self):
        """Deprecated. Replaced by get_scenarios_df"""
        names = []
        client = self.get_dd_client()
        model_builder = client.get_model_builder(name=self.model_name)
        if model_builder is None:
            raise ValueError('No DO model with name `{}` exists'.format(model_name))
        names = model_builder.get_scenarios(as_dict=True)
        return list(names.keys())

    def get_scenarios_df(self, scenario_names: List[str] = None) -> pd.DataFrame:
        """Return scenarios as Dataframe.
        If scenario_names is None, will get all scenarios in Model.
        Else, just the ones matching the names.
        For now, the only column in the df is the scenario_name.
        More can be added later.
        """
        names = []
        client = self.get_dd_client()
        model_builder = client.get_model_builder(name=self.model_name)
        if model_builder is None:
            raise ValueError('No DO model with name `{}` exists'.format(model_name))
        scenarios_dict = model_builder.get_scenarios(as_dict=True)
        df = pd.DataFrame({'scenario_name': list(scenarios_dict.keys())})
        if scenario_names is not None:
            df = df.query("scenario_name in @scenario_names")
        return df