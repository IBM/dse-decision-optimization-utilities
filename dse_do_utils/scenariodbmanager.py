# Copyright IBM All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

# -----------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------
# ScenarioDbManager
# -----------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------
# Change notes
# VT 2021-12-01:
# - Cleanup, small documentation and typing hints
# - Make 'multi_scenario' the default option
# -----------------------------------------------------------------------------------

import sqlalchemy
import pandas as pd
from typing import Dict, List
from collections import OrderedDict
import re
from sqlalchemy import exc
from sqlalchemy import Table, Column, String, Integer, Float, ForeignKey, ForeignKeyConstraint

#  Typing aliases
Inputs = Dict[str, pd.DataFrame]
Outputs = Dict[str, pd.DataFrame]


class ScenarioDbTable():
    """Abstract class. Subclass to be able to define table schema definition, i.e. column name, data types, primary and foreign keys.
    Only columns that are specified and included in the DB insert.
    """

    def __init__(self, db_table_name: str, columns_metadata: List[sqlalchemy.Column] = [], constraints_metadata=[]):
        self.db_table_name = ScenarioDbTable.camel_case_to_snake_case(
            db_table_name)  # To make sure it is a proper DB table name. Also allows us to use the scenario table name.
        self.columns_metadata = columns_metadata
        self.constraints_metadata = constraints_metadata
        self.dtype = None

    def get_db_table_name(self) -> str:
        return self.db_table_name

    def get_df_column_names(self) -> List[str]:
        """TODO: what to do if the column names in the DB are different from the column names in the DF?"""
        column_names = []
        for c in self.columns_metadata:
            if isinstance(c, sqlalchemy.Column):
                column_names.append(c.name)
        return column_names

    def create_table_metadata(self, metadata, multi_scenario: bool = False):
        """If multi_scenario, then add a primary key 'scenario_name'."""
        columns_metadata = self.columns_metadata
        constraints_metadata = self.constraints_metadata

        if multi_scenario and (self.db_table_name != 'scenario'):
            columns_metadata.insert(0, Column('scenario_name', String(256), ForeignKey("scenario.scenario_name"),
                                              primary_key=True, index=True))
            constraints_metadata = [ScenarioDbTable.add_scenario_name_to_fk_constraint(fkc) for fkc in
                                    constraints_metadata]

        return Table(self.db_table_name, metadata, *(c for c in (columns_metadata + constraints_metadata)))

    @staticmethod
    def add_scenario_name_to_fk_constraint(fkc: ForeignKeyConstraint):
        """Creates a new ForeignKeyConstraint by adding the `scenario_name`."""
        columns = fkc.column_keys
        refcolumns = [fk.target_fullname for fk in fkc.elements]
        table_name = refcolumns[0].split(".")[0]
        # Create a new ForeignKeyConstraint by adding the `scenario_name`
        columns.insert(0, 'scenario_name')
        refcolumns.insert(0, f"{table_name}.scenario_name")
        return ForeignKeyConstraint(columns, refcolumns)

    @staticmethod
    def camel_case_to_snake_case(name: str) -> str:
        return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()

    @staticmethod
    def df_column_names_to_snake_case(df: pd.DataFrame) -> pd.DataFrame:
        """"Change all columns names from camelCase to snake_case."""
        df.columns = [ScenarioDbTable.camel_case_to_snake_case(x) for x in df.columns]
        return df

    def insert_table_in_db_bulk(self, df: pd.DataFrame, mgr):
        """Insert a DataFrame in the DB using 'bulk' insert, i.e. with one SQL insert.
        (Instead of row-by-row.)
        Args:
            df (pd.DataFrame)
            mgr (ScenarioDbManager)
        """
        table_name = self.get_db_table_name()
        columns = self.get_df_column_names()
        try:
            # TODO: does it make sense to specify the dtype if we have a proper schema?
            df[columns].to_sql(table_name, schema=mgr.schema, con=mgr.engine, if_exists='append', dtype=None,
                               index=False)
        except exc.IntegrityError as e:
            print("++++++++++++Integrity Error+++++++++++++")
            print(f"DataFrame insert/append of table '{table_name}'")
            print(e)

    @staticmethod
    def sqlcol(df: pd.DataFrame) -> Dict:
        dtypedict = {}
        for i, j in zip(df.columns, df.dtypes):
            if "object" in str(j):
                dtypedict.update({i: sqlalchemy.types.NVARCHAR(length=255)})

            if "datetime" in str(j):
                dtypedict.update({i: sqlalchemy.types.DateTime()})

            if "float" in str(j):
                dtypedict.update({i: sqlalchemy.types.Float()})  # precision=10, asdecimal=True

            if "int" in str(j):
                dtypedict.update({i: sqlalchemy.types.INT()})
        return dtypedict


#########################################################################
# AutoScenarioDbTable
#########################################################################
class AutoScenarioDbTable(ScenarioDbTable):
    """Designed to automatically generate the table definition based on the DataFrame.
    Advantages:
    - No need to define a custom ScenarioDbTable class per table
    - Automatically all columns are inserted
    Disadvantages:
    - No primary and foreign key relations. Thus no checks.
    - Missing relationships means Cognos cannot automatically extract a data model
    """
    def __init__(self, db_table_name: str):
        """Need to provide a name for the DB table.
        """
        super().__init__(db_table_name)

    def create_table_metadata(self, metadata, multi_scenario: bool = False):
        return None

    def insert_table_in_db_bulk(self, df, mgr):
        """
        Args:
            df (pd.DataFrame)
            mgr (ScenarioDbManager)
        """
        table_name = self.get_db_table_name()
        if self.dtype is None:
            dtype = ScenarioDbTable.sqlcol(df)
        else:
            dtype = self.dtype
        try:
            # Note that this can use the 'replace', so the table will be dropped automatically and the defintion auto created
            # So no need to drop the table explicitly (?)
            df.to_sql(table_name, schema=mgr.schema, con=mgr.engine, if_exists='replace', dtype=dtype, index=False)
        except exc.IntegrityError as e:
            print("++++++++++++Integrity Error+++++++++++++")
            print(f"DataFrame insert/append of table '{table_name}'")
            print(e)

#########################################################################
#  ScenarioDbManager
#########################################################################


class ScenarioDbManager():
    """
    TODO:
    * Allow insert of tables in inputs/outputs that do not have ScenarioDbTable definitions, like in the original ScenarioDbManager
    These to be inserted after the others. No need for a
    """

    def __init__(self, input_db_tables: Dict[str, ScenarioDbTable], output_db_tables: Dict[str, ScenarioDbTable],
                 credentials=None, schema: str = None, echo: bool = False, multi_scenario: bool = True):
        self.schema = schema
        self.input_db_tables = input_db_tables
        self.output_db_tables = output_db_tables
        self.db_tables = OrderedDict(list(input_db_tables.items()) + list(output_db_tables.items()))  # {**input_db_tables, **output_db_tables}  # For compatibility reasons
        self.engine = self.create_database_engine(credentials, schema, echo)
        self.echo = echo
        self.metadata = sqlalchemy.MetaData()
        self.multi_scenario = multi_scenario  # If true, will add a primary key 'scenario_name' to each table
        self.initialize_db_tables_metadata()  # Needs to be done after self.metadata, self.multi_scenario has been set
        self.read_scenario_table_from_db_callback = None  # For Flask caching in Dash Enterprise

    def create_database_engine(self, credentials=None, schema: str = None, echo: bool = False):
        if credentials is not None:
            engine = self.create_db2_engine(credentials, schema, echo)
        else:
            engine = self.create_sqllite_engine(echo)
        return engine

    def create_sqllite_engine(self, echo: bool):
        return sqlalchemy.create_engine('sqlite:///:memory:', echo=echo)

    #     def get_db2_connection_string(self, credentials, schema: str):
    #         """Create a DB2 connection string.
    #         Needs a work-around for DB2 on cloud.ibm.com.
    #         The option 'ssl=True' doesn't work. Instead use 'Security=ssl'.
    #         See https://stackoverflow.com/questions/58952002/using-credentials-from-db2-warehouse-on-cloud-to-initialize-flask-sqlalchemy.

    #         TODO:
    #         * Not sure the check for the port 50001 is necessary, or if this applies to any `ssl=True`
    #         * The schema doesn't work properly in db2 on cloud.ibm.com. Instead it automatically creates a schema based on the username.
    #         * Also tried to use 'schema={schema}', but it didn't work properly.
    #         * In case ssl=False, do NOT add the option `ssl=False`: doesn't gie an error, but select rows will always return zero rows!
    #         * TODO: what do we do in case ssl=True, but the port is not 50001?!
    #         """
    #         if str(credentials['ssl']).upper() == 'TRUE' and str(credentials['port']) == '50001':
    #             ssl = '?Security=ssl'  # Instead of 'ssl=True'
    #         else:
    #             #         ssl = f"ssl={credentials['ssl']}"  # I.e. 'ssl=True' or 'ssl=False'
    #             ssl = ''  # For some weird reason, the string `ssl=False` blocks selection from return any rows!!!!
    #         connection_string = 'db2+ibm_db://{username}:{password}@{host}:{port}/{database}{ssl};currentSchema={schema}'.format(
    #             username=credentials['username'],
    #             password=credentials['password'],
    #             host=credentials['host'],
    #             port=credentials['port'],
    #             database=credentials['database'],
    #             ssl=ssl,
    #             schema=schema
    #         )
    #         return connection_string

    def get_db2_connection_string(self, credentials, schema: str):
        """Create a DB2 connection string.

        Needs a work-around for DB2 on cloud.ibm.com.
        Workaround: Pass in your credentials like this:

        DB2_credentials = {
            'username': "user1",
            'password': "password1",
            'host': "hostname.databases.appdomain.cloud",
            'port': "30080",
            'database': "bludb",
            'schema': "my_schema", #<- SCHEMA IN DATABASE
            'ssl': "SSL" #<- NOTE: SPECIFY SSL HERE IF TRUE FOR DB2
        }

        The option 'ssl=True' doesn't work. Instead use 'Security=ssl'.
        See https://stackoverflow.com/questions/58952002/using-credentials-from-db2-warehouse-on-cloud-to-initialize-flask-sqlalchemy.

        Notes:
            * The schema doesn't work properly in DB2 Lite version on cloud.ibm.com. Schema names work properly
              with paid versions where you can have multiple schemas
            * SQLAlchemy expects a certain way the SSL is encoded in the connection string.
              This method adapts based on different ways the SSL is defined in the credentials
        """

        if 'ssl' in credentials:
            #    SAVE FOR FUTURE LOGGER MESSAGES...
            #print("SSL Flag detected.")

            #SET THIS IF WE NEED TO SEE IF WE ARE CONNECTING TO A CLOUD DATABASE VS ON PREM (FUTURE?)
            #WE ARE CONNECTING TO A DB2 DATABASE AAS, SO WE NEED TO SET (CHECK) THE SSL FLAG CORRECTLY
            #if("DATABASES.APPDOMAIN.CLOUD" in str(credentials['host']).upper()):
            #    SAVE FOR FUTURE LOGGER MESSAGES...
            #print("DB2 database in the cloud detected based off hostname...")

            #SSL=True IS NOT THE PROPER SYNTAX FOR SQLALCHEMY AND DB2 CLOUD. IT NEEDS TO BE 'ssl=SSL' so we will correct it.

            if(str(credentials['ssl']).upper() == 'TRUE'):
                #print("WARNING! 'SSL':'TRUE' Detected, but it needs to be 'ssl':'SSL' for SQL ALCHEMY. Correcting...")
                credentials['ssl'] = 'SSL'
            elif(str(credentials['ssl']).upper() == 'SSL'):
                # SAVE FOR FUTURE LOGGER MESSAGES...
                #print("SSL Specified correctly for DB2aaS cloud connection.")
                credentials['ssl'] = 'SSL'
            else:
                # print("WARNING! SSL was specified as a none standard value: SSL was not set to True or SSL.")
                pass

            connection_string = 'db2+ibm_db://{username}:{password}@{host}:{port}/{database};currentSchema={schema};SECURITY={ssl}'.format(
                username=credentials['username'],
                password=credentials['password'],
                host=credentials['host'],
                port=credentials['port'],
                database=credentials['database'],
                ssl=credentials['ssl'],
                schema=schema
            )
        else:
            # print(" WARNING! SSL was not specified! Creating connection string without it!")
            connection_string = 'db2+ibm_db://{username}:{password}@{host}:{port}/{database};currentSchema={schema}'.format(
                username=credentials['username'],
                password=credentials['password'],
                host=credentials['host'],
                port=credentials['port'],
                database=credentials['database'],
                schema=schema
            )
        # SAVE FOR FUTURE LOGGER MESSAGES...
        #print("Connection String : " + connection_string)
        return connection_string

    def create_db2_engine(self, credentials, schema: str, echo: bool = False):
        """Create a DB2 engine instance.
        Connection string logic in `get_db2_connection_string`
        """
        connection_string = self.get_db2_connection_string(credentials, schema)
        return sqlalchemy.create_engine(connection_string, echo=echo)

    def initialize_db_tables_metadata(self):
        """To be called from constructor, after engine is 'created'/connected, after self.metadata, self.multi_scenario have been set.
        This will add the `scenario_name` to the db_table configurations.
        This also allows non-bulk inserts into an existing DB (i.e. without running 'create_schema')"""
        for scenario_table_name, db_table in self.db_tables.items():
            db_table.table_metadata = db_table.create_table_metadata(self.metadata,
                                                                     self.multi_scenario)  # Stores the table schema in the self.metadata

    def drop_all_tables(self):
        """Drops all tables as defined in db_tables (if exists)"""
        for scenario_table_name, db_table in self.db_tables.items():
            db_table_name = db_table.db_table_name
            sql = f"DROP TABLE IF EXISTS {db_table_name}"
            #         print(f"Dropping table {db_table_name}")
            r = self.engine.execute(sql)

    def create_schema(self):
        """Drops all tables and re-creates the schema in the DB."""
        self.drop_all_tables()
        self.metadata.create_all(self.engine, checkfirst=True)

    def insert_scenarios_in_db(self, inputs={}, outputs={}, bulk: bool = True):
        for table_name, df in inputs.items():
            self.insert_table_in_db(table_name, df, bulk)
        for table_name, df in outputs.items():
            self.insert_table_in_db(table_name, df, bulk)

    def insert_tables_in_db(self, inputs: Inputs = {}, outputs: Outputs = {}, bulk: bool = True, auto_insert: bool = False):
        """Note: the non-bulk ONLY works if the schema was created! I.e. only when using with self.create_schema.
        TODO: how to set the schema info without clearing the existing schema and thus the whole DB?
        """
        dfs = {**inputs, **outputs}  # Combine all dfs in one dict
        completed_dfs = []
        for scenario_table_name, db_table in self.db_tables.items():
            if scenario_table_name in dfs:
                completed_dfs.append(scenario_table_name)
                if bulk:
                    #                     self.insert_table_in_db_bulk(db_table, dfs[scenario_table_name])
                    db_table.insert_table_in_db_bulk(dfs[scenario_table_name], self)
                else:  # Row by row for data checking
                    self.insert_table_in_db(db_table, dfs[scenario_table_name])
            else:
                print(f"No table named {scenario_table_name} in inputs or outputs")
        # Insert any tables not defined in the schema:
        if auto_insert:
            for scenario_table_name, df in dfs.items():
                if scenario_table_name not in completed_dfs:
                    print(f"Table {scenario_table_name} auto inserted")
                    db_table = AutoScenarioDbTable(scenario_table_name)
                    db_table.insert_table_in_db_bulk(df, self)

    def insert_table_in_db(self, db_table: ScenarioDbTable, df: pd.DataFrame):
        num_exceptions = 0
        max_num_exceptions = 10
        columns = db_table.get_df_column_names()
        #         print(columns)
        # df[columns] ensures that the order of columns in the DF matches that of the SQL table definition. If not, the insert will fail
        for row in df[columns].itertuples(index=False):
            #             print(row)
            stmt = (
                sqlalchemy.insert(db_table.table_metadata).
                    values(row)
            )
            try:
                self.engine.execute(stmt)
            except exc.IntegrityError as e:
                print("++++++++++++Integrity Error+++++++++++++")
                print(e)
                num_exceptions = num_exceptions + 1
            except exc.StatementError as e:
                print("++++++++++++Statement Error+++++++++++++")
                print(e)
                num_exceptions = num_exceptions + 1
            finally:
                if num_exceptions > max_num_exceptions:
                    print(
                        f"Max number of exceptions {max_num_exceptions} for this table exceeded. Stopped inserting more data.")
                    break

    def read_scenario_table_from_db(self, scenario_name: str, scenario_table_name: str) -> pd.DataFrame:
        """
        Load a single table from the DB.
        :param scenario_name: Name of scenario
        :param scenario_table_name: Name of scenario table (not the DB table name)
        :return:
        """
        # print(f"read table {scenario_table_name}")
        if scenario_table_name in self.input_db_tables:
            db_table = self.input_db_tables[scenario_table_name]
        elif scenario_table_name in self.output_db_tables:
            db_table = self.output_db_tables[scenario_table_name]
        else:
            # error!
            raise ValueError(f"Scenario table name '{scenario_table_name}' unknown. Cannot load data from DB.")

        db_table_name = db_table.db_table_name
        sql = f"SELECT * FROM {db_table_name} WHERE scenario_name = '{scenario_name}'"
        df = pd.read_sql(sql, con=self.engine)
        if db_table_name != 'scenario':
            df = df.drop(columns=['scenario_name'])

        return df

    def set_table_read_callback(self, table_read_callback=None):
        """Sets a callback function to read a table from a scenario
        """
        #     print(f"Set callback to {table_read_callback}")
        self.read_scenario_table_from_db_callback = table_read_callback

    def read_scenario_table_from_db_cached(self, scenario_name: str, scenario_table_name: str) -> pd.DataFrame:
        """For use with Flask caching. Default implementation.
        In case no caching has been configured. Simply calls the regular method `read_scenario_table_from_db`.

        For caching:
        1. Specify a callback procedure in `read_scenario_table_from_db_callback` that uses a hard-coded version of a ScenarioDbManager,
        which in turn calls the regular method `read_scenario_table_from_db`
        """
        # 1. Override this method and call a procedure that uses a hard-coded version of a ScenarioDbManager,
        # which in turn calls the regular method `read_scenario_table_from_db`

        # return self.read_scenario_table_from_db(scenario_name, scenario_table_name)
        if self.read_scenario_table_from_db_callback is not None:
            df = self.read_scenario_table_from_db_callback(scenario_name, scenario_table_name)  # NOT a method!
        else:
            df = self.read_scenario_table_from_db(scenario_name, scenario_table_name)
        return df

    def read_scenario_tables_from_db_cached(self, scenario_name: str, input_table_names:List[str]=None, output_table_names:List[str]=None):
        """For use with Flask caching. Loads data for selected input and output tables.
        Same as `read_scenario_tables_from_db`, but calls `read_scenario_table_from_db_cached`"""

        if input_table_names is None:  # load all tables by default
            input_table_names = list(self.input_db_tables.keys())
            if 'Scenario' in input_table_names: input_table_names.remove('Scenario')  # Remove the scenario table
        if output_table_names is None:  # load all tables by default
            output_table_names = self.output_db_tables.keys()

        inputs = {}
        for scenario_table_name in input_table_names:
            # print(f"read input table {scenario_table_name}")
            inputs[scenario_table_name] = self.read_scenario_table_from_db_cached(scenario_name, scenario_table_name)

        outputs = {}
        for scenario_table_name in output_table_names:
            # print(f"read output table {scenario_table_name}")
            outputs[scenario_table_name] = self.read_scenario_table_from_db_cached(scenario_name, scenario_table_name)
        return inputs, outputs

    def read_scenario_tables_from_db(self, scenario_name: str, input_table_names:List[str]=None, output_table_names:List[str]=None):
        """Loads data for selected input and output tables.
        If either list is names is None, will load all tables as defined in db_tables configuration.
        """
        if input_table_names is None:  # load all tables by default
            input_table_names = list(self.input_db_tables.keys())
            if 'Scenario' in input_table_names: input_table_names.remove('Scenario')  # Remove the scenario table
        if output_table_names is None:  # load all tables by default
            output_table_names = self.output_db_tables.keys()

        inputs = {}
        for scenario_table_name in input_table_names:
            inputs[scenario_table_name] = self.read_scenario_table_from_db(scenario_name, scenario_table_name)
        outputs = {}
        for scenario_table_name in output_table_names:
            outputs[scenario_table_name] = self.read_scenario_table_from_db(scenario_name, scenario_table_name)
        return inputs, outputs

    def read_scenario_from_db(self, scenario_name: str) -> (Inputs, Outputs):
        """Single scenario load.
        Reads all tables for a single scenario.
        Returns all tables in one dict"""
        inputs = {}
        for scenario_table_name, db_table in self.input_db_tables.items():
            db_table_name = db_table.db_table_name
            sql = f"SELECT * FROM {db_table_name} WHERE scenario_name = '{scenario_name}'"
            df = pd.read_sql(sql, con=self.engine)
            #         print(db_table_name)
            inputs[scenario_table_name] = df

        outputs = {}
        for scenario_table_name, db_table in self.output_db_tables.items():
            db_table_name = db_table.db_table_name
            sql = f"SELECT * FROM {db_table_name} WHERE scenario_name = '{scenario_name}'"
            df = pd.read_sql(sql, con=self.engine)
            #         print(db_table_name)
            outputs[scenario_table_name] = df

        inputs, outputs = ScenarioDbManager.delete_scenario_name_column(inputs, outputs)
        return inputs, outputs

    def read_scenarios_from_db(self, scenario_names: List[str] = []):
        """Multi scenario load.
        Reads all tables from set of scenarios"""
        where_scenarios = ','.join([f"'{n}'" for n in scenario_names])

        inputs = {}
        for scenario_table_name, db_table in self.input_db_tables.items():
            db_table_name = db_table.db_table_name
            sql = f"SELECT * FROM {db_table_name} WHERE scenario_name in ({where_scenarios})"
            #             print(sql)
            df = pd.read_sql(sql, con=self.engine)
            #         print(db_table_name)
            inputs[scenario_table_name] = df
            print(f"Read {df.shape[0]} rows and {df.shape[1]} columns into {scenario_table_name}")

        outputs = {}
        for scenario_table_name, db_table in self.output_db_tables.items():
            db_table_name = db_table.db_table_name
            sql = f"SELECT * FROM {db_table_name} WHERE scenario_name in ({where_scenarios})"
            #             print(sql)
            df = pd.read_sql(sql, con=self.engine)
            #         print(db_table_name)
            outputs[scenario_table_name] = df
            print(f"Read {df.shape[0]} rows and {df.shape[1]} columns into {scenario_table_name}")

        return inputs, outputs

    def delete_scenario_from_db(self, scenario_name: str):
        """Deletes all rows associated with a given scenario.
        Note that it only deletes rows from tables defined in the self.db_tables, i.e. will NOT delete rows in 'auto-inserted' tables!
        Must do a 'cascading' delete to ensure not violating FK constraints. In reverse order of how they are inserted.
        Also deletes entry in scenario table
        TODO: do within one session/cursor, so we don't have to worry about the order of the delete?
        """
        insp = sqlalchemy.inspect(self.engine)
        for scenario_table_name, db_table in reversed(self.db_tables.items()):
            if insp.has_table(db_table.db_table_name, schema=self.schema):
                sql = f"DELETE FROM {db_table.db_table_name} WHERE scenario_name = '{scenario_name}'"
                self.engine.execute(sql)

        # for scenario_table_name, db_table in reversed(self.db_tables.items()):
        #     sql = f"DELETE FROM {db_table.db_table_name} WHERE scenario_name = '{scenario_name}'"
        #     self.engine.execute(sql)

        # Delete scenario entry in scenario table:
        sql = f"DELETE FROM SCENARIO WHERE scenario_name = '{scenario_name}'"
        self.engine.execute(sql)

    def replace_scenario_in_db(self, scenario_name: str, inputs: Inputs = {}, outputs: Outputs = {}, bulk=True):
        """Replace a single full scenario in the DB. If doesn't exists, will insert.
        Only inserts tables with an entry defined in self.db_tables (i.e. no `auto_insert`).
        Will first delete all rows associated with a scenario_name.
        Will set/overwrite the scenario_name in all dfs, so no need to add in advance.
        Assumes schema has been created.
        Note: there is no difference between dfs in inputs or outputs, i.e. they are inserted the same way."""
        # Step 1: delete scenario if exists
        self.delete_scenario_from_db(scenario_name)
        # Step 2: add scenario_name to all dfs
        inputs = ScenarioDbManager.add_scenario_name_to_dfs(scenario_name, inputs)
        outputs = ScenarioDbManager.add_scenario_name_to_dfs(scenario_name, outputs)
        # Step 3: insert scenario_name in scenario table
        sql = f"INSERT INTO SCENARIO (scenario_name) VALUES ('{scenario_name}')"
        self.engine.execute(sql)
        # Step 4: (bulk) insert scenario
        self.insert_single_scenario_tables_in_db(inputs=inputs, outputs=outputs, bulk=bulk)

    @staticmethod
    def add_scenario_name_to_dfs(scenario_name: str, inputs: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        """Adds a `scenario_name` column to each df.
        Or overwrites all values of that column already exists.
        This avoids to need for the MultiScenarioManager when loading and storing single scenarios."""
        outputs = {}
        for scenario_table_name, df in inputs.items():
            df['scenario_name'] = scenario_name
            outputs[scenario_table_name] = df
        return outputs

    def insert_single_scenario_tables_in_db(self, inputs={}, outputs={}, bulk: bool = True):
        """Specifically for single scenario replace/insert.
        Does NOT insert into the `scenario` table.
        No `auto_insert`, i.e. only df matching db_tables.
        """
        dfs = {**inputs, **outputs}  # Combine all dfs in one dict
        for scenario_table_name, db_table in self.db_tables.items():
            if scenario_table_name != 'Scenario':
                if scenario_table_name in dfs:
                    df = dfs[scenario_table_name]
                    print(f"Inserting {df.shape[0]} rows and {df.shape[1]} columns in {scenario_table_name}")
                    #                 display(df.head(3))
                    if bulk:
                        db_table.insert_table_in_db_bulk(df, self)
                    else:  # Row by row for data checking
                        self.insert_table_in_db(db_table, df)
                else:
                    print(f"No table named {scenario_table_name} in inputs or outputs")

    @staticmethod
    def delete_scenario_name_column(inputs, outputs):
        """Drops the column `scenario_name` from any df in either inputs or outputs.
        This is used to create a inputs/outputs combination similar to loading a single scenario from the DO Experiment.
        """
        new_inputs = {}
        new_outputs = {}
        for scenario_table_name, df in inputs.items():
            if 'scenario_name' in df.columns:
                df = df.drop(columns=['scenario_name'])
                new_inputs[scenario_table_name] = df
        for scenario_table_name, df in outputs.items():
            if 'scenario_name' in df.columns:
                df = df.drop(columns=['scenario_name'])
                new_outputs[scenario_table_name] = df
        return new_inputs, new_outputs

    def get_scenarios_df(self):
        """Return all scenarios in df. Result is indexed by `scenario_name`."""
        sql = f"SELECT * FROM SCENARIO"
        df = pd.read_sql(sql, con=self.engine).set_index(['scenario_name'])
        return df

# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#  Input Tables
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

class ScenarioTable(ScenarioDbTable):
    def __init__(self, db_table_name: str = 'scenario'):
        columns_metadata = [
            Column('scenario_name', String(256), primary_key=True),
        ]
        super().__init__(db_table_name, columns_metadata)


class ParameterTable(ScenarioDbTable):
    def __init__(self, db_table_name: str = 'parameters', extended_columns_metadata: List[Column] = []):
        columns_metadata = [
            Column('param', String(256), primary_key=True),
            Column('value', String(256), primary_key=False),
        ]
        columns_metadata.extend(extended_columns_metadata)
        super().__init__(db_table_name, columns_metadata)


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#  Output Tables
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class KpiTable(ScenarioDbTable):
    def __init__(self, db_table_name: str = 'kpis'):
        columns_metadata = [
            Column('NAME', String(256), primary_key=True),
            Column('VALUE', Float(), primary_key=False),
        ]
        super().__init__(db_table_name, columns_metadata)

class BusinessKpiTable(ScenarioDbTable):
    def __init__(self, db_table_name: str = 'business_kpi', extended_columns_metadata: List[Column] = []):
        columns_metadata = [
            Column('kpi', String(256), primary_key=True),
            Column('value', Float(), primary_key=False),
        ]
        columns_metadata.extend(extended_columns_metadata)
        super().__init__(db_table_name, columns_metadata)