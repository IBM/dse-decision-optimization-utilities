# Copyright IBM All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import dataclass

import pandas as pd

from dse_do_utils import ScenarioManager, OptimizationEngine
from dse_do_utils.datamanager import Inputs, Outputs, DataManager
from dse_do_utils.scenariodbmanager import ScenarioDbManager
from logging import Logger, getLogger
from typing import Any, Dict, Optional, Tuple, NamedTuple, Type, List


@dataclass  # (frozen=True)
class ScenarioConfig:
    scenario_name: str = 'Scenario_x'
    parameters: Dict = None  # Dict of parameters to override. Uses same names as in Parameters data table.

@dataclass  # (frozen=True)
class RunConfig:
    insert_inputs_in_db: bool = False
    insert_outputs_in_db: bool = False
    new_schema: bool = False
    insert_in_do: bool = False
    write_output_to_excel: bool = False
    enable_data_check: bool = False
    enable_data_check_outputs: bool = False
    data_check_bulk_insert: bool = False  # False implies row-by-row
    log_level: str = 'DEBUG'  # 'DEBUG'
    export_lp: bool = False
    export_lp_path: str = ''
    do_model_name: str = None
    template_scenario_name: Optional[str] = None  # 'TemplateScenario'


class ScenarioGenerator():
    """Generates a variation of a scenario, i.e. `inputs` dataset, driven by a ScenarioConfig.
    To be subclassed.
    This base class implements overrides of the Parameter table.
    The ScenarioGenerator is typically used in the context of a ScenarioRunner.

    Usage::

        class MyScenarioGenerator(ScenarioGenerator):
            def generate_scenario(self):
                new_inputs = super().generate_scenario()
                new_inputs['MyTable1'] = self.generate_my_table1().reset_index()
                new_inputs['MyTable2'] = self.generate_my_table2().reset_index()
                return new_inputs
    """

    def __init__(self,
                 inputs: Inputs,
                 scenario_config: ScenarioConfig) -> None:
        self._logger: Logger = getLogger(self.__class__.__name__)
        self.inputs: Inputs = inputs.copy()  # Only copy of dict
        self.scenario_config: ScenarioConfig = scenario_config

    def generate_scenario(self):
        """Generate a variation of the base_inputs. To be overridden.
        This default implementation changes the Parameter table based on the overrides in the ScenarioConfig.parameters.

        Usage::

            def generate_scenario(self):
                new_inputs = super().generate_scenario()
                new_inputs['MyTable'] = self.generate_my_table().reset_index()
                return new_inputs

        """
        new_inputs = self.inputs
        new_inputs['Parameter'] = self.get_parameters().reset_index()
        return new_inputs

    def get_parameters(self) -> pd.DataFrame:
        """Applies overrides to the Parameter table based on the ScenarioConfig.parameters.
        """
        if self.scenario_config.parameters is None:
            df = self.inputs['Parameter']
        else:
            df = self.inputs['Parameter'].copy().set_index(['param'])
            for param, value in self.scenario_config.parameters.items():
                df.at[param, 'value'] = value
        return df


class ScenarioRunner:
    """
    TODO: remove local_root, local_platform, replace by data_directory? (It seems to be working fine though)
    """
    def __init__(self,
                 scenario_db_manager: ScenarioDbManager,
                 optimization_engine_class: Type[OptimizationEngine],
                 data_manager_class: Type[DataManager],
                 scenario_db_manager_class: Type[ScenarioDbManager],  # For the SQLite data check
                 scenario_generator_class: Optional[Type[ScenarioGenerator]] = None,
                 do_model_name: str = 'my_model',
                 schema: Optional[str] = None,
                 # use_scenario_db: bool = True,
                 local_root: Optional[str] = None,
                 local_platform: Optional[int] = None,
                 data_directory: Optional[str] = None) -> None:

        self.scenario_db_manager: ScenarioDbManager = scenario_db_manager
        self.optimization_engine_class: Type[OptimizationEngine] = optimization_engine_class
        self.data_manager_class = data_manager_class
        self.scenario_db_manager_class = scenario_db_manager_class
        self.scenario_generator_class = scenario_generator_class

        self.optimization_engine: OptimizationEngine = None  # To be set in run.
        self.data_manager: DataManager = None  # To be set in run.
        self.sqlite_scenario_db_manager: ScenarioDbManager = None  # To be set in run.

        self._logger: Logger = getLogger(self.__class__.__name__)
        self.schema: Optional[str] = schema
        self.do_model_name: str = do_model_name
        # self.use_scenario_db: bool = use_scenario_db  # TODO: VT20220906: remove, doesn't seem to be used?
        self.local_root: Optional[str] = local_root
        self.local_platform: Optional[int] = local_platform
        self.data_directory: Optional[str] = data_directory

    def run_once(self,
                 scenario_config: ScenarioConfig,
                 run_config: RunConfig,
                 base_inputs: Optional[Inputs] = None,
                 excel_file_name: Optional[str] = None):
        if run_config.new_schema:
            self.create_new_db_schema()
        base_inputs = self._load_base_inputs(excel_file_name=excel_file_name, base_inputs=base_inputs)
        outputs = self._run_once(scenario_config, run_config, base_inputs)
        return outputs

    def run_multiple(self,
                     scenario_configs: List[ScenarioConfig],
                     run_config: RunConfig,
                     base_inputs: Optional[Inputs] = None,
                     excel_file_name: Optional[str] = None) -> None:
        """Only once create schema and/or load data from Excel.
        Then it will run all scenario_configs, each time applying the ScenarioGenerator on the base inputs."""
        if run_config.new_schema:
            self.create_new_db_schema()
        base_inputs = self._load_base_inputs(excel_file_name=excel_file_name, base_inputs=base_inputs)
        for scenario_config in scenario_configs:
            self._run_once(scenario_config, run_config, base_inputs)

    def _run_once(self,
                 scenario_config: ScenarioConfig,
                 run_config: RunConfig,
                 base_inputs: Inputs = None) -> Outputs:
        '''
        :param scenario_config:
        :param run_config:
        :param base_inputs:
        :param excel_filepath
        :return:
        '''

        scenario_name = scenario_config.scenario_name

        # # Load base inputs
        # if excel_file_name and not base_inputs:
        #     self._logger.info('Loading data from the excel file')
        #     inputs = self.load_input_data_from_excel(excel_file_name)
        # elif not excel_file_name and base_inputs:
        #     inputs = base_inputs
        # else:
        #     raise ValueError(
        #         'Either base_inputs or excel_file_name should be provided.')

        # Generate scenario
        self._logger.info(f'Generating scenario {scenario_name}')
        inputs = self.generate_scenario(base_inputs, scenario_config)

        # Data check
        if run_config.enable_data_check:
            inputs = self.data_check_inputs(inputs, scenario_name = scenario_config.scenario_name, bulk = run_config.data_check_bulk_insert)

        # Pass inputs through scenario DB
        if run_config.insert_inputs_in_db:
            inputs = self.insert_inputs_in_db(inputs, run_config, scenario_config.scenario_name)

        # Run DO engine.
        self._logger.info(f'Solving {scenario_name}')
        # inputs = inputs_from_db if db_insert_input_flag else inputs
        outputs = self.run_model(inputs, run_config)

        if run_config.enable_data_check_outputs:
            inputs, outputs = self.data_check_outputs(inputs=inputs, outputs=outputs, scenario_name=scenario_config.scenario_name, bulk=run_config.data_check_bulk_insert)

        if run_config.insert_outputs_in_db:
            self.insert_outputs_in_db(inputs, outputs, run_config, scenario_config.scenario_name)

        if run_config.insert_in_do:
            self.insert_in_do(inputs, outputs, scenario_config, self.model_name)

        if run_config.write_output_to_excel:
            self.write_output_data_to_excel(inputs, outputs, scenario_name)

        self._logger.info(f'Done with {scenario_config.scenario_name}')

        return outputs

    def create_new_db_schema(self):
        self._logger.info(f'Creating a new schema: {self.schema}')
        self.scenario_db_manager.create_schema()

    def _load_base_inputs(self, excel_file_name, base_inputs):
        # Load base inputs
        if excel_file_name and not base_inputs:
            self._logger.info('Loading data from the excel file')
            inputs = self.load_input_data_from_excel(excel_file_name)
        elif not excel_file_name and base_inputs:
            inputs = base_inputs
        else:
            raise ValueError(
                'Either base_inputs or excel_file_name should be provided.')
        return inputs

    # def run_once(self,
    #              scenario_config: ScenarioConfig,
    #              run_config: RunConfig,
    #              base_inputs: Optional[Inputs] = None,
    #              excel_file_name: Optional[str] = None) -> Outputs:
    #     '''
    #     :param scenario_config:
    #     :param run_config:
    #     :param base_inputs:
    #     :param excel_filepath
    #     :return:
    #     '''
    #
    #     scenario_name = scenario_config.scenario_name
    #     db_insert_input_flag = run_config.insert_inputs_in_db
    #     db_insert_output_flag = run_config.insert_outputs_in_db
    #     '''
    #     Read data from the excel file. Either use `ScenarioInputsOutputs` class
    #     or `ScenarioManager.load_data_from_excel`.
    #     '''
    #
    #     # Load base inputs
    #     if excel_file_name and not base_inputs:
    #         self._logger.info('Loading data from the excel file')
    #         inputs = self.load_input_data_from_excel(excel_file_name)
    #     elif not excel_file_name and base_inputs:
    #         inputs = base_inputs
    #     else:
    #         raise ValueError(
    #             'Either base_inputs or excel_file_name should be provided.')
    #
    #     # Generate scenario
    #     self._logger.info(f'Generating scenario {scenario_name}')
    #     inputs = self.generate_scenario(inputs, scenario_config)
    #
    #     # Data check
    #     if run_config.enable_data_check:
    #         inputs = self.data_check_inputs(inputs, scenario_name = scenario_config.scenario_name, bulk = run_config.data_check_bulk_insert)
    #
    #     # Pass inputs through scenario DB
    #     if run_config.insert_inputs_in_db:
    #         inputs = self.insert_inputs_in_db(inputs, run_config, scenario_config.scenario_name)
    #
    #     # Run DO engine.
    #     self._logger.info(f'Solving {scenario_name}')
    #     # inputs = inputs_from_db if db_insert_input_flag else inputs
    #     outputs = self.run_model(inputs, run_config)
    #
    #     if run_config.enable_data_check_outputs:
    #         inputs, outputs = self.data_check_outputs(inputs=inputs, outputs=outputs, scenario_name=scenario_config.scenario_name, bulk=run_config.data_check_bulk_insert)
    #
    #     if run_config.insert_outputs_in_db:
    #         self.insert_outputs_in_db(inputs, outputs, run_config, scenario_config.scenario_name)
    #
    #     if run_config.insert_in_do:
    #         self.insert_in_do(inputs, outputs, scenario_config, self.model_name)
    #
    #     if run_config.write_output_to_excel:
    #         self.write_output_data_to_excel(inputs, outputs, scenario_name)
    #
    #     self._logger.info(f'Done with {scenario_config.scenario_name}')
    #
    #     return outputs

    def load_input_data_from_excel(self, excel_file_name) -> Inputs:
        sm = ScenarioManager(local_root=self.local_root, local_relative_data_path = '',
                             data_directory=self.data_directory,
                             # model_name=self.do_model_name,
                             # scenario_name=scenario_name,
                             # template_scenario_name='TemplateScenario',
                             platform=self.local_platform)
        inputs, _ = sm.load_data_from_excel(excel_file_name)
        return inputs

    def write_output_data_to_excel(self, inputs: Inputs, outputs: Outputs, scenario_name: str):
        sm = ScenarioManager(local_root=self.local_root, local_relative_data_path = '',
                             data_directory=self.data_directory,
                             inputs=inputs, outputs=outputs,
                             model_name=self.do_model_name,
                             scenario_name=scenario_name,
                             platform=self.local_platform)
        filepath = sm.write_data_to_excel()
        self._logger.info(f'Wrote output to {filepath}')

    def generate_scenario(self, base_inputs: Inputs,
                          scenario_config: ScenarioConfig):
        """
        Generate a derived scenario from a baseline scenario on the 
        specifications in the scenario_config.
        :param base_inputs:
        :param scenario_config:
        :return:
        """
        if self.scenario_generator_class is not None:
            self._logger.info('Generate Scenario')
            sg: ScenarioGenerator = self.scenario_generator_class(base_inputs, scenario_config)
            inputs = sg.generate_scenario()
        else:
            inputs = base_inputs
        return inputs

    def data_check_inputs(self, inputs: Inputs, scenario_name: str = 'data_check', bulk: bool = False) -> Inputs:
        """Use SQLite to validate data. Read data back and do a dm.prepare_data_frames.
        Does a deepcopy of the inputs to ensure the DB operations do not alter the inputs.
        Bulk can be set to True once the basic data issues have been resolved and performance needs to be improved.
        Set bulk to False to get more granular DB insert errors, i.e. per record.
        TODO: add a data_check() on the DataManager for additional checks."""
        self._logger.info('Checking input data via SQLite and DataManager')
        self.sqlite_scenario_db_manager: ScenarioDbManager = self.scenario_db_manager_class()
        self.sqlite_scenario_db_manager.create_schema()
        self.sqlite_scenario_db_manager.replace_scenario_in_db(scenario_name, deepcopy(inputs), {}, bulk=bulk)

        inputs_v2, outputs_v2 = self.sqlite_scenario_db_manager.read_scenario_from_db(scenario_name)
        dm: DataManager = self.data_manager_class(inputs_v2, outputs_v2)
        dm.prepare_data_frames()
        return inputs_v2

    def data_check_outputs(self, inputs: Inputs, outputs: Outputs, scenario_name: str = 'data_check', bulk: bool = False) -> Tuple[Inputs, Outputs]:
        """Use SQLite to validate data. Read data back and do a dm.prepare_data_frames.
        Does a deepcopy of the inputs to ensure the DB operations do not alter the inputs.
        Bulk can be set to True once the basic data issues have been resolved and performance needs to be improved.
        Set bulk to False to get more granular DB insert errors, i.e. per record.
        TODO: add a data_check() on the DataManager for additional checks."""
        self._logger.info('Checking output data via SQLite and DataManager')
        if self.sqlite_scenario_db_manager is None:
            self.sqlite_scenario_db_manager: ScenarioDbManager = self.scenario_db_manager_class()
            self.sqlite_scenario_db_manager.create_schema()
            self.sqlite_scenario_db_manager.replace_scenario_in_db(scenario_name, deepcopy(inputs), deepcopy(outputs), bulk=bulk)
        else:
            self.sqlite_scenario_db_manager.update_scenario_output_tables_in_db(scenario_name, outputs)  # TODO: add bulk=False option

        inputs_v2, outputs_v2 = self.sqlite_scenario_db_manager.read_scenario_from_db(scenario_name)
        dm: DataManager = self.data_manager_class(inputs_v2, outputs_v2)
        dm.prepare_data_frames()
        return inputs_v2, outputs_v2

    def insert_inputs_in_db(self, inputs: Inputs, run_config: RunConfig, scenario_name: str) -> Inputs:

        # 1. Create new schema: Is NOT done here! Is now done earlier and only once per call
        # 2. Insert inputs in DB
        self.scenario_db_manager.replace_scenario_in_db(scenario_name, inputs, {}, bulk=True)
        # 3. Read inputs from DB
        inputs_v2 = self.scenario_db_manager.read_scenario_input_tables_from_db(scenario_name)
        return inputs_v2

    # def insert_inputs_in_db(self, inputs: Inputs, run_config: RunConfig, scenario_name: str) -> Inputs:
    #
    #     # 1. Create new schema
    #     if run_config.new_schema:
    #         self._logger.info(f'Creating a new schema: {self.schema}')
    #         self.scenario_db_manager.create_schema()
    #     # 2. Insert inputs in DB
    #     self.scenario_db_manager.replace_scenario_in_db(scenario_name, inputs, {}, bulk=True)
    #     # 3. Read inputs from DB
    #     inputs_v2 = self.scenario_db_manager.read_scenario_input_tables_from_db(scenario_name)
    #     return inputs_v2


    def run_model(self, inputs: Inputs, run_config: RunConfig):
        '''
        Main method to run the optimization model.
        '''

        self.data_manager = self.data_manager_class(
            inputs=inputs, log_level=run_config.log_level)  # 'DEBUG'
        self.optimization_engine: OptimizationEngine = self.optimization_engine_class(
            data_manager=self.data_manager,
            name=(run_config.do_model_name if run_config.do_model_name is not None else self.do_model_name),
            export_lp=run_config.export_lp,
            export_lp_path=run_config.export_lp_path,
        )

        return self.optimization_engine.run()

    def insert_outputs_in_db(self, inputs: Inputs, outputs: Outputs, run_config: RunConfig, scenario_name: str):
        self._logger.info('Inserting outputs into the database')
        if run_config.insert_inputs_in_db:
            self.scenario_db_manager.update_scenario_output_tables_in_db(scenario_name, outputs)
        else:
            self.scenario_db_manager.replace_scenario_in_db(scenario_name, inputs, outputs)

    def insert_in_do(self, inputs, outputs, scenario_config: ScenarioConfig,
                     run_config: RunConfig):

        print(f"DO insert for {scenario_config.scenario_name}")
        sm = ScenarioManager(model_name=run_config.do_model_name,
                             scenario_name=scenario_config.scenario_name)
        # sm.inputs = inputs
        # sm.outputs = outputs
        # self._logger.info(f'Scenario: {scenario_config.scenario_name}')
        # sm.print_table_names()
        # sm.write_data_into_scenario()
        # self._logger.info('Start create')
        sm.write_data_into_scenario_s(
            run_config.do_model_name,
            scenario_config.scenario_name,
            inputs,
            outputs,
            template_scenario_name=run_config.template_scenario_name)
        # sm.write_data_to_excel()

    # @staticmethod
    # def schema_exists(scdb: ScenarioDbManager, db_credentials: dict,
    #                   schema: str) -> bool:
    #     """
    #     TODO: scdb already has a engine. No need to create a new one
    #     :param scdb:
    #     :param db_credentials:
    #     :param schema:
    #     :return:
    #     """
    #
    #     connection_string_list = scdb._get_db2_connection_string(
    #         db_credentials, schema).split(';')
    #     connection_string = (connection_string_list[0] + ';' +
    #                          connection_string_list[-1])
    #     engine = create_engine(connection_string, echo=True)
    #
    #     with engine.connect() as connection:
    #         result = connection.execute(
    #             text(f'SELECT schemaname FROM syscat.schemata;'))
    #
    #         for row in result:
    #             if row[0] == schema:
    #                 return True
    #
    #     return False
    #
    # def create_new_schema(self, db_credentials: Dict[str, str],
    #                       schema: str) -> None:
    #     '''
    #     Create a new schema if it does not exist.
    #     '''
    #
    #     scdb = ScenarioDbManager(echo=False,
    #                              credentials=db_credentials,
    #                              schema=schema)
    #
    #     if not ScenarioRunner.schema_exists(scdb, db_credentials, schema):
    #         scdb.create_schema()
