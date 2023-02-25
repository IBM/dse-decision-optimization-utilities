# Copyright IBM Corp. 2021, 2022
# IBM Confidential Source Code Materials
# This Source Code is subject to the license and security terms contained in the License.txt file contained in this source code package.

import types
from abc import ABC, abstractmethod

import pandas as pd
from dse_do_utils.datamanager import Outputs
from utils.core.core01_data_manager import Core01DataManager


class Core02DataManager(Core01DataManager, ABC):
    """Adds Lexicographical optimization."""

    def __init__(self, inputs=None, outputs=None, log_level=None):
        super().__init__(inputs, outputs, log_level)

        # Input data
        # self.lex_opti_levels = None
        # self.lex_opti_goals = None

        # Intermediate data - input
        self._lex_opti_levels = None
        self._lex_opti_goals = None

        # Output
        self.lex_opti_metrics_output: pd.DataFrame = None

    def prepare_input_data_frames(self):
        """
        Prepare input data frames
        """
        self.logger.debug("Enter")

        super().prepare_input_data_frames()

        self.lex_opti_levels
        self.lex_opti_goals

        self.logger.debug("Exit")

    def prepare_output_data_frames(self, dtypes=None):
        super().prepare_output_data_frames()

        self.lex_opti_metrics_output = self.prepare_df(
            self.outputs.get('LexOptiMetrics'),
            index_columns=['lexOptiLevelId', 'metricType', 'metricName'],
            value_columns=['metricValue', 'metricTextValue'],
            dtypes={
                **self.dtypes,  # later entries will override any entries in in self.dtypes
                'metricValue': float,
                'metricTextValue': str,
            },
        )

    def set_parameters(self):
        super().set_parameters()
        self.param.enable_lex_optimization = self.get_parameter_value(
            self.params,
            'enableLexOptimization',
            param_type='bool',
            default_value=True)

    ####################################################################################
    #  Properties
    ####################################################################################

    @property
    def lex_opti_levels(self):
        """
        Get the

        Returns:
            self._lex_opti_goals
        """

        if self._lex_opti_levels is None:
            self._lex_opti_levels = self.prep_lex_opti_levels()
        return self._lex_opti_levels

    def prep_lex_opti_levels(self):
        """
        Prepare lex_opti_levels

        Returns:
            df: lex_opti_levels
        """
        input_table_name='LexOptiLevel'
        df = self.inputs.get(input_table_name)
        # Provide default settings when table is missing from inputs:
        if df is None or df.shape[0] == 0:
            df = self.get_default_lex_opti_level_table()

        df = self.prepare_df(
            df,
            index_columns=['lexOptiLevelId'],
            value_columns=['priority', 'timeLimit', 'mipGap'], # Note that 'absTol' is not required
            optional_columns=['relTol', 'absTol', 'isActive'],  #
            dtypes={
                **self.dtypes,  # later entries will override any entries in in self.dtypes
                # 'isActive': bool,
                'priority': int,
                'timeLimit': int,
                'mipGap': float,
                # 'relTol': float,
                # 'absTol': float,
            },
            data_specs_key = input_table_name
        )

        df['relTol'] = df['relTol'].fillna(0).clip(lower=0).astype(float)  # Use clip to avoid issues with negative values
        df['absTol'] = df['absTol'].fillna(0).clip(lower=0).astype(float)
        df['isActive'] = df['isActive'].fillna(True).astype(bool)

        return df

    @abstractmethod
    def get_default_lex_opti_level_table(self) -> pd.DataFrame:
        """Non-indexed DataFrame.
        By breaking it out in a method, makes it easier to override these default values.

        Just an example"""
        df = pd.DataFrame({
            'lexOptiLevelId': ['backlogCost', 'operationalCost'],
            'priority': [1, 2],
            'sense': ['min', 'min'],
            'timeLimit': [600, 600],
            'mipGap': [0.01, 0.01],
            'absTol': [0.01, 0.01],
            'relTol': [-1, -1],
            'isActive': [True, True],
        })
        return df

    @property
    def lex_opti_goals(self):
        """
        Get the

        Returns:
            self._lex_opti_goals
        """

        if self._lex_opti_goals is None:
            self._lex_opti_goals = self.prep_lex_opti_goals()
        return self._lex_opti_goals

    def prep_lex_opti_goals(self):
        """
        Prepare lex_opti_goals

        Returns:
            df: lex_opti_goals
        """
        input_table_name='LexOptiGoal'
        df = self.inputs.get(input_table_name)
        # Provide default settings when table is missing from inputs:
        if df is None or df.shape[0] == 0:
            df = self.get_default_lex_opti_goal_table()

        df = self.prepare_df(
            df,
            index_columns=['lexOptiGoalId'],
            value_columns=['lexOptiLevelId'],
            optional_columns=['weight', 'isActive'],
            dtypes={
                **self.dtypes,  # later entries will override any entries in in self.dtypes{
                'isActive': bool,
                'weight': float,
            },
            data_specs_key = input_table_name
        )

        df['weight'] = df['weight'].fillna(1)
        df['isActive'] = df['isActive'].fillna(True)

        return df

    @abstractmethod
    def get_default_lex_opti_goal_table(self) -> pd.DataFrame:
        """Non-indexed DataFrame.
        By breaking it out in a method, makes it easier to override these default values.

        Just an example. Requires override"""
        df = pd.DataFrame({
            'lexOptiGoalId': ['backlogCost', 'productionCost', 'transportationCost'],
            'lexOptiLevelId': ['backlogCost', 'operationalCost', 'operationalCost'],
            'weight': [1,1,1],
            'isActive': [True,True,True],
        })
        return df

    ####################################################################################
    #  Pre-processing
    ####################################################################################
    def pre_processing(self):
        self.logger.debug("Enter")
        super().pre_processing()
        # self.prep_lex_optimization()
        self.logger.debug("Exit")

    def prep_lex_optimization(self):
        """Set defaults in case no input tables"""
        self.logger.debug("Enter")
        # if self.lex_opti_levels is None or self.lex_opti_levels.shape[0] == 0:
        #     self.lex_opti_levels = pd.DataFrame({
        #         'lexOptiLevelId': ['backlogCost', 'operationalCost'],
        #         'priority': [1, 2],
        #         'sense': ['min', 'min'],
        #         'timeLimit': [600, 600],
        #         'mipGap': [0.01, 0.01],
        #         'absTol': [0.01, 0.01],
        #         'relTol': [-1, -1],
        #         'isActive': [True, True],
        #     }).set_index('lexOptiLevelId', verify_integrity=True)
        #
        # if self.lex_opti_goals is None:
        #     self.lex_opti_goals = pd.DataFrame({
        #         'lexOptiGoalId': ['backlogCost', 'productionCost','transportationCost', 'inventoryCost', 'warehouseVariableCost', 'warehouseFixedCost'],
        #         'lexOptiLevelId': ['backlogCost', 'operationalCost','operationalCost', 'operationalCost', 'operationalCost', 'operationalCost'],
        #         'weight': [1,1,1,1,1,1],
        #         'isActive': [True,True,True,True,True,True],
        #     }).set_index('lexOptiGoalId', verify_integrity=True)

        self.logger.debug("Exit")



    def get_outputs(self) -> Outputs:
        self.logger.debug("Enter")

        outputs = super().get_outputs()
        outputs['LexOptiMetrics'] = self.lex_opti_metrics_output.reset_index()

        # # Add data specs - TODO VT_20220908: where is this being used?
        # tables = ['LexOptiMetrics']
        # for table in tables:
        #     self.add_data_spec(f'Output {table} Rows', outputs[table].shape[0])

        self.logger.debug("Exit")
        return outputs



