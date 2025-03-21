# Copyright IBM All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

# -----------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------
# DataManager
# -----------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------
import types

import pandas as pd
from typing import List, Dict, Tuple, Optional

#  Typing aliases
Inputs = Dict[str, pd.DataFrame]
Outputs = Dict[str, pd.DataFrame]


class DataManager(object):
    """A DataManager is a container of original scenario and intermediate data.

    It typically contains the input and output dictionaries with DataFrames that came from
    or will be inserted into a DO scenario.
    In addition, it will hold any intermediate data.
    It holds methods that operate on and convert the data.
    When used in combination with an optimization engine, it should not contain the
    docplex code that creates or interacts with the docplex Model. (That is the task of the OptimizationEngine.)

    One of the reasons to separate the DataManager from the OptimizationEngine is to re-use the DataManager,
    e.g. for output visualization notebooks.

    A typical DataManager:
        * Prepares the input DataFrames (like selecting and renaming columns and indexing) and assigns them to a direct attribute.
        * Contains a set of methods that create intermediate data ('pre-processing'). Intermediate data will also be assigned as a direct member property.
    """

    def __init__(self, inputs: Optional[Inputs] = None, outputs: Optional[Outputs] = None):
        self.inputs = inputs
        self.outputs = outputs

        # Parameters:
        self.params: Optional[pd.DataFrame] = None
        self.param = types.SimpleNamespace()

    def prepare_data_frames(self):
        if (self.inputs is not None) and (len(self.inputs) > 0):
            self.prepare_input_data_frames()
        if (self.outputs is not None) and (len(self.outputs) > 0):
            self.prepare_output_data_frames()

    def prepare_input_data_frames(self):
        """Placeholder to process input data frames, in particular to set the index and
        to assign dataframes to a direct property of the DataManager.
        Make sure to test if table-name exists in input dict so we can re-use this class in e.g.
        DashEnterprise apps where not the whole scenario is loaded.

        Example::

            if 'MyTable' in self.inputs:
                self.my_table = self.inputs['MyTable'].set_index('Id', verify_integrity=True)

        """
        pass
        # self.set_parameters()  # TODO: do we always want to call set_parameter here?

    def prepare_output_data_frames(self):
        """Placeholder to process output data frames.
        Processes the default 'kpis' table.
        """
        if 'kpis' in self.outputs and self.outputs['kpis'].shape[0] > 0:
            """Note: for some reason an imported scenario uses 'Name' and 'Value' as column names!"""
            df = self.outputs['kpis']
            df.columns= df.columns.str.upper()
            self.kpis = (df
                         .set_index(['NAME'], verify_integrity = True)
                         )

    def print_hello(self):
        """FOR TESTING: Print some hello string.

        Prints some message. To test reloading of the package from a notebook.
        Usage::

            (In notebook cell #1)
            from dse_do_utils import DataManager
            dm = DataManager()
            (In cell #2)
            dm.print_hello()

        Change the test of the string. Upload the module to WSL.
        If testing autoreload, rerun the second cell only. Verify it prints the updated string.
        If testing imp.reload, rerun the notebook from the start.
        """
        print("Hello world #1")

    # def pp_parameters(self):
    #     """
    #     Deprecated
    #     Returns:
    #
    #     """
    #     return self.prep_parameters()

    def set_parameters(self):
        """Set the parameters as properties of the self.param object.
        This allows for easy access to the parameters, e.g. `dm.param.time_limit`
        To be overridden. Make sure to call the `super().set_parameters()`

        Creates the self.param SimpleNamespace to be able to add the individual parameter properties.
        Creates the self.params pd.DataFrame to be able to easily extract the parameter values.
        """
        self.params = self.prep_parameters()
        self.param = types.SimpleNamespace()

        #Examples of extraction of parameters:
        # self.param.time_limit = self.get_parameter_value(self.params, 'solveTimeLimit', param_type='int', default_value=600)
        # Supported param_type values are int, float, str, bool, datetime

    def prep_parameters(self) -> pd.DataFrame:
        """Pre-process the Parameter(s) input table.
        Assumes the inputs contains a table named `Parameter` or `Parameters` with key `param` and column `value`.
        Otherwise, creates a blank DataFrame instance.
        """
        if 'Parameter' in self.inputs.keys():
            params = self.inputs['Parameter'].set_index(['param'], verify_integrity=True)
        elif 'Parameters' in self.inputs.keys():
            params = self.inputs['Parameters'].set_index(['param'], verify_integrity=True)
        else:
            params = pd.DataFrame(columns=['param', 'value']).set_index('param')
        # self.params = params
        return params


    @staticmethod
    def get_parameter_value(params, param_name: str, param_type: Optional[str] = None, default_value=None,
                            value_format: str = '%Y-%m-%d %H:%M:%S'):
        """
        Get value of parameter from the parameter table (DataFrame).
        Note that if the input table has a mix of data types in the value column, Pandas can change the data type of a
        parameter depending on what other values are used in other rows.
        This requires the explicit conversion to the expected data type.

        Args:
            params (indexed DataFrame with parameters): Index = 'param', value in 'value' column.
            param_name (str): Name of parameter.
            param_type (str): Type of parameter. Valid param_type values are int, float, str, bool, datetime.
            default_value: Value if param_name not in index.
            value_format (str): Format for datetime conversion.

        Returns:
        """
        from datetime import datetime
        # assert 'param' in params.index #Not absolutely necessary, as long as single index
        assert 'value' in params.columns
        if param_name in params.index:
            raw_param = params.loc[param_name].value
            if param_type == 'int':
                # Unfortunately, Pandas may sometimes convert a 0 to a FALSE, etc.
                if str(raw_param).lower() in ['false', 'f', 'no', 'n', '0', '0.0']:
                    param = 0
                elif str(raw_param).lower() in ['true', 't', 'yes', 'y', '1', '1.0']:
                    param = 1
                else:
                    param = int(
                        float(raw_param))  # by first doing the float, a value of '1.0' will be converted correctly
            elif param_type == 'float':
                # Unfortunately, Pandas may sometimes convert a 0 to a FALSE, etc.
                if str(raw_param).lower() in ['false', 'f', 'no', 'n', '0', '0.0']:
                    param = 0
                elif str(raw_param).lower() in ['true', 't', 'yes', 'y', '1', '1.0']:
                    param = 1
                else:
                    param = float(raw_param)
            elif param_type == 'str':
                param = str(raw_param)
            elif param_type == 'bool':
                # Note that the function `bool()` does not do what you expect!
                # Note that the type of the raw_param could be a Python bool, string, or Numpy Bool
                # (see http://joergdietrich.github.io/python-numpy-bool-types.html)
                # param = (str(raw_param) == 'True')
                param = (str(raw_param).lower() in ['true', 'yes', 'y', 't', '1', '1.0'])
            elif param_type == 'datetime':
                # Make more robust:
                # 1. Remove any excess quotes if a string (When forcing a value to be a quoted string in Excel)
                # 2. If it already is a datetime, do not convert (Excel read may return a datetime already)
                if isinstance(raw_param, datetime):
                    param = raw_param
                else:
                    raw_param = raw_param.strip('"')
                    param = datetime.strptime(raw_param, value_format)
            else:
                param = raw_param
        else:
            print(f'Warning: {param_name} not in Parameters. Using default value = {default_value}')
            # If datetime, the default value can be a string
            import six  # For Python 2 and 3 compatibility of testing string instance
            if param_type == 'datetime' and isinstance(default_value, six.string_types):
                param = datetime.strptime(default_value, value_format)
            else:
                param = default_value
        return param

    @staticmethod
    def df_crossjoin_si(df1: pd.DataFrame, df2: pd.DataFrame, **kwargs) -> pd.DataFrame:
        """
        Make a cross join (cartesian product) between two dataframes by using a constant temporary key.
        Assumes both input dataframes have a single index column.
        Returns a dataframe with a MultiIndex that is the cartesian product of the indices of the input dataframes.
        See: https://github.com/pydata/pandas/issues/5401
        See https://mkonrad.net/2016/04/16/cross-join--cartesian-product-between-pandas-dataframes.html

        Args:
            df1 (DataFrame): dataframe 1
            df2 (DataFrame): dataframe 2
            kwargs keyword arguments that will be passed to pd.merge()
        Returns:
            (DataFrame) cross join of df1 and df2
        """
        # The copy() allows the original df1 to select a sub-set of columns of another DF without a Pandas warning
        df1 = df1.copy()
        df2 = df2.copy()
        df1['_tmpkey'] = 1
        df2['_tmpkey'] = 1

        res = pd.merge(df1, df2, on='_tmpkey', **kwargs).drop('_tmpkey', axis=1)
        indices = list(df1.index.names) + list(df2.index.names)  # Ensures the index columns are named properly
        res.index = pd.MultiIndex.from_product((df1.index, df2.index),
                                               names=indices)  # without names omits the names of the index columns

        df1.drop('_tmpkey', axis=1, inplace=True)
        df2.drop('_tmpkey', axis=1, inplace=True)

        return res

    # Multi-index DFs:
    @staticmethod
    def df_crossjoin_mi(df1: pd.DataFrame, df2: pd.DataFrame, **kwargs) -> pd.DataFrame:
        """
        Make a cross join (cartesian product) between two dataframes by using a constant temporary key.
        Assumes both input dataframes have a (single or multi) index.
        Returns a dataframe with a MultiIndex that is the cartesian product of the indices of the input dataframes.
        Creates a named MultiIndex if both input dataframes have their indices named.
        Otherwise will return an unnamed multi-index.

        Args:
            df1 (DataFrame) input df1
            df2 (DataFrame) input df2
            kwargs keyword arguments that will be passed to pd.merge()
        Returns:
            (DataFrame) cross join of df1 and df2
        """
        # The copy() allows the original df1 to select a sub-set of columns of another DF without a Pandas warning
        df1 = df1.copy()
        df2 = df2.copy()
        indices = list(df1.index.names) + list(df2.index.names)
        df1 = df1.reset_index()
        df2 = df2.reset_index()

        df1['_tmpkey'] = 1
        df2['_tmpkey'] = 1

        res = pd.merge(df1, df2, on='_tmpkey', **kwargs).drop('_tmpkey', axis=1)
        if not None in indices:
            # If a None is in indices, the set_index will fail. Thus return non-indexed DF.
            res = res.set_index(indices)

        df1.drop('_tmpkey', axis=1, inplace=True)
        df2.drop('_tmpkey', axis=1, inplace=True)

        return res

    @staticmethod
    def df_crossjoin_ai(df1: pd.DataFrame, df2: pd.DataFrame, **kwargs) -> pd.DataFrame:
        """
        Cross-join 'Any Index'
        Make a cross join (cartesian product) between two dataframes by using a constant temporary key.
        Accepts dataframes that are single or multi-indexed with named and un-named indices.

        Args:
            df1 (DataFrame) input df1
            df2 (DataFrame) input df2
            kwargs keyword arguments that will be passed to pd.merge()
        Returns:
            (DataFrame) cross join of df1 and df2
        """
        # if isinstance(df1.index, pd.core.index.MultiIndex) or isinstance(df2.index, pd.core.index.MultiIndex):  # pd.core.index.MultiIndex is deprecated
        if isinstance(df1.index, pd.MultiIndex) or isinstance(df2.index, pd.MultiIndex):  # Fix for Pandas 1.0
            return DataManager.df_crossjoin_mi(df1, df2, **kwargs)
        else:
            return DataManager.df_crossjoin_si(df1, df2, **kwargs)

    @staticmethod
    def apply_and_concat(dataframe, field, func, column_names):
        """Adds multiple columns in one lambda apply function call.

        Based on https://stackoverflow.com/questions/23690284/pandas-apply-function-that-returns-multiple-values-to-rows-in-pandas-dataframe

        Usage::

            def my_function(my_input_value):
                my_output_value_1 = 1
                my_output_value_2 = 2
                return (my_output_value1, my_output_value_2)

            df = apply_and_concat(df, 'my_input_column_name', my_function, ['my_output_column_name_1','my_output_column_name_2'])

        df should have the column 'my_input_column_name'.
        Result is that df will have 2 new columns: 'my_output_column_name_1' and 'my_output_column_name_2'

        .. deprecated:: 0.2.2
            Same can be done with plain Pandas.

        Alternative in plain Pandas::

            df[['my_output_column_name_1','my_output_column_name_2']] = df.apply(lambda row : pd.Series(my_function(row.my_input_column_name)), axis = 1)


        Args:
            dataframe (DataFrame): The DataFrame that the function is applied to
            field (str): the name of the input data column of dataframe
            func: the function that will be applied. Should have one input argument and return a tuple with N elements.
            column_names (list of str): The names of the N output columns. Should match the number of values in the function return tuple.

        Returns:
            modified dataframe with N new columns
        """
        return pd.concat((
            dataframe,
            dataframe[field].apply(
                lambda cell: pd.Series(func(cell), index=column_names))), axis=1)

    # @staticmethod
    # def apply_and_concat_row(dataframe, func, column_names, **kwargs):
    #     """Generic function that adds multiple columns to the dataframe, based on the call to `func(row, **kwargs)` returning multiple values.
    #     **kwargs are added as arguments to the function, in addition to the row.
    #
    #     Usage::
    #
    #         def my_function(row, arg1=1):
    #             return (1 * arg1, 2 * arg1)
    #
    #         df = apply_and_concat_row(df, my_function, ['col1','col2'], arg1=7)
    #
    #     .. deprecated:: 0.2.2
    #         Same can be done with plain Pandas::
    #             df[['my_output_column_name_1','my_output_column_name_2']] = df.apply(lambda row : pd.Series(my_function(row.my_input_column_name)), axis = 1)
    #
    #     Args:
    #         dataframe (DataFrame): The DataFrame that the function is applied to
    #         func: the function that will be applied. Should have one input argument for the row, optionally a set of named input arguments and return a tuple with N elements.
    #         column_names (list of str): The names of the N output columns. Should match the number of values in the function return tuple.
    #         **kwargs (Optional): named arguments passed to the func
    #     """
    #     return pd.concat((
    #         dataframe,
    #         dataframe.apply(
    #             lambda row: pd.Series(func(row, **kwargs), index=column_names), axis=1)), axis=1, sort=False)

    @staticmethod
    def extract_solution(df: pd.DataFrame, extract_dvar_names: Optional[List[str] | Dict[str, str]] = None, drop_column_names: List[str] = None,
                         drop: bool = True, epsilon: float = None, round_decimals: int = None,
                         solution_column_name_post_fix: str = 'Sol',
                         allow_mixed_type_columns: bool = False) -> pd.DataFrame:
        """Generalized routine to extract a solution value.
        Can remove the dvar column from the df to be able to have a clean df for export into scenario.

        In some cases, CPLEX extracted values for continuous dvars can have very small values instead of zeros.
        If epsilon has a value, this method will drop these small values to zero.
        And it will assume the values need to be positive, so it clips negative values at zero.

        In some case, CPLEX extracted values for integer dvars can have very small values from the rounded integer value.
        If round_decimals is set to 0, the solution values will be rounded to the nearest integer.
        Use values larger than zero to round continuous dvars to their required precision.

        Args:
            df: DataFrame
            extract_dvar_names: list of column names with CPLEX dvars, or a Dict[str, str]
                                where the keys are the dvar column names and the values the name of the solution column
            drop_column_names: columns to be dropped (can be different and in addition to drop)
            drop: if True drops all columns in extract_dvar_names
            epsilon (float): if not None, drop values below threshold to zero and clip negative values at zero
            round_decimals (int): round the solution value by number of decimals. If None, no rounding.
            If 0, rounding to integer value.
            solution_column_name_post_fix (str): Postfix for the name of the solution column. Default = 'Sol'
            allow_mixed_type_columns (bool): If True, will allow the column not to have the `solution_value` attribute, i.e. be a plain Python value, not a CPLEX dvar or expression
        """


        if extract_dvar_names is not None:
            if isinstance(extract_dvar_names, list):
                dvar_column_dict = {dvar_name: f'{dvar_name}{solution_column_name_post_fix}' for dvar_name in extract_dvar_names}
            elif isinstance(extract_dvar_names, dict):
                dvar_column_dict = extract_dvar_names
            else:
                # dvar_column_dict = {}
                raise TypeError("Input argument 'extract_dvar_names' must be either a List[str] or a Dict[str, str]")
            for xDVarName, solution_column_name in dvar_column_dict.items():
                if xDVarName in df.columns:
                    # solution_column_name = f'{xDVarName}Sol'
                    # df[solution_column_name] = [dvar.solution_value for dvar in df[xDVarName]]
                    if allow_mixed_type_columns:
                        df[solution_column_name] = [dvar.solution_value if hasattr(dvar, 'solution_value') else dvar for
                                                dvar in df[xDVarName]]  # VT_20241029: allow expression to be a constant
                    else:
                        df[solution_column_name] = [dvar.solution_value for dvar in df[xDVarName]]
                    if drop:
                        df = df.drop([xDVarName], axis=1)
                    if epsilon is not None:
                        df.loc[df[solution_column_name] < epsilon, solution_column_name] = 0
                        df[solution_column_name] = df[solution_column_name].clip(lower=0)
                    if round_decimals is not None:
                        df[solution_column_name] = df[solution_column_name].round(round_decimals)
                        if round_decimals == 0:
                            df[solution_column_name] = df[solution_column_name].astype(int)
                else:
                    # Note (VT_20240401): for backward compatibility reasons, for now, do not throw an exception or print a warning
                    # print(f"Warning: The column {xDVarName} doesn't exist in the DataFrame. Valid column: {df.columns}")
                    pass

        # if extract_dvar_names is not None:
        #     for xDVarName in extract_dvar_names:
        #         if xDVarName in df.columns:
        #             solution_column_name = f'{xDVarName}Sol'
        #             df[solution_column_name] = [dvar.solution_value for dvar in df[xDVarName]]
        #             if drop:
        #                 df = df.drop([xDVarName], axis=1)
        #             if epsilon is not None:
        #                 df.loc[df[solution_column_name] < epsilon, solution_column_name] = 0
        #                 df[solution_column_name] = df[solution_column_name].clip(lower=0)
        #             if round_decimals is not None:
        #                 df[solution_column_name] = df[solution_column_name].round(round_decimals)
        if drop and drop_column_names is not None:
            for column in drop_column_names:
                if column in df.columns:
                    df = df.drop([column], axis=1)
        return df

    # def drop_small_epsilon_values(self, df: pd.DataFrame, columns: List[str], epsilon: float = 0.0001) -> pd.DataFrame:
    #     """Drops small values of extracted CPLEX continuous dvar solutions to zero.
    #     In some cases, CPLEX extracted values can have very small values instead of zeros.
    #     This method drops these small values to zero.
    #     It also assumes the values need to be positive, so it clips all negative values at zero.
    #     Args:
    #         df: DataFrame
    #         columns: List of column names
    #         epsilon: threshold value
    #     """
    #     for col in columns:
    #         if col in df.columns:
    #             df.loc[df[col] < epsilon, col] = 0
    #             df[col] = df[col].clip(lower=0)
    #     return df

    def get_raw_table_by_name(self, table_name: str) -> Optional[pd.DataFrame]:
        """Get the 'raw' (non-indexed) table from inputs or outputs."""
        if self.inputs is not None and table_name in self.inputs:
            df = self.inputs[table_name]
        elif self.outputs is not None and table_name in self.outputs:
            df = self.outputs[table_name]
        else:
            df = None
        return df

    def print_inputs_outputs_summary(self):
        """Prints a summary of the input and output data.
        Prints the names of all input and output tables, along with the column names and the number of rows and columns."""
        for table_name, df in self.inputs.items():
            print(f"Input {table_name}: {df.shape[0]} rows, {df.shape[1]} columns: {', '.join([col for col in df.columns])}")
        for table_name, df in self.outputs.items():
            print(f"Output {table_name}: {df.shape[0]} rows, {df.shape[1]} columns: {', '.join([col for col in df.columns])}")
