# Copyright IBM All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

# -----------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------
# ScenarioManager
# -----------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
import os
import glob
import pandas as pd


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

    # def __init__(self, model_name=None, scenario_name=None, load_from_excel=False, excel_input_file_name=None,
    # write_to_excel=False, excel_output_file_name=None, local_root=None):
    def __init__(self, model_name=None, scenario_name=None, local_root=None):
        self.model_name = model_name
        self.scenario_name = scenario_name
        # self.load_from_excel = load_from_excel
        # self.excel_input_file_name = excel_input_file_name
        # self.write_to_excel = write_to_excel
        # self.excel_output_file_name = excel_output_file_name
        self.local_root = local_root
        self.inputs = None  # Or set the an empty dict?
        self.outputs = None

    def load_data(self, load_from_excel=False, excel_file_name=None):
        """Load data from either the DO scenario, or an Excel spreadsheet.
        The Excel spreadsheet is expected to be in the `datasets` folder, either in WS or local.

        Returns:
            inputs, outputs (tuple of dicts): the inputs and outputs dictionary of DataFrames
        """
        if load_from_excel:
            self.inputs, self.outputs = self.load_data_from_excel(excel_file_name)
        else:
            self.inputs, self.outputs = ScenarioManager.load_data_from_scenario_s(model_name=self.model_name,
                                                                                  scenario_name=self.scenario_name)
        return self.inputs, self.outputs

    # def write_data(self, write_to_excel=False):
    #     """"Write data to either the DO scenario or an Excel spreadsheet
    #     TODO: Unlike with the load_data, allow for both writing to the scenario and to Excel. Use different APIs and pass the relevant arguments only to their specific APIs.
    #     I.e. move some of the properties passed in the constructor to a dedicated write_to_scenario or write_to_excel API.
    #     """
    #     if write_to_excel:
    #         ScenarioManager.write_data_to_excel(excel_file_name=self.excel_output_file_name, inputs=self.inputs, outputs=self.outputs, copy_to_csv=True)
    #     else:
    #         ScenarioManager.write_data_into_scenario(self.model_name, self.scenario_name, self.inputs, self.outputs)


    def get_data_directory(self):
        """Returns the path to the datasets folder.

        :return: path to the datasets folder
        """
        return os.path.join(self.get_root_directory(), 'datasets')  # Do we need to add an empty string at the end?

    def get_root_directory(self):
        """Return the root directory of the file system.
        If system is WS, it will return the DSX root, otherwise the directory specified in the local_root.
        Raises:
            ValueError if root directory doesn't exist.
        """
        if ScenarioManager.env_is_dsx():  # Note that this is False in DO! So don't run in DO
            root_dir = os.environ['DSX_PROJECT_DIR']
        else:
            if self.local_root is None:
                raise ValueError('The local_root should be specified if loading from an Excel file outside of WS')
            root_dir = self.local_root
        # Assert that root_dir actually exists
        if not os.path.isdir(root_dir):
            raise ValueError("Root directory `{}` does not exist.".format(root_dir))
        return root_dir

    # -----------------------------------------------------------------
    # Read and write from/to DO scenario - value-added
    # -----------------------------------------------------------------
    def load_data_from_scenario(self):
        """Loads the data from a DO scenario"""
        self.inputs, self.outputs = ScenarioManager.load_data_from_scenario_s(self.model_name, self.scenario_name)
        return self.inputs, self.outputs

    def write_data_into_scenario(self):
        """Writes the data into a DO scenario. Create new scenario and write data."""
        return ScenarioManager.write_data_into_scenario_s(self.model_name, self.scenario_name, self.inputs,
                                                          self.outputs)

    def add_data_into_scenario(self, inputs=None, outputs=None):
        """Adds data to a DO scenario. If table exists, does an overwrite/replace."""
        return ScenarioManager.add_data_into_scenario_s(self.model_name, self.scenario_name, inputs, outputs)

    def replace_data_in_scenario(self, inputs=None, outputs=None):
        """Replaces all input, output or both.
        Note: you will need to specify the inputs or outputs you want to replace explicitly as input arguments.
        It will NOT get them from self.inputs or self.outputs!
        In this way, you can control which to update. E.g. after a solve, only update the outputs, not the inputs.
        """
        return ScenarioManager.replace_data_into_scenario_s(self.model_name, self.scenario_name, inputs, outputs)

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
    @staticmethod
    def get_do_scenario(model_name, scenario_name):
        """Returns a DO scenario.

        Args:
            model_name (str): the name of the DO model
            scenario_name (str): the name of the scenario

        Returns:
            A dd-scenario.Container of type `scenario`

        Raises:
            ValueError: When either the model_name or the scenario_name doesn't match an existing entity.
        """
        client = ScenarioManager._get_dd_client()
        dd_model_builder = client.get_model_builder(name=model_name)
        if dd_model_builder is None:
            raise ValueError('No DO model with name `{}` exists'.format(model_name))
        scenario = dd_model_builder.get_scenario(name=scenario_name)
        if scenario is None:
            raise ValueError('No DO scenario with name `{}` exists in model `{}`'.format(scenario_name, model_name))
        return scenario

    @staticmethod
    def load_data_from_scenario_s(model_name, scenario_name):
        """Loads the data from a DO scenario"""
        scenario = ScenarioManager.get_do_scenario(model_name, scenario_name)
        # Load all input data as a map { data_name: data_frame }
        inputs = scenario.get_tables_data(category='input')
        outputs = scenario.get_tables_data(category='output')
        return (inputs, outputs)

    @staticmethod
    def write_data_into_scenario_s(model_name, scenario_name, inputs=None, outputs=None, template_scenario_name=None):
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
        client = ScenarioManager._get_dd_client()
        dd_model_builder = client.get_model_builder(name=model_name)
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

    @staticmethod
    def add_data_into_scenario_s(model_name, scenario_name, inputs=None, outputs=None):
        """Adds tables in existing scenario.

        Replaces table, if table exists.
        Assumes scenario exists. Does not explicitly clear existing tables.
        Could be used in post-processing.
        """
        scenario = ScenarioManager.get_do_scenario(model_name, scenario_name)
        if inputs is not None:
            for table in inputs:
                scenario.add_table_data(table, inputs[table], category='input')
        if outputs is not None:
            for table in outputs:
                scenario.add_table_data(table, outputs[table], category='output')

    @staticmethod
    def replace_data_into_scenario_s(model_name, scenario_name, inputs=None, outputs=None):
        """Replaces all input, output or both.

        If input/output are not None, clears inputs/outputs first
        Assumes scenario exists. Does explicitly clear all existing input/output tables.
        TODO: test. Not sure this actually works
        """
        client = ScenarioManager._get_dd_client()
        scenario = ScenarioManager.get_do_scenario(model_name, scenario_name)
        if inputs is not None:
            ScenarioManager.clear_scenario_data(client, scenario, category='input')
            for table in inputs:
                scenario.add_table_data(table, inputs[table], category='input')
        if outputs is not None:
            ScenarioManager.clear_scenario_data(client, scenario, category='output')
            for table in outputs:
                scenario.add_table_data(table, outputs[table], category='output')

    # @staticmethod
    # def load_scenario_from_data(scenario, data, category='input'):
    #     """"
    #     TODO: test. Not sure this actually works
    #     """
    #     for table in data:
    #         scenario.add_table_data(table, data[table], category=category)

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
    def create_new_scenario(client, model_builder, new_scenario_name, template_scenario_name=None):
        """
        Creates a new scenario from a template. The template is found either from the template_scenario_name,
        or if this is None, from the new_scenario_name. If a scenario with the new name already exists,
        all input and output tables are cleared. Thereby keeping the solve code.
        Creates a new blank scenario if a scenario with this name doesn't exist.

        Args:
            client (dd_scenario.Client): Client managing the DO model
            model_builder (dd_scenario.ModelBuilder): The DO model
            new_scenario_name (str): Name for the new scenario
            template_scenario_name (str): Name of an existing scenario

        Returns:
            A dd_scenario.Container of type scenario
        Raises:
            ValueError: new_scenario_name is None
            ValueError: new_scenario_name is the same as template_scenario_name
        """
        if new_scenario_name is None: raise ValueError('The new_scenario_name cannot be None')
        if template_scenario_name is not None:
            if (new_scenario_name != template_scenario_name): raise ValueError(
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
    def get_kpis_table_as_dataframe(mdl):
        """Return a DataFrame with the KPI names and values in the mdl.
        This table is compatible with the representation in DO4WS and can be updated in the scenario.

        Args:
            mdl (docplex.mp.model)

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

    def load_data_from_excel(self, excel_file_name):
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

    def write_data_to_excel(self, excel_file_name=None, copy_to_csv=False):
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

        root_dir = self.get_root_directory()
        # Save the regular Excel file:
        excel_file_path_1 = os.path.join(root_dir, 'datasets', excel_file_name + '.xlsx')
        writer_1 = pd.ExcelWriter(excel_file_path_1, engine='xlsxwriter')
        ScenarioManager.write_data_to_excel_s(writer_1, inputs=self.inputs, outputs=self.outputs)
        writer_1.save()
        # Save the csv copy:
        if copy_to_csv:
            excel_file_path_2 = os.path.join(root_dir, 'datasets', excel_file_name + 'to_csv.xlsx')
            csv_excel_file_path_2 = os.path.join(root_dir, 'datasets', excel_file_name + '_xlsx.csv')
            writer_2 = pd.ExcelWriter(excel_file_path_2, engine='xlsxwriter')
            ScenarioManager.write_data_to_excel_s(writer_2, inputs=self.inputs, outputs=self.outputs)
            writer_2.save()
            os.rename(excel_file_path_2, csv_excel_file_path_2)

    # -----------------------------------------------------------------
    # Read and write from/to Excel - base functions
    # -----------------------------------------------------------------
    @staticmethod
    def load_data_from_excel_s(xl, table_index_sheet='_table_index_'):
        """
        Create dataFrames from the sheets of the Excel file.
        Store in dictionary df_dict with table_name as key.
        The table_name is either the name of the sheet, or the table_name as defined in the table_index_sheet.
        TODO: Test allow for distinction between input and output via the index-sheet

        Args:
            xl (pandas.ExcelFile): Excel file
            table_index_sheet (str): Name of table index sheet

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
                    if ('category' in table_index_df.columns.values):  # TODO: test!
                        category = table_index_df.loc[sheet].category

                if category == 'output':
                    outputs[table_name] = xl.parse(sheet)
                else:
                    inputs[table_name] = xl.parse(sheet)
        return inputs, outputs

    @staticmethod
    def _create_truncted_post_fixed_name(long_name, max_length, index):
        """Create a trunced name post-fixed with '_<index>' where the total length of the string <= max_length"""
        post_fix = '_' + str(index)
        return long_name[:max_length - len(post_fix)] + post_fix

    @staticmethod
    def _create_unique_abbreviated_name(long_name, max_length, existing_names):
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
    def write_data_to_excel_s(writer, inputs=None, outputs=None, table_index_sheet='_table_index_'):
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
    def load_data_from_csv(self, csv_directory, input_csv_name_pattern="*.csv", output_csv_name_pattern=None, **kwargs):
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
    def load_data_from_csv_s(csv_directory, csv_name_pattern="*.csv", **kwargs):
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

    def write_data_to_csv(self):
        """Write inputs and/or outputs to .csv files in the root/datasets folder.

        Args: None
        Returns: None
        """
        # root_dir = self.get_root_directory()
        # csv_directory = os.path.join(root_dir, 'datasets')
        csv_directory = self.get_data_directory()
        ScenarioManager.write_data_to_csv_s(csv_directory, inputs=self.inputs, outputs=self.outputs)

    @staticmethod
    def write_data_to_csv_s(csv_directory, inputs=None, outputs=None):
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
        if outputs is not None:
            for table_name, df in outputs.items():
                file_path = os.path.join(csv_directory, table_name + ".csv")
                print("Writing {}".format(file_path))
                df.to_csv(file_path, index=False)

    # -----------------------------------------------------------------
    # Utils
    # -----------------------------------------------------------------

    @staticmethod
    def env_is_dsx():
        """Return true if environment is DSX"""
        return 'DSX_PROJECT_DIR' in os.environ

    @staticmethod
    def _get_dd_client():
        """Return the Client managing the DO scenario.
        Only reason for this separate API is to place the import Client in one place,
        so that editing this code on a local laptop generates one error.
        Returns: new dd_scenario.Client
        """
        from dd_scenario import Client
        return Client()

    def print_table_names(self):
        """Print the names of the input and output tables. For development and debugging."""
        print("Input tables: {}".format(", ".join(self.inputs.keys())))
        print("Output tables: {}".format(", ".join(self.outputs.keys())))