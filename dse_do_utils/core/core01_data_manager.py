# Copyright IBM Corp. 2021, 2022
# IBM Confidential Source Code Materials
# This Source Code is subject to the license and security terms contained in the License.txt file contained in this source code package.
import enum
import logging
import types
from abc import abstractmethod, ABC
from dse_do_utils import DataManager
from dse_do_utils.datamanager import Outputs, Inputs
from typing import List, Dict, Optional, Type
import pandas as pd


class LogLevelEnum():
    """DEPRECATED"""
    CRITICAL: int = logging.CRITICAL
    ERROR: int = logging.ERROR
    WARNING: int = logging.WARNING
    INFO: int = logging.INFO
    DEBUG: int = logging.DEBUG

    LEVELS: Dict = {
        'CRITICAL': CRITICAL,
        'ERROR': ERROR,
        'WARNING': WARNING,
        'INFO': INFO,
        'DEBUG': DEBUG
    }


class Core01DataManager(DataManager):
    """To be used in conjunction with the CoreOptimizationEngine

    Core01 features:
    - logger
    - parameter extraction
    - prepare_df and dtypes
    """

    def __init__(self, inputs: Optional[Inputs] = None, outputs: Optional[Outputs] = None, log_level: Optional[str] = None):
        super().__init__(inputs, outputs)

        # Create a custom logger
        # self.logger = self.create_logger(log_level)

        # `__name__` returns `dse_do_utils.core.core01_data_manager`
        # `self.__name__` returns an error
        # `self.__module__` returns `fruit.data_manager`
        # `self.__class__.__name__` returns `FruitDataManager`
        # `self.__class__.__module__` returns `fruit.data_manager` (same as `self.__module__`)

        # VT20230607: changed to __name__ from self.__module__

        self.logger = logging.getLogger(__name__)  # `__name__` is Python best practice
        if log_level is not None:
            self.logger.setLevel(log_level)

        # # Parameters:
        # self.params = None
        # self.param = types.SimpleNamespace()

        self.dtypes: Dict = self.get_default_dtypes()

        # Output data
        self.kpis: Optional[pd.DataFrame] = None
        self.business_kpis: Optional[pd.DataFrame] = pd.DataFrame(columns=['kpi', 'value']).set_index('kpi')

        # Optimization Progress Tracking
        self.optimization_progress_output: Optional[pd.DataFrame] = pd.DataFrame(columns=['run_id', 'progress_seq', 'metric_type', 'metric_name',
                                                                  'metric_value', 'metric_text_value']).set_index(['run_id', 'progress_seq', 'metric_type', 'metric_name'])

    def prepare_input_data_frames(self):
        super().prepare_input_data_frames()
        # self.logger.debug("Enter")

        self.set_parameters()

    def prepare_output_data_frames(self):
        super().prepare_output_data_frames()
        # self.logger.debug("Enter")

        self.kpis = self.prepare_df(
            self.outputs.get('kpis'),
            index_columns=['NAME'],
            value_columns=['VALUE'],
            dtypes=None,
        )

        self.business_kpis = self.prepare_output_df(
            output_table_name='BusinessKpi',
            index_columns=['kpi'],
            value_columns=['value'],
            dtypes=None,
        )

        self.optimization_progress_output = self.prepare_output_df(
            output_table_name='OptimizationProgress',
            index_columns=['progress_seq', 'metric_type', 'metric_name'],
            value_columns=['metric_value', 'metric_text_value'],
            dtypes={
                'progress_seq': int,
                'metric_type': str,
                'metric_name': str,
                'metric_value': float,
                'metric_text_value': str,
            }
        )

    def set_parameters(self):
        """Core01 parameters:
            - solveTimeLimit: int = 600
            - threads: int = 0
            - removeZeroQuantityOutputRecords: bool = True
            - enableLPNames: bool = False
        """
        super().set_parameters()

        self.param.time_limit = self.get_parameter_value(self.params, 'solveTimeLimit', param_type='int', default_value=600)
        self.param.remove_zero_quantity_output_records = self.get_parameter_value(
            self.params,
            param_name='removeZeroQuantityOutputRecords',
            param_type='bool',
            default_value=False)

        self.param.threads = self.get_parameter_value(self.params, 'threads', param_type='int',
                                                      default_value=0)  # default 0 implies no limit

        self.param.mip_gap = self.get_parameter_value(
            self.params,
            'mipGap',
            param_type='float',
            default_value=0
        )

        self.param.enable_lp_names = self.get_parameter_value(
            self.params,
            param_name='enableLPNames',
            param_type='bool',
            default_value=False)

        self.param.handle_unscaled_infeasibilities = self.get_parameter_value(
            self.params,
            param_name='handleUnscaledInfeasibilities',
            param_type='bool',
            default_value=False)

        self.param.log_solution_quality_metrics = self.get_parameter_value(
            self.params,
            param_name='logSolutionQualityMetrics',
            param_type='bool',
            default_value=False)

        self.param.enable_optimization_progress_tracking = self.get_parameter_value(
            self.params,
            param_name='enable_optimization_progress_tracking',
            param_type='bool',
            default_value=False)

    def pre_processing(self) -> None:
        self.clear_optimization_progress()

    @abstractmethod
    def post_processing(self) -> None:
        pass

    @abstractmethod
    def get_outputs(self) -> Outputs:
        outputs = dict()
        outputs['kpis'] = self.kpis.reset_index()
        outputs['BusinessKpi'] = self.business_kpis.reset_index()
        outputs['OptimizationProgress'] = self.optimization_progress_output.reset_index()
        return outputs

    ########################################################################
    #
    ########################################################################
    def prepare_input_df(self,
                         input_table_name: str,
                         index_columns: Optional[List[str]] = None,
                         value_columns: Optional[List[str]] = None,
                         optional_columns: Optional[List[str]] = None,
                         dtypes: Optional[Dict] = None):
        """Convenience method for prepare_df on input tables."""
        return self.prepare_df(self.inputs.get(input_table_name), index_columns, value_columns, optional_columns, dtypes, data_specs_key=input_table_name)

    def prepare_output_df(self,
                         output_table_name: str,
                         index_columns: Optional[List[str]] = None,
                         value_columns: Optional[List[str]] = None,
                         optional_columns: Optional[List[str]] = None,
                         dtypes: Optional[Dict] = None,):
        """Convenience method for prepare_df on output tables."""
        return self.prepare_df(self.outputs.get(output_table_name), index_columns, value_columns, optional_columns, dtypes, data_specs_key=output_table_name)

    def prepare_df(self,
                   df: Optional[pd.DataFrame],
                   index_columns: Optional[List[str]] = None,
                   value_columns: Optional[List[str]] = None,
                   optional_columns: Optional[List[str]] = None,
                   dtypes: Optional[Dict] = None,
                   data_specs_key: str = None,
                   verify_integrity: bool = True) -> pd.DataFrame:
        """
        Set the index of the df. Cast the column data types.
        If df doesn't exist, create an empty DataFrame.

        Args:
            df: dataframe
            index_columns: index column names
            value_columns: value column names
            optional_columns:
            dtypes: map of column data types. Adds and overrides values in self.dtypes
            data_specs_key: data specs key
            verify_integrity: flag to verify integrity when setting the index

        Returns:
            df: dataframe
        """

        # dtypes = dtypes if dtypes is not None else self.dtypes
        # Merge local and global dtypes:
        default_dtypes = self.dtypes if self.dtypes is not None else {}
        override_dtypes = dtypes if dtypes is not None else {}
        dtypes = default_dtypes | override_dtypes  # merge of dicts, where values in override take priority

        if df is not None:
            # Processing on existing dataframe
            df = df.where(pd.notnull(df), None)  # Replace NaN with None
            # df = df.replace({float('NaN'): None})  # TODO: this is faster. Validate.

            # Construct applicable data types
            # applicable_dtypes = dict()
            # for column_name in df.columns:
            #     if column_name in dtypes:
            #         applicable_dtypes[column_name] = dtypes[column_name]
            # df = df.astype(applicable_dtypes)

            # Set index and verify integrity
            if index_columns is not None:
                df = df.set_index(index_columns, verify_integrity=verify_integrity)

            # Validate that all value_columns exist
            if value_columns is not None:
                try:
                    _ = df[value_columns]
                except KeyError:
                    # TODO log missing columns
                    missing_cols = [c for c in value_columns if c not in df.columns]
                    raise KeyError(f'Missing columns: {missing_cols} for specs {data_specs_key}')

            # Add optional columns with None values
            if optional_columns is not None:
                for column_name in optional_columns:
                    if column_name not in df.columns:
                        df[column_name] = None

        else:
            # Create an empty dataframe with columns and index
            all_columns = []
            if index_columns is not None:
                all_columns.extend(index_columns)

            if value_columns is not None:
                all_columns.extend(value_columns)

            if optional_columns is not None:
                all_columns.extend(optional_columns)

            df = pd.DataFrame(columns=all_columns).set_index(index_columns)
            # df = self.prepare_df(df)  # VT-2022-0608: why call again? The df is empty

        # Set dtypes
        applicable_dtypes = dict()
        for column_name in df.columns:
            if column_name in dtypes:
                applicable_dtypes[column_name] = dtypes[column_name]
        df = df.astype(applicable_dtypes)

        return df

    def get_default_dtypes(self) -> Dict[str, Type]:
        """Return a Dict with default dtypes by column-name (key).
        To be overridden. Make sure to extend with call to super.
        dtypes = super().get_default_dtypes()
        dtypes.update({'my_key':'my_value})
        """
        return {}

    def remove_zero_quantity_output(self, df: pd.DataFrame, column_name: str, table_name: str = 'unspecified',
                                    threshold: float = 0) -> pd.DataFrame:
        """Removes rows from df where a (solution) column has zero values, or less than the threshold.
        Uses parameter `remove_zero_quantity_output_records`. If False, will not remove rows.
        Logs (`INFO`) number and percentage of removed rows.

        Usage::
            def post_processing(self):
                self.my_table_output = self.remove_zero_quantity_output(df=self.my_table_output,
                                                                      column_name='my_sol',
                                                                      table_name='MyTableOutput')

        Args:
            df (pd.DataFrame): a df, typically an output table
            column_name (str): name of column in df. Typically represents the solution of a dvar
            table_name (str): name of the df/output table. Only used for debugging and logging.
            threshold (float): threshold value. Default zero.

        Returns:
            df (pd.DataFrame): df with rows removed
        """
        if self.param.remove_zero_quantity_output_records:
            mask = df.eval(f"{column_name} <= {threshold}")
            self.logger.info(
                f"Removing {mask.sum():,} zero-quantity out of total of {df.shape[0]:,} "
                f"rows from {table_name}. New size = {df[~mask].shape[0]:,} == "
                f"{df[~mask].shape[0] / df.shape[0]:.1%} of original")
            df = df[~mask]
        return df

    ########################################################################
    # Optimization Progress Tracking
    ########################################################################
    def clear_optimization_progress(self):
        """Clear rows in optimization_progress_output and initialize with column and index. Needs to be called as part of pre-processing
        Returns:

        """
        """Clear rows in optimization_progress_output and initialize with column and index."""
        self.optimization_progress_output = pd.DataFrame(columns=['run_id', 'progress_seq', 'metric_type', 'metric_name',
                                                                  'metric_value', 'metric_text_value']).set_index(['run_id', 'progress_seq', 'metric_type', 'metric_name'])

    def add_optimization_progress(self, data: List[Dict]):
        """Add rows to optimization_progress_output. To be called from engine
        """
        new_progress_df = pd.DataFrame(data).set_index(['run_id', 'progress_seq', 'metric_type', 'metric_name'])
        if self.optimization_progress_output is not None and self.optimization_progress_output.shape[0] > 0:
            # Concatenating with an empty df will be deprecated in Pandas
            self.optimization_progress_output = pd.concat([self.optimization_progress_output, new_progress_df])
        else:
            self.optimization_progress_output = new_progress_df

    def get_optimization_progress_as_wide_df(self) -> (pd.DataFrame, List[str]):
        """Get the Optimization Progress data in wide form, which makes it easier to visualize.
        Includes both engine metrics and KPIs.
        Returns:
            df - index=['progress_seq'], columns=['solve_time', 'objective_value', 'objective_bound', 'objective_gap', 'search_status', 'event_type', 'solve_status']
            kpis (List[str]): List of KPI names
        """
        # The challenge is that the pivot operations wil fail
        if self.optimization_progress_output.shape[0] == 0:
            df = pd.DataFrame(columns=['run_id', 'progress_seq', 'solve_time', 'objective_value', 'objective_bound', 'objective_gap', 'search_status', 'event_type', 'solve_status']).set_index(['progress_seq'])
            kpis = []
            return df, kpis

        df1 = self.optimization_progress_output.query("metric_type == 'engine' & metric_value.notnull()").reset_index()
            #  [['progress_seq', 'metric_name', 'metric_value']]

        df_pivot_1 = df1.pivot(columns='metric_name', index='progress_seq', values='metric_value')[
            ['solve_time', 'objective_value', 'objective_bound', 'objective_gap']]   # TODO: only extract these columns if they exist

        df2 = self.optimization_progress_output.query("metric_type == 'engine' & metric_text_value.notnull() & metric_text_value != 'None'").reset_index()[
            ['progress_seq', 'metric_name', 'metric_text_value']]
        df_pivot_2 = df2.pivot(columns='metric_name', index='progress_seq', values='metric_text_value')
            #  [['search_status', 'event_type', 'solve_status']]   # TODO: only extract these columns if they exist

        df3 = self.optimization_progress_output.query("metric_type == 'kpi'").reset_index()[['run_id', 'progress_seq','metric_name','metric_value']]
        df_pivot_3 = df3.pivot(columns='metric_name', index='progress_seq', values='metric_value')

        df_pivot = df_pivot_1.join(df_pivot_2, rsuffix='_right').join(df_pivot_3, rsuffix='_right')  # rsuffix to make more robust against overlapping columns
        df = df_pivot
        df.columns = df.columns.values

        # Fill NaN in KPIs with the previous row values
        # This can happen due to an 'ObjBound' event that reduces the bound, but has no solution.
        df = df.ffill()

        kpis = df3.metric_name.unique().tolist()

        return df, kpis

    def get_kpi_value(self, kpi_name: str):
        """
        For use in dashboard (and other reporting) to get the value of a KPI in the kpis DataFrame.
        """
        try:
            kpi_value = self.kpis.at[kpi_name, 'VALUE']
        except KeyError:
            self.logger.warning(f"KeyError: KPI '{kpi_name}' not found in kpis DataFrame.")
            kpi_value = 0
        return kpi_value

    def get_business_kpi_value(self, kpi_name: str):
        """
        For use in dashboard (and other reporting) to get the value of a Business KPI in the kpis DataFrame.
        """
        try:
            kpi_value = self.business_kpis.at[kpi_name, 'value']  # TODO: incorporate the business_kpis DataFrame in the Core01DataManager
        except AttributeError:
            self.logger.warning(f"AttributeError: business_kpis DataFrame not found.")
            kpi_value = 0
        except KeyError:
            self.logger.warning(f"KeyError: KPI '{kpi_name}' not found in business_kpis DataFrame.")
            kpi_value = 0
        return kpi_value

    ########################################################################
    # Logger (TODO: review)
    ########################################################################
    # def create_logger(self, log_level: int = None) -> logging.Logger:
    #     """DEPRECATED
    #     Create logger
    #
    #     Args:
    #         log_level: log level, by default log_level is None
    #                    and a logger set to CRITICAL log level will be created
    #                    otherwise, a logger is set to the level specified
    #                    by log_level
    #     """
    #     log_level_enum = LogLevelEnum()
    #     logger = logging.getLogger(self.__class__.__name__)
    #
    #     if log_level is None or log_level not in log_level_enum.LEVELS.keys():
    #         log_level = 'CRITICAL'
    #
    #     logger.setLevel(getattr(log_level_enum, log_level))
    #
    #     # Create handlers
    #     # Stop progagate custom handler settings to root logger
    #     logger.propagate = False
    #     n_handlers = len(logger.handlers[:])
    #     if n_handlers == 0:
    #         self.add_logger_handler(log_level_enum, log_level, logger=logger)
    #     else:
    #         for handler in logger.handlers[:]:
    #             logger.removeHandler(handler)
    #
    #         self.add_logger_handler(log_level_enum, log_level, logger=logger)
    #     return logger

    # def add_logger_handler(self, log_level_enum, log_level, logger):
    #     """DEPRECATED
    #     Add logger handler
    #
    #     Args:
    #         log_level_enum: log level enum object
    #         log_level: log level
    #     """
    #     c_handler = logging.StreamHandler()
    #     c_handler.setLevel(getattr(log_level_enum, log_level))
    #
    #     # Create formatters and add it to handlers
    #     c_format = logging.Formatter('%(asctime)s %(levelname)s: %(module)s.%(funcName)s - %(message)s')
    #     c_handler.setFormatter(c_format)
    #
    #     # Add handlers to the logger
    #     logger.addHandler(c_handler)
