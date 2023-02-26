# Copyright IBM Corp. 2021, 2022
# IBM Confidential Source Code Materials
# This Source Code is subject to the license and security terms contained in the License.txt file contained in this source code package.
import enum
import logging
import types
from abc import abstractmethod, ABC
from dse_do_utils import DataManager
from dse_do_utils.datamanager import Outputs
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

    def __init__(self, inputs=None, outputs=None, log_level=None):
        super().__init__(inputs, outputs)

        # Create a custom logger
        # self.logger = self.create_logger(log_level)
        self.logger = logging.getLogger()

        # Parameters:
        self.params = None
        self.param = types.SimpleNamespace()

        self.dtypes: Dict = self.get_default_dtypes()

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
        # self.param.n_threads = self.get_parameter_value(
        #     self.params,
        #     param_name='numberThreads',
        #     param_type='int',
        #     default_value=0)

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

    def prepare_output_data_frames(self, dtypes=None):
        super().prepare_output_data_frames()
        self.logger.debug("Enter")

        self.kpis = self.prepare_df(
            self.outputs.get('kpis'),
            index_columns=['NAME'],
            value_columns=['VALUE'],
            dtypes=dtypes
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
            dtypes: map of column data types
            data_specs_key: data specs key
            verify_integrity: flag to verify integrity when setting the index

        Returns:
            df: dataframe

        TODO: move to CoreDataManager
        """

        dtypes = dtypes if dtypes is not None else self.dtypes

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
        """
        return {}
    ########################################################################
    # Logger (TODO: review)
    ########################################################################
    def create_logger(self, log_level: int = None) -> logging.Logger:
        """DEPRECATED
        Create logger

        Args:
            log_level: log level, by default log_level is None
                       and a logger set to CRITICAL log level will be created
                       otherwise, a logger is set to the level specified
                       by log_level
        """
        log_level_enum = LogLevelEnum()
        logger = logging.getLogger(self.__class__.__name__)

        if log_level is None or log_level not in log_level_enum.LEVELS.keys():
            log_level = 'CRITICAL'

        logger.setLevel(getattr(log_level_enum, log_level))

        # Create handlers
        # Stop progagate custom handler settings to root logger
        logger.propagate = False
        n_handlers = len(logger.handlers[:])
        if n_handlers == 0:
            self.add_logger_handler(log_level_enum, log_level, logger=logger)
        else:
            for handler in logger.handlers[:]:
                logger.removeHandler(handler)

            self.add_logger_handler(log_level_enum, log_level, logger=logger)
        return logger

    def add_logger_handler(self, log_level_enum, log_level, logger):
        """DEPRECATED
        Add logger handler

        Args:
            log_level_enum: log level enum object
            log_level: log level
        """
        c_handler = logging.StreamHandler()
        c_handler.setLevel(getattr(log_level_enum, log_level))

        # Create formatters and add it to handlers
        c_format = logging.Formatter('%(asctime)s %(levelname)s: %(module)s.%(funcName)s - %(message)s')
        c_handler.setFormatter(c_format)

        # Add handlers to the logger
        logger.addHandler(c_handler)
