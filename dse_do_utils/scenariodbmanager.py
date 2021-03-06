import sqlalchemy
import pandas as pd
from typing import Dict, List
from collections import OrderedDict
import re
from sqlalchemy import exc
from sqlalchemy import Table, Column, String, Integer, Float, ForeignKey, ForeignKeyConstraint


class ScenarioDbTable():
    """Abstract class?"""

    def __init__(self, db_table_name: str, columns_metadata: List[sqlalchemy.Column] = [], constraints_metadata=[]):
        self.db_table_name = ScenarioDbTable.camel_case_to_snake_case(
            db_table_name)  # To make sure it is a proper DB table name. Also allows us to use the scenario table name.
        self.columns_metadata = columns_metadata
        self.constraints_metadata = constraints_metadata
        #         self.create_table_sql = None
        #         self.index_columns = None
        self.dtype = None

    #         self.scenario_primary_foreign_key = Column('scenario_name', String(256), ForeignKey("scenario.scenario_name"), primary_key=True)

    def get_db_table_name(self):
        return self.db_table_name

    def get_df_column_names(self):
        """TODO: what to do if the column names in the DB are different from the column names in the DF?"""
        column_names = []
        for c in self.columns_metadata:
            if isinstance(c, sqlalchemy.Column):
                column_names.append(c.name)
        return column_names

    #         return [c.name for c in self.columns_metadata]

    def create_table_metadata(self, metadata, multi_scenario: bool = False):
        """If multi_scenario, then add a primary key 'scenario_name'"""
        columns_metadata = self.columns_metadata
        constraints_metadata = self.constraints_metadata

        if multi_scenario and (self.db_table_name != 'scenario'):
            # TODO: do we need to exclude the ScenarioDbTable itself? Or is sqlalchemy automatically taking care of duplicate Columns?
            columns_metadata.insert(0, Column('scenario_name', String(256), ForeignKey("scenario.scenario_name"),
                                              primary_key=True, index=True))
            #             columns_metadata.insert(0, self.scenario_primary_foreign_key)
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

    #     def convert_data(self, df):
    #         # By default convert column names to snake_case:
    #         df = ScenarioDbTable.df_column_names_to_snake_case(df)
    #         return df

    @staticmethod
    def camel_case_to_snake_case(name):
        return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()

    @staticmethod
    def df_column_names_to_snake_case(df):
        df.columns = [ScenarioDbTable.camel_case_to_snake_case(x) for x in df.columns]
        return df

    def insert_table_in_db_bulk(self, df, mgr):
        """
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
    def sqlcol(df):
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
#
#########################################################################
class AutoScenarioDbTable(ScenarioDbTable):
    def __init__(self, db_table_name):
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

    def __init__(self, input_db_tables: Dict[str, ScenarioDbTable], output_db_tables: Dict[str, ScenarioDbTable], credentials=None, schema: str = None, echo=False, multi_scenario: bool = False):
        self.schema = schema
        self.input_db_tables = input_db_tables
        self.output_db_tables = output_db_tables
        self.db_tables = OrderedDict(list(input_db_tables.items()) + list(output_db_tables.items()))  # {**input_db_tables, **output_db_tables}  # For compatibility reasons
        self.engine = self.create_database_engine(credentials, schema, echo)
        self.echo = echo
        self.metadata = sqlalchemy.MetaData()
        self.multi_scenario = multi_scenario  # If true, will add a primary key 'scenario_name' to each table
        self.initialize_db_tables_metadata()  # Needs to be done after self.metadata, self.multi_scenario has been set

    #     def __init__(self, db_tables: Dict[str, ScenarioDbTable], credentials=None, schema: str = None, echo=False,
    #                  multi_scenario: bool = False):
    #         self.schema = schema
    #         self.db_tables = db_tables
    #         self.engine = self.create_database_engine(credentials, schema, echo)
    #         self.echo = echo
    #         self.metadata = sqlalchemy.MetaData()
    #         self.multi_scenario = multi_scenario  # If true, will add a primary key 'scenario_name' to each table
    #         self.initialize_db_tables_metadata()  # Needs to be done after self.metadata, self.multi_scenario has been set

    def create_database_engine(self, credentials=None, schema: str = None, echo: bool = False):
        if credentials is not None:
            engine = self.create_db2_engine(credentials, schema, echo)
        else:
            engine = self.create_sqllite_engine(echo)
        return engine

    def create_sqllite_engine(self, echo):
        return sqlalchemy.create_engine('sqlite:///:memory:', echo=echo)

    def get_db2_connection_string(self, credentials, schema: str):
        """Create a DB2 connection string.
        Needs a work-around for DB2 on cloud.ibm.com.
        The option 'ssl=True' doesn't work. Instead use 'Security=ssl'.
        See https://stackoverflow.com/questions/58952002/using-credentials-from-db2-warehouse-on-cloud-to-initialize-flask-sqlalchemy.

        TODO:
        * Not sure the check for the port 50001 is necessary, or if this applies to any `ssl=True`
        * The schema doesn't work properly in db2 on cloud.ibm.com. Instead it automatically creates a schema based on the username.
        * Also tried to use 'schema={schema}', but it didn't work properly.
        * In case ssl=False, do NOT add the option `ssl=False`: doesn't gie an error, but select rows will always return zero rows!
        * TODO: what do we do in case ssl=True, but the port is not 50001?!
        """
        if str(credentials['ssl']).upper() == 'TRUE' and str(credentials['port']) == '50001':
            ssl = '?Security=ssl'  # Instead of 'ssl=True'
        else:
            #         ssl = f"ssl={credentials['ssl']}"  # I.e. 'ssl=True' or 'ssl=False'
            ssl = ''  # For some weird reason, the string `ssl=False` blocks selection from return any rows!!!!
        connection_string = 'db2+ibm_db://{username}:{password}@{host}:{port}/{database}{ssl};currentSchema={schema}'.format(
            username=credentials['username'],
            password=credentials['password'],
            host=credentials['host'],
            port=credentials['port'],
            database=credentials['database'],
            ssl=ssl,
            schema=schema
        )
        return connection_string

    def create_db2_engine(self, credentials, schema: str, echo: bool = False):
        """Create a DB2 engine instance.
        Connection string logic in `get_db2_connection_string`
        """
        connection_string = self.get_db2_connection_string(credentials, schema)
        return sqlalchemy.create_engine(connection_string, echo=echo)

    #     def create_db2_engine(self, credentials, schema: str, echo: bool = False):
    #         connection_string = 'db2+ibm_db://{username}:{password}@{host}:{port}/{database};currentSchema={schema}'.format(
    #             username=credentials['username'],
    #             password=credentials['password'],
    #             host=credentials['host'],
    #             port=credentials['port'],
    #             database=credentials['database'],
    #             schema=schema
    #         )
    #         return sqlalchemy.create_engine(connection_string, echo=echo)

    def initialize_db_tables_metadata(self):
        """To be called from constructor, after engine is 'created'/connected, after self.metadata, self.multi_scenario have been set.
        This will add the  `scenario_name` to the db_table configurations.
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
        self.drop_all_tables()
        #         for scenario_table_name, db_table in self.db_tables.items():
        #             db_table.table_metadata = db_table.create_table_metadata(self.metadata, self.multi_scenario)  # Stores the table schema in the self.metadata

        self.metadata.create_all(self.engine, checkfirst=True)

    def insert_scenarios_in_db(self, inputs={}, outputs={}, bulk: bool = True):
        for table_name, df in inputs.items():
            self.insert_table_in_db(table_name, df, bulk)
        for table_name, df in outputs.items():
            self.insert_table_in_db(table_name, df, bulk)

    def insert_tables_in_db(self, inputs={}, outputs={}, bulk: bool = True, auto_insert: bool = False):
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

    def insert_table_in_db(self, db_table: ScenarioDbTable, df):
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

    def read_scenario_from_db(self, scenario_name: str):
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
        for scenario_table_name, db_table in reversed(self.db_tables.items()):
            sql = f"DELETE FROM {db_table.db_table_name} WHERE scenario_name = '{scenario_name}'"
            self.engine.execute(sql)
        # Delete scenario entry in scenario table:
        sql = f"DELETE FROM SCENARIO WHERE scenario_name = '{scenario_name}'"
        self.engine.execute(sql)

    def replace_scenario_in_db(self, scenario_name: str, inputs={}, outputs={}, bulk=True):
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