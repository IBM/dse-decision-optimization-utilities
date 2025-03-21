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

    def prepare_input_data_frames(self):
        super().prepare_input_data_frames()
        # self.logger.debug("Enter")

        self.set_parameters()

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

    def prepare_output_data_frames(self):
        """
        """
        super().prepare_output_data_frames()
        self.logger.debug("Enter")

        self.kpis = self.prepare_df(
            self.outputs.get('kpis'),
            index_columns=['NAME'],
            value_columns=['VALUE'],
            dtypes=None,
        )

    @abstractmethod
    def pre_processing(self) -> None:
        pass

    @abstractmethod
    def post_processing(self) -> None:
        pass

    @abstractmethod
    def get_outputs(self) -> Outputs:
        outputs = dict()
        outputs['kpis'] = self.kpis.reset_index()
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
