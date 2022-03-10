# Copyright IBM All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

# -----------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------
# ScenarioDbManager
# -----------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------
# Change notes:
# VT 2021-12-27:
# - FK checks in SQLite. Avoids the hack in a separate Jupyter cell.
# - Transactions
# - Removed `ScenarioDbTable.camel_case_to_snake_case(db_table_name)` from ScenarioDbTable constructor
# - Cleanup and documentation
# VT 2021-12-22:
# - Cached read of scenarios table
# VT 2021-12-01:
# - Cleanup, small documentation and typing hints
# - Make 'multi_scenario' the default option
# -----------------------------------------------------------------------------------
import pathlib
import zipfile
from abc import ABC
from multiprocessing.pool import ThreadPool

import sqlalchemy
import pandas as pd
from typing import Dict, List, NamedTuple, Any, Optional
from collections import OrderedDict
import re
from sqlalchemy import exc, MetaData, select
from sqlalchemy import Table, Column, String, Integer, Float, ForeignKey, ForeignKeyConstraint

#  Typing aliases
from dse_do_utils import ScenarioManager

Inputs = Dict[str, pd.DataFrame]
Outputs = Dict[str, pd.DataFrame]


class ScenarioDbTable(ABC):
    """Abstract class. Subclass to be able to define table schema definition, i.e. column name, data types, primary and foreign keys.
    Only columns that are specified and included in the DB insert.
    """

    def __init__(self, db_table_name: str, columns_metadata: List[sqlalchemy.Column] = [], constraints_metadata=[]):
        """
        Warning: Do not use mixed case names for the db_table_name.
        Supplying a mixed-case is not working well and is causing DB FK errors.
        Therefore, for now, ensure db_table_name is all lower-case.
        Currently, the code does NOT prevent from using mixed-case. It just generates a warning.

        Also, will check db_table_name against some reserved words, i.e. ['order']

        :param db_table_name: Name of table in DB. Do NOT use MixedCase! Will cause odd DB errors. Lower-case works fine.
        :param columns_metadata:
        :param constraints_metadata:
        """
        self.db_table_name = db_table_name
        # ScenarioDbTable.camel_case_to_snake_case(db_table_name)  # To make sure it is a proper DB table name. Also allows us to use the scenario table name.
        self.columns_metadata = columns_metadata
        self.constraints_metadata = constraints_metadata
        self.dtype = None
        if not db_table_name.islower() and not db_table_name.isupper(): ## I.e. is mixed_case
            print(f"Warning: using mixed case in the db_table_name {db_table_name} may cause unexpected DB errors. Use lower-case only.")

        reserved_table_names = ['order', 'parameter', 'group']  # TODO: add more reserved words for table names
        if db_table_name in reserved_table_names:
            print(f"Warning: the db_table_name '{db_table_name}' is a reserved word. Do not use as table name.")
        self._sa_column_by_name = None  # Dict[str, sqlalchemy.Column] Will be generated dynamically first time it is needed.

    def get_db_table_name(self) -> str:
        return self.db_table_name

    def get_df_column_names(self) -> List[str]:
        """TODO: what to do if the column names in the DB are different from the column names in the DF?"""
        column_names = []
        for c in self.columns_metadata:
            if isinstance(c, sqlalchemy.Column):
                column_names.append(c.name)
        return column_names

    def get_sa_table(self) -> Optional[sqlalchemy.Table]:
        """Returns the SQLAlchemy Table. Can be None if table is a AutoScenarioDbTable and not defined in Python code."""
        return self.table_metadata

    def get_sa_column(self, db_column_name) -> Optional[sqlalchemy.Column]:
        """Returns the SQLAlchemy.Column with the specified name.
        Uses the self.table_metadata (i.e. the sqlalchemy.Table), so works both for pre-defined tables and self-reflected tables like AutoScenarioDbTable
        """
        # Grab column directly from sqlalchemy.Table, see https://docs.sqlalchemy.org/en/14/core/metadata.html#accessing-tables-and-columns
        if (self.table_metadata is not None) and (db_column_name in self.table_metadata.c):
            return self.table_metadata.c[db_column_name]
        else:
            return None

    def create_table_metadata(self, metadata, engine, schema, multi_scenario: bool = False) -> sqlalchemy.Table:
        """If multi_scenario, then add a primary key 'scenario_seq'.

        engine, schema is used only for AutoScenarioDbTable to get the Table (metadata) by reflection
        """
        columns_metadata = self.columns_metadata
        constraints_metadata = self.constraints_metadata

        if multi_scenario and (self.db_table_name != 'scenario'):
            columns_metadata.insert(0, Column('scenario_seq', Integer(), ForeignKey("scenario.scenario_seq"),
                                              primary_key=True, index=True))
            constraints_metadata = [ScenarioDbTable.add_scenario_seq_to_fk_constraint(fkc) for fkc in
                                    constraints_metadata]

        return Table(self.db_table_name, metadata, *(c for c in (columns_metadata + constraints_metadata)))

    @staticmethod
    def add_scenario_name_to_fk_constraint(fkc: ForeignKeyConstraint):
        """DEPRECATED
        Creates a new ForeignKeyConstraint by adding the `scenario_name`."""
        columns = fkc.column_keys
        refcolumns = [fk.target_fullname for fk in fkc.elements]
        table_name = refcolumns[0].split(".")[0]
        # Create a new ForeignKeyConstraint by adding the `scenario_name`
        columns.insert(0, 'scenario_name')
        refcolumns.insert(0, f"{table_name}.scenario_name")
        # TODO: `deferrable=True` doesn't seem to have an effect. Also, deferrable is illegal in DB2!?
        return ForeignKeyConstraint(columns, refcolumns)  #, deferrable=True

    @staticmethod
    def add_scenario_seq_to_fk_constraint(fkc: ForeignKeyConstraint):
        """Creates a new ForeignKeyConstraint by adding the `scenario_seq`."""
        columns = fkc.column_keys
        refcolumns = [fk.target_fullname for fk in fkc.elements]
        table_name = refcolumns[0].split(".")[0]
        # Create a new ForeignKeyConstraint by adding the `scenario_seq`
        columns.insert(0, 'scenario_seq')
        refcolumns.insert(0, f"{table_name}.scenario_seq")
        # TODO: `deferrable=True` doesn't seem to have an effect. Also, deferrable is illegal in DB2!?
        return ForeignKeyConstraint(columns, refcolumns)  #, deferrable=True

    @staticmethod
    def camel_case_to_snake_case(name: str) -> str:
        return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()

    @staticmethod
    def df_column_names_to_snake_case(df: pd.DataFrame) -> pd.DataFrame:
        """"Change all columns names from camelCase to snake_case."""
        df.columns = [ScenarioDbTable.camel_case_to_snake_case(x) for x in df.columns]
        return df

    def insert_table_in_db_bulk(self, df: pd.DataFrame, mgr, connection=None):
        """Insert a DataFrame in the DB using 'bulk' insert, i.e. with one SQL insert.
        (Instead of row-by-row.)
        Args:
            df (pd.DataFrame)
            mgr (ScenarioDbManager)
            connection: if not None, being run within a transaction
        """
        table_name = self.get_db_table_name()
        columns = self.get_df_column_names()
        try:
            if connection is None:
                df[columns].to_sql(table_name, schema=mgr.schema, con=mgr.engine, if_exists='append', dtype=None,
                                   index=False)
            else:
                df[columns].to_sql(table_name, schema=mgr.schema, con=connection, if_exists='append', dtype=None,
                                   index=False)
        except exc.IntegrityError as e:
            print("++++++++++++Integrity Error+++++++++++++")
            print(f"DataFrame insert/append of table '{table_name}'")
            print(e)

    def _delete_scenario_table_from_db(self, scenario_name: str, connection, scenario_sa_table: Table):
        """Delete all rows associated with the scenario in the DB table.
        Beware: make sure this is done in the right 'inverse cascading' order to avoid FK violations.
        Note that if there happen to be multiple entries in the scenario table with the same name
        (which shouldn't happen), all will be deleted.
        """
        s = scenario_sa_table
        # scenario_seqs = [seq for seq in connection.execute(s.select(s.c.scenario_seq).where(s.c.scenario_name == scenario_name))]
        scenario_seqs = [r.scenario_seq for r in connection.execute(s.select().where(s.c.scenario_name == scenario_name))]

        t = self.get_sa_table()  # A Table()
        if t is not None:
            # Do a join with the scenario table to delete all entries based on the scenario_name
            sql = t.delete().where(t.c.scenario_seq.in_(scenario_seqs))
            connection.execute(sql)

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

    Main difference with the 'regular' ScenarioDbTable definition:
    * At 'create_schema`, the table will NOT be created. Instead,
    * At 'insert_table_in_db_bulk' SQLAlchemy will automatically create a TABLE based on the DataFrame.

    Advantages:
    - No need to define a custom ScenarioDbTable class per table
    - Automatically all columns are inserted
    Disadvantages:
    - No primary and foreign key relations. Thus no checks.
    - Missing relationships means Cognos cannot automatically extract a data model

    TODO: find out what will happen if the DataFrame structure changes and we're doing a new insert
    """
    def __init__(self, db_table_name: str):
        """Need to provide a name for the DB table.
        """
        super().__init__(db_table_name)
        # metadata and engine are set during initialization
        self.metadata = None
        self.engine = None

    def create_table_metadata(self, metadata, engine, schema, multi_scenario: bool = False):
        """Use the engine to reflect the Table metadata.
        Called during initialization."""
        # Store metadata and engine so we can do a dynamic reflect later
        self.metadata = metadata
        self.engine = engine
        self.schema = schema

        # TODO: From the reflected Table, also extract the columns_metadata.
        # We need that for any DB edits

        # print(f"create_table_metadata: ")
        if engine is not None:
            return self._reflect_db_table(metadata, engine, schema)

        return None

    def insert_table_in_db_bulk(self, df, mgr, connection=None):
        """
        Args:
            df (pd.DataFrame)
            mgr (ScenarioDbManager)
            connection: if not None, being run within a transaction
        """
        table_name = self.get_db_table_name()
        if self.dtype is None:
            dtype = ScenarioDbTable.sqlcol(df)
        else:
            dtype = self.dtype
        try:
            # Note that this can use the 'replace', so the table will be dropped automatically and the defintion auto created
            # So no need to drop the table explicitly (?)
            if connection is None:
                df.to_sql(table_name, schema=mgr.schema, con=mgr.engine, if_exists='replace', dtype=dtype, index=False)
            else:
                df.to_sql(table_name, schema=mgr.schema, con=connection, if_exists='replace', dtype=dtype, index=False)
        except exc.IntegrityError as e:
            print("++++++++++++Integrity Error+++++++++++++")
            print(f"DataFrame insert/append of table '{table_name}'")
            print(e)

    def get_sa_table(self) -> Optional[sqlalchemy.Table]:
        """Returns the SQLAlchemy Table. Can be None if table is a AutoScenarioDbTable and not defined in Python code.
        TODO: automatically reflect if None. Is NOT working yet!
        """
        # Get table_metadata from reflection if it doesn't exist
        # Disabled because reflection doesn't find the table
        if self.table_metadata is None:
            self.table_metadata = self._reflect_db_table(self.metadata, self.engine, self.schema)

        return self.table_metadata

    def _reflect_db_table(self, metadata_obj, engine, schema) -> Optional[sqlalchemy.Table]:
        """Get the Table metadata from reflection.
        Does NOT WORK with SQLAlchemy 1.4 and ibm_db_sa 0.3.7
        You do need to specify the schema.
        For reflection, not sure if we should reuse the existing metadata_obj, or create a new one.

        """
        try:
            table = Table(self.db_table_name, metadata_obj, autoload_with=engine)
            # table = Table(self.db_table_name, MetaData(schema=schema), autoload_with=engine)
            print(f"AutoScenarioDbTable._reflect_db_table: Found table '{self.db_table_name}'.")
        except sqlalchemy.exc.NoSuchTableError:
            table = None
            print(f"AutoScenarioDbTable._reflect_db_table: Table '{self.db_table_name}' doesn't exist in DB.")
        return table


class DbCellUpdate(NamedTuple):
    scenario_name: str
    table_name: str
    row_index: List[Dict[str, Any]]  # e.g. [{'column': 'col1', 'value': 1}, {'column': 'col2', 'value': 'pear'}]
    column_name: str
    current_value: Any
    previous_value: Any  # Not used for DB operation
    row_idx: int  # Not used for DB operation


#########################################################################
#  ScenarioDbManager
#########################################################################
class ScenarioDbManager():
    """
    TODO: documentation!
    """

    def __init__(self, input_db_tables: Dict[str, ScenarioDbTable], output_db_tables: Dict[str, ScenarioDbTable],
                 credentials=None, schema: str = None, echo: bool = False, multi_scenario: bool = True,
                 enable_transactions: bool = True, enable_sqlite_fk: bool = True, enable_scenario_seq: bool = False):
        """Create a ScenarioDbManager.

        :param input_db_tables: OrderedDict[str, ScenarioDbTable] of name and sub-class of ScenarioDbTable. Need to be in correct order.
        :param output_db_tables: OrderedDict[str, ScenarioDbTable] of name and sub-class of ScenarioDbTable. Need to be in correct order.
        :param credentials: DB credentials
        :param schema: schema name
        :param echo: if True, SQLAlchemy will produce a lot of debugging output
        :param multi_scenario: If true, adds SCENARIO table and PK
        :param enable_transactions: If true, uses transactions
        :param enable_sqlite_fk: If True, enables FK constraint checks in SQLite
        """
        # WARNING: do NOT use 'OrderedDict[str, ScenarioDbTable]' as type. OrderedDict is not subscriptable. Will cause a syntax error.
        self.schema = self._check_schema_name(schema)
        self.multi_scenario = multi_scenario  # If true, will add a primary key 'scenario_name' to each table
        self.enable_transactions = enable_transactions
        self.enable_sqlite_fk = enable_sqlite_fk
        self.enable_scenario_seq = enable_scenario_seq
        self.echo = echo
        self.input_db_tables = self._add_scenario_db_table(input_db_tables)
        self.output_db_tables = output_db_tables
        self.db_tables = OrderedDict(list(input_db_tables.items()) + list(output_db_tables.items()))  # {**input_db_tables, **output_db_tables}  # For compatibility reasons

        self.engine = self._create_database_engine(credentials, schema, echo)
        self.metadata = sqlalchemy.MetaData(schema=schema)  # VT_20210120: Added schema=schema just for reflection? Not sure what are the implications
        self._initialize_db_tables_metadata()  # Needs to be done after self.metadata, self.multi_scenario has been set
        self.read_scenario_table_from_db_callback = None  # For Flask caching
        self.read_scenarios_table_from_db_callback = None # For Flask caching

    ############################################################################################
    # Initialization. Called from constructor.
    ############################################################################################
    def _check_schema_name(self, schema: Optional[str]):
        """Checks if schema name is not mixed-case, as this is known to cause issues. Upper-case works well.
        This is just a warning. It does not change the schema name."""
        if schema is not None and not schema.islower() and not schema.isupper(): ## I.e. is mixed_case
            print(f"Warning: using mixed case in the schema name {schema} may cause unexpected DB errors. Use upper-case only.")
        return schema

    def _add_scenario_db_table(self, input_db_tables: Dict[str, ScenarioDbTable]) -> Dict[str, ScenarioDbTable]:
        """Adds a Scenario table as the first in the OrderedDict (if it doesn't already exist).
        Called from constructor."""
        # WARNING: do NOT use 'OrderedDict[str, ScenarioDbTable]' as type. OrderedDict is not subscriptable. Will cause a syntax error.
        if self.multi_scenario:
            if 'Scenario' not in input_db_tables.keys():
                input_db_tables.update({'Scenario': ScenarioTable()})
                input_db_tables.move_to_end('Scenario', last=False)
            else:
                if list(input_db_tables.keys()).index('Scenario') > 0:
                    print("Warning: the `Scenario` table should be the first in the input tables")
        return input_db_tables

    def get_scenario_db_table(self) -> ScenarioDbTable:
        """Scenario table must be the first in self.input_db_tables"""
        db_table: ScenarioTable = list(self.input_db_tables.values())[0]
        return db_table

    def get_scenario_sa_table(self) -> sqlalchemy.Table:
        """Returns the SQLAlchemy 'scenario' table. """
        return self.get_scenario_db_table().get_sa_table()

    def _create_database_engine(self, credentials=None, schema: str = None, echo: bool = False):
        """Creates a SQLAlchemy engine at initialization.
        If no credentials, creates an in-memory SQLite DB. Which can be used for schema validation of the data.
        """
        if credentials is not None:
            engine = self._create_db2_engine(credentials, schema, echo)
        else:
            engine = self._create_sqllite_engine(echo)
        return engine

    def _create_sqllite_engine(self, echo: bool):
        if self.enable_sqlite_fk:
            ScenarioDbManager._enable_sqlite_foreign_key_checks()
        return sqlalchemy.create_engine('sqlite:///:memory:', echo=echo)

    @staticmethod
    def _enable_sqlite_foreign_key_checks():
        """Enables the FK constraint validation in SQLite."""
        print("Enable SQLite FK checks")
        from sqlalchemy import event
        from sqlalchemy.engine import Engine
        from sqlite3 import Connection as SQLite3Connection

        @event.listens_for(Engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, connection_record):
            if isinstance(dbapi_connection, SQLite3Connection):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON;")
                cursor.close()

    def _get_db2_connection_string(self, credentials, schema: str):
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
              with paid versions where you can have multiple schemas, i.e. the 'Standard' version.
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

    def _create_db2_engine(self, credentials, schema: str, echo: bool = False):
        """Create a DB2 engine instance.
        Connection string logic in `get_db2_connection_string`
        """
        connection_string = self._get_db2_connection_string(credentials, schema)
        return sqlalchemy.create_engine(connection_string, echo=echo)

    def _initialize_db_tables_metadata(self):
        """To be called from constructor, after engine is 'created'/connected, after self.metadata, self.multi_scenario have been set.
        This will add the `scenario_name` to the db_table configurations.
        This also allows non-bulk inserts into an existing DB (i.e. without running 'create_schema')

        TODO: also reflect the columns_metadata. That is required for any table edits
        """
        for scenario_table_name, db_table in self.db_tables.items():
            db_table.table_metadata = db_table.create_table_metadata(self.metadata,
                                                                     self.engine,
                                                                     self.schema,
                                                                     self.multi_scenario)  # Stores the table schema in the self.metadata

    ############################################################################################
    # Create schema
    ############################################################################################
    def create_schema(self):
        """Drops all tables and re-creates the schema in the DB."""
        if self.enable_transactions:
            print("Create schema within a transaction")
            with self.engine.begin() as connection:
                self._create_schema_transaction(connection=connection)
        else:
            self._create_schema_transaction(self.engine)

    def _create_schema_transaction(self, connection):
        """(Re)creates a schema, optionally using a transaction
        Drops all tables and re-creates the schema in the DB."""
        # if self.schema is None:
        #     self.drop_all_tables_transaction(connection=connection)
        # else:
        #     self.drop_schema_transaction(self.schema)
        # DROP SCHEMA isn't working properly, so back to dropping all tables
        self._drop_all_tables_transaction(connection=connection)
        self.metadata.create_all(connection, checkfirst=True)

    def drop_all_tables(self):
        """Drops all tables in the current schema."""
        if self.enable_transactions:
            with self.engine.begin() as connection:
                self._drop_all_tables_transaction(connection=connection)
        else:
            self._drop_all_tables_transaction(self.engine)

    def _drop_all_tables_transaction(self, connection):
        """Drops all tables as defined in db_tables (if exists)
        TODO: loop over tables as they exist in the DB.
        This will make sure that however the schema definition has changed, all tables will be cleared.
        Problem. The following code will loop over all existing tables:

            inspector = sqlalchemy.inspect(self.engine)
            for db_table_name in inspector.get_table_names(schema=self.schema):

        However, the order is alphabetically, which causes FK constraint violation
        Weirdly, this happens in SQLite, not in DB2! With or without transactions

        TODO:
        1. Use SQLAlchemy to drop table, avoid text SQL
        2. Drop all tables without having to loop and know all tables
        See: https://stackoverflow.com/questions/35918605/how-to-delete-a-table-in-sqlalchemy)
        See https://docs.sqlalchemy.org/en/14/core/metadata.html#sqlalchemy.schema.MetaData.drop_all
        """
        # # Would this work?:
        # self.metadata.reflect(bind=connection)  # To reflect any tables in the DB, but not in the current schema
        # self.metadata.drop_all(bind=connection)

        for scenario_table_name, db_table in reversed(self.db_tables.items()):
            db_table_name = db_table.db_table_name
            sql = f"DROP TABLE IF EXISTS {db_table_name}"
            #         print(f"Dropping table {db_table_name}")
            connection.execute(sql)

    def _drop_schema_transaction(self, schema: str, connection=None):
        """NOT USED. Not working in DB2 Cloud.
        Drops schema, and all the objects defined within that schema.
        See: https://www.ibm.com/docs/en/db2/11.5?topic=procedure-admin-drop-schema-drop-schema
        However, this doesn't work on DB2 cloud.
        TODO: find out if and how we can get this to work.
        See https://docs.sqlalchemy.org/en/14/core/metadata.html#sqlalchemy.schema.MetaData.drop_all
        """
        # sql = f"DROP SCHEMA {schema} CASCADE"  # Not allowed in DB2!
        sql = f"CALL SYSPROC.ADMIN_DROP_SCHEMA('{schema}', NULL, 'ERRORSCHEMA', 'ERRORTABLE')"
        # sql = f"CALL SYSPROC.ADMIN_DROP_SCHEMA('{schema}', NULL, NULL, NULL)"
        if connection is None:
            r = self.engine.execute(sql)
        else:
            r = connection.execute(sql)

    ############################################################################################
    # Insert/replace scenario
    ############################################################################################
    def replace_scenario_in_db(self, scenario_name: str, inputs: Inputs = {}, outputs: Outputs = {}, bulk=True):
        """Insert or replace a scenario. Main API to insert/update a scenario.
        If the scenario exists, will delete rows first.
        Inserts scenario data in all tables.
        Inserts tables in order specified in OrderedDict. Inputs first, outputs second.

        :param scenario_name:
        :param inputs:
        :param outputs:
        :param bulk:
        :return:
        """
        if self.enable_transactions:
            print("Replacing scenario within transaction")
            with self.engine.begin() as connection:
                self._replace_scenario_in_db_transaction(connection, scenario_name=scenario_name, inputs=inputs, outputs=outputs, bulk=bulk)
        else:
            self._replace_scenario_in_db_transaction(self.engine, scenario_name=scenario_name, inputs=inputs, outputs=outputs, bulk=bulk)

    def _replace_scenario_in_db_transaction(self, connection, scenario_name: str, inputs: Inputs = {}, outputs: Outputs = {},
                                            bulk: bool = True):
        """Replace a single full scenario in the DB. If doesn't exist, will insert.
        Only inserts tables with an entry defined in self.db_tables (i.e. no `auto_insert`).
        Will first delete all rows associated with a scenario_name.
        Will set/overwrite the scenario_name in all dfs, so no need to add in advance.
        Assumes schema has been created.
        Note: there is no difference between dfs in inputs or outputs, i.e. they are inserted the same way.
        """
        # Step 1: delete scenario if exists
        self._delete_scenario_from_db(scenario_name, connection=connection)
        # Step 2: insert scenario_name in scenario table and get scenario_seq
        scenario_seq = self._get_or_create_scenario_in_scenario_table(scenario_name, connection)
        # Step 3: add scenario_name to all dfs
        inputs = ScenarioDbManager.add_scenario_seq_to_dfs(scenario_seq, inputs)
        outputs = ScenarioDbManager.add_scenario_seq_to_dfs(scenario_seq, outputs)
        # Step 4: (bulk) insert scenario
        num_caught_exceptions = self._insert_single_scenario_tables_in_db(inputs=inputs, outputs=outputs, bulk=bulk, connection=connection)
        # Throw exception if any exceptions caught in 'non-bulk' mode
        # This will cause a rollback when using a transaction
        if num_caught_exceptions > 0:
            raise RuntimeError(f"Multiple ({num_caught_exceptions}) Integrity and/or Statement errors caught. See log. Raising exception to allow for rollback.")


    def _insert_single_scenario_tables_in_db(self, inputs: Inputs = {}, outputs: Outputs = {},
                                             bulk: bool = True, connection=None) -> int:
        """Specifically for single scenario replace/insert.
        Does NOT insert into the `scenario` table.
        No `auto_insert`, i.e. only df matching db_tables.  TODO: verify if doesn't work with AutoScenarioDbTable
        """
        num_caught_exceptions = 0
        dfs = {**inputs, **outputs}  # Combine all dfs in one dict
        for scenario_table_name, db_table in self.db_tables.items():
            if scenario_table_name != 'Scenario':
                if scenario_table_name in dfs:
                    df = dfs[scenario_table_name]
                    print(f"Inserting {df.shape[0]} rows and {df.shape[1]} columns in {scenario_table_name}")
                    #                 display(df.head(3))
                    if bulk:
                        db_table.insert_table_in_db_bulk(df=df, mgr=self, connection=connection)
                    else:  # Row by row for data checking
                        num_caught_exceptions += self._insert_table_in_db_by_row(db_table, df, connection=connection)
                else:
                    print(f"No table named {scenario_table_name} in inputs or outputs")
        return num_caught_exceptions

    def _insert_table_in_db_by_row(self, db_table: ScenarioDbTable, df: pd.DataFrame, connection=None) -> int:
        """Inserts a table in the DB row-by-row.
        For debugging FK/PK data issues.
        Uses a single SQL insert statement for each row in the DataFrame so that if there is a FK/PK issue,
        the error message will be about only this row. Is a lot easier to debug than using bulk.
        In addition, it catches the exception and keeps on inserting, so that we get to see multiple errors.
        This allows us to debug multiple data issues within one run.
        To avoid too many exceptions, the number of exceptions per table is limited to 10.
        After the limit, the insert will be terminated. And the next table will be inserted.
        Note that as a result of terminating a table insert, it is very likely it will cause FK issues in subsequent tables.
        """
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
                if connection is None:
                    self.engine.execute(stmt)
                else:
                    connection.execute(stmt)
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
        return num_exceptions

    ############################################################################################
    # Read scenario
    ############################################################################################
    def get_scenarios_df(self) -> pd.DataFrame:
        """Return all scenarios in df. Result is indexed by `scenario_name`.
        Main API to get all scenarios.
        The API called by a cached procedure in the dse_do_dashboard.DoDashApp.
        """
        # sql = f"SELECT * FROM SCENARIO"
        # sa_scenario_table = list(self.input_db_tables.values())[0].table_metadata
        sa_scenario_table = self.get_scenario_sa_table()
        sql = sa_scenario_table.select()
        if self.enable_transactions:
            with self.engine.begin() as connection:
                # TODO: Still index by scenario_name, or by scenario_seq? By name keeps it backward compatible.
                #  But there is a theoretical risk of duplicates
                df = pd.read_sql(sql, con=connection).set_index(['scenario_name'])
        else:
            df = pd.read_sql(sql, con=self.engine).set_index(['scenario_name'])
        return df

    def read_scenario_table_from_db(self, scenario_name: str, scenario_table_name: str) -> pd.DataFrame:
        """Read a single table from the DB.
        Main API to read a single table.
        The API called by a cached procedure in the dse_do_dashboard.DoDashApp.

        :param scenario_name: Name of scenario
        :param scenario_table_name: Name of scenario table (not the DB table name)
        :return:
        """
        # print(f"read table {scenario_table_name}")
        if scenario_table_name in self.db_tables:
            db_table = self.db_tables[scenario_table_name]
        else:
            # error!
            raise ValueError(f"Scenario table name '{scenario_table_name}' unknown. Cannot load data from DB.")

        if self.enable_transactions:
            with self.engine.begin() as connection:
                df = self._read_scenario_db_table_from_db(scenario_name, db_table, connection)
        else:
            df = self._read_scenario_db_table_from_db(scenario_name, db_table, self.engine)

        return df

    def read_scenario_from_db(self, scenario_name: str, multi_threaded: bool = False) -> (Inputs, Outputs):
        """Single scenario load.
        Main API to read a complete scenario.
        Reads all tables for a single scenario.
        Returns all tables in one dict

        Note: multi_threaded doesn't seem to lead to performance improvement.
        Fixed: omit reading scenario table as an input.
        """
        # print(f"read_scenario_from_db.multi_threaded = {multi_threaded}")
        if multi_threaded:
            inputs, outputs = self._read_scenario_from_db_multi_threaded(scenario_name)
        else:
            if self.enable_transactions:
                with self.engine.begin() as connection:
                    inputs, outputs = self._read_scenario_from_db(scenario_name, connection)
            else:
                inputs, outputs = self._read_scenario_from_db(scenario_name, self.engine)
        return inputs, outputs

    def _read_scenario_from_db(self, scenario_name: str, connection) -> (Inputs, Outputs):
        """Single scenario load.
        Main API to read a complete scenario.
        Reads all tables for a single scenario.
        Returns all tables in one dict
        """
        inputs = {}
        for scenario_table_name, db_table in self.input_db_tables.items():
            # print(f"scenario_table_name = {scenario_table_name}")
            if scenario_table_name != 'Scenario':  # Skip the Scenario table as an input
                inputs[scenario_table_name] = self._read_scenario_db_table_from_db(scenario_name, db_table, connection=connection)

        outputs = {}
        for scenario_table_name, db_table in self.output_db_tables.items():
            outputs[scenario_table_name] = self._read_scenario_db_table_from_db(scenario_name, db_table, connection=connection)

        return inputs, outputs

    def _read_scenario_from_db_multi_threaded(self, scenario_name) -> (Inputs, Outputs):
        """Reads all tables from a scenario using multi-threading.
        Does NOT seem to result in performance improvement!"""
        class ReadTableFunction(object):
            def __init__(self, dbm):
                self.dbm = dbm
            def __call__(self, scenario_table_name, db_table):
                return self._read_scenario_db_table_from_db_thread(scenario_table_name, db_table)
            def _read_scenario_db_table_from_db_thread(self, scenario_table_name, db_table):
                with self.dbm.engine.begin() as connection:
                    df = self.dbm._read_scenario_db_table_from_db(scenario_name, db_table, connection)
                    dict = {scenario_table_name: df}
                return dict

        thread_number = 8
        pool = ThreadPool(thread_number)
        thread_worker = ReadTableFunction(self)
        # print("ThreadPool created")
        all_tables = [(scenario_table_name, db_table) for scenario_table_name, db_table in self.db_tables.items() if scenario_table_name != 'Scenario']
        # print(all_tables)
        all_results = pool.starmap(thread_worker, all_tables)
        inputs = {k:v for element in all_results for k,v in element.items() if k in self.input_db_tables.keys()}
        outputs = {k:v for element in all_results for k,v in element.items() if k in self.output_db_tables.keys()}
        # print("All tables loaded")

        return inputs, outputs

    def read_scenario_input_tables_from_db(self, scenario_name: str) -> Inputs:
        """Convenience method to load all input tables.
        Typically used at start if optimization model.
        :returns The inputs and outputs. (The outputs are always empty.)
        """
        inputs, outputs = self.read_scenario_tables_from_db(scenario_name, input_table_names=['*'])
        return inputs

    def read_scenario_tables_from_db(self, scenario_name: str,
                                     input_table_names: Optional[List[str]] = None,
                                     output_table_names: Optional[List[str]] = None) -> (Inputs, Outputs):
        """Read selected set input and output tables from scenario.
        If input_table_names/output_table_names contains a '*', then all input/output tables will be read.
        If empty list or None, then no tables will be read.
        """
        if self.enable_transactions:
            with self.engine.begin() as connection:
                inputs, outputs = self._read_scenario_tables_from_db(connection, scenario_name, input_table_names, output_table_names)
        else:
            inputs, outputs = self._read_scenario_tables_from_db(self.engine, scenario_name, input_table_names, output_table_names)
        return inputs, outputs

    def _read_scenario_tables_from_db(self, connection, scenario_name: str,
                                      input_table_names: List[str] = None,
                                      output_table_names: List[str] = None) -> (Inputs, Outputs):
        """Loads data for selected input and output tables.
        If either list is names is ['*'], will load all tables as defined in db_tables configuration.
        """
        if input_table_names is None:  # load no tables by default
            input_table_names = []
        elif '*' in input_table_names:
            input_table_names = list(self.input_db_tables.keys())
            if 'Scenario' in input_table_names: input_table_names.remove('Scenario')  # Remove the scenario table

        if output_table_names is None:  # load no tables by default
            output_table_names = []
        elif '*' in output_table_names:
            output_table_names = self.output_db_tables.keys()

        inputs = {}
        for scenario_table_name, db_table in self.input_db_tables.items():
            if scenario_table_name in input_table_names:
                inputs[scenario_table_name] = self._read_scenario_db_table_from_db(scenario_name, db_table, connection=connection)
        outputs = {}
        for scenario_table_name, db_table in self.output_db_tables.items():
            if scenario_table_name in output_table_names:
                outputs[scenario_table_name] = self._read_scenario_db_table_from_db(scenario_name, db_table, connection=connection)
        return inputs, outputs

    def _read_scenario_db_table_from_db(self, scenario_name: str, db_table: ScenarioDbTable, connection) -> pd.DataFrame:
        """Read one table from the DB.
        Removes the `scenario_seq` column.
        """
        db_table_name = db_table.db_table_name
        # sql = f"SELECT * FROM {db_table_name} WHERE scenario_name = '{scenario_name}'"  # Old
        # db_table.table_metadata is a Table()
        s: sqlalchemy.Table = self.get_scenario_sa_table()
        t: sqlalchemy.Table = db_table.get_sa_table()
        sql = t.select().where(t.c.scenario_seq == s.c.scenario_seq).where(s.c.scenario_name == scenario_name)
        df = pd.read_sql(sql, con=connection)
        if db_table_name != 'scenario':
            df = df.drop(columns=['scenario_seq'])

        return df

    ############################################################################################
    # Read multi scenario
    ############################################################################################
    def read_multi_scenario_tables_from_db(self, scenario_names: List[str],
                                           input_table_names: Optional[List[str]] = None,
                                           output_table_names: Optional[List[str]] = None) -> (Inputs, Outputs):
        """Read selected set input and output tables from multiple scenarios.
        If input_table_names/output_table_names contains a '*', then all input/output tables will be read.
        If empty list or None, then no tables will be read.
        """
        if self.enable_transactions:
            with self.engine.begin() as connection:
                inputs, outputs = self._read_multi_scenario_tables_from_db(connection, scenario_names, input_table_names, output_table_names)
        else:
            inputs, outputs = self._read_multi_scenario_tables_from_db(self.engine, scenario_names, input_table_names, output_table_names)
        return inputs, outputs

    def _read_multi_scenario_tables_from_db(self, connection, scenario_names: List[str],
                                            input_table_names: List[str] = None,
                                            output_table_names: List[str] = None) -> (Inputs, Outputs):
        """Loads data for selected input and output tables from multiple scenarios.
        If either list is names is ['*'], will load all tables as defined in db_tables configuration.
        """
        if input_table_names is None:  # load no tables by default
            input_table_names = []
        elif '*' in input_table_names:
            input_table_names = list(self.input_db_tables.keys())

        # Add the scenario table
        if 'Scenario' not in input_table_names:
            input_table_names.append('Scenario')

        if output_table_names is None:  # load no tables by default
            output_table_names = []
        elif '*' in output_table_names:
            output_table_names = self.output_db_tables.keys()

        inputs = {}
        for scenario_table_name, db_table in self.input_db_tables.items():
            if scenario_table_name in input_table_names:
                inputs[scenario_table_name] = self._read_multi_scenario_db_table_from_db(scenario_names, db_table, connection=connection)
        outputs = {}
        for scenario_table_name, db_table in self.output_db_tables.items():
            if scenario_table_name in output_table_names:
                outputs[scenario_table_name] = self._read_multi_scenario_db_table_from_db(scenario_names, db_table, connection=connection)
        return inputs, outputs

    def _read_multi_scenario_db_table_from_db(self, scenario_names: List[str], db_table: ScenarioDbTable, connection) -> pd.DataFrame:
        """Read one table from the DB for multiple scenarios.
        Does NOT remove the `scenario_name` column.
        """
        t: sqlalchemy.Table = db_table.get_sa_table()  #table_metadata
        # sql = t.select().where(t.c.scenario_name.in_(scenario_names))  # This is NOT a simple string!

        s = self.get_scenario_sa_table()
        # TODO: Test of we can do below query in one select (option 1), joining the scenario table, instead of separate selects (option 2)
        # Option 1: do in one query:
        sql = t.select().where(t.c.scenario_seq == s.c.scenario_seq).where(s.c.scenario_name.in_(scenario_names))

        # Option2: If not, we can do in 2 selects
        # scenario_seqs = [r.scenario_seq for r in connection.execute(s.select().where(s.c.scenario_name.in_(scenario_names)))]
        # sql = t.select().where(t.c.scenario_seq.in_(scenario_seqs))

        df = pd.read_sql(sql, con=connection)

        return df

    ############################################################################################
    # Update scenario
    ############################################################################################
    def update_cell_changes_in_db(self, db_cell_updates: List[DbCellUpdate]):
        """Update a set of cellz in the DB.

        :param db_cell_updates:
        :return:
        """
        if self.enable_transactions:
            print("Update cellz with transaction")
            with self.engine.begin() as connection:
                self._update_cell_changes_in_db(db_cell_updates, connection=connection)
        else:
            self._update_cell_changes_in_db(db_cell_updates)

    def _update_cell_changes_in_db(self, db_cell_updates: List[DbCellUpdate], connection=None):
        """Update an ordered list of single value changes (cell) in the DB."""
        for db_cell_change in db_cell_updates:
            self._update_cell_change_in_db(db_cell_change, connection)

    def _update_cell_change_in_db(self, db_cell_update: DbCellUpdate, connection):
        """Update a single value (cell) change in the DB."""
        db_table: ScenarioDbTable = self.db_tables[db_cell_update.table_name]
        s = self.get_scenario_sa_table()
        t: sqlalchemy.Table = db_table.get_sa_table()
        pk_conditions = [(db_table.get_sa_column(pk['column']) == pk['value']) for pk in db_cell_update.row_index]
        target_col: sqlalchemy.Column = db_table.get_sa_column(db_cell_update.column_name)
        print(f"_update_cell_change_in_db - target_col = {target_col} for db_cell_update.column_name={db_cell_update.column_name}, pk_conditions={pk_conditions}")

        if scenario_seq := self._get_scenario_seq(db_cell_update.scenario_name, connection) is not None:
            sql = t.update().where(sqlalchemy.and_((t.c.scenario_seq == scenario_seq), *pk_conditions)).values({target_col:db_cell_update.current_value})
            connection.execute(sql)
        else:
            # Error?
            pass
        # print(f"_update_cell_change_in_db = {sql}")



    ############################################################################################
    # Update/Replace tables in scenario
    ############################################################################################
    def update_scenario_output_tables_in_db(self, scenario_name, outputs: Outputs):
        """Main API to update output from a DO solve in the scenario.
        Deletes ALL output tables. Then inserts the given set of tables.
        Since this only touches the output tables, more efficient than replacing the whole scenario."""
        if self.enable_transactions:
            with self.engine.begin() as connection:
                self._update_scenario_output_tables_in_db(scenario_name, outputs, connection)
        else:
            self._update_scenario_output_tables_in_db(scenario_name, outputs, self.engine)

    def _update_scenario_output_tables_in_db(self, scenario_name, outputs: Outputs, connection):
        """Deletes ALL output tables. Then inserts the given set of tables.
        Note that if a defined output table is not included in the outputs, it will still be deleted from the scenario data."""
        # 1. Add scenario name to dfs:
        outputs = ScenarioDbManager.add_scenario_name_to_dfs(scenario_name, outputs)
        # 2. Delete all output tables
        scenario_sa_table = self.get_scenario_sa_table()
        for scenario_table_name, db_table in reversed(self.output_db_tables.items()):  # Note this INCLUDES the SCENARIO table!
            if (scenario_table_name != 'Scenario'):
                db_table._delete_scenario_table_from_db(scenario_name, connection, scenario_sa_table)
        # 3. Insert new data
        for scenario_table_name, db_table in self.output_db_tables.items():  # Note this INCLUDES the SCENARIO table!
            if (scenario_table_name != 'Scenario') and scenario_table_name in outputs.keys():  # If in given set of tables to replace
                df = outputs[scenario_table_name]
                print(f"Inserting {df.shape[0]} rows and {df.shape[1]} columns in {scenario_table_name}")
                db_table.insert_table_in_db_bulk(df=df, mgr=self, connection=connection)  # The scenario_name is a column in the df

    def replace_scenario_tables_in_db(self, scenario_name, inputs={}, outputs={}):
        """Untested"""
        if self.enable_transactions:
            with self.engine.begin() as connection:
                self._replace_scenario_tables_in_db(connection, scenario_name, inputs, outputs)
        else:
            self._replace_scenario_tables_in_db(self.engine, scenario_name, inputs, outputs)

    def _replace_scenario_tables_in_db(self, connection, scenario_name, inputs={}, outputs={}):
        """Untested
        Replace only the tables listed in the inputs and outputs. But leave all other tables untouched.
        Will first delete all given tables (in reverse cascading order), then insert the new ones (in cascading order)"""

        # Add scenario name to dfs:
        inputs = ScenarioDbManager.add_scenario_name_to_dfs(scenario_name, inputs)
        outputs = ScenarioDbManager.add_scenario_name_to_dfs(scenario_name, outputs)
        dfs = {**inputs, **outputs}
        # 1. Delete tables
        scenario_sa_table = self.get_scenario_sa_table()
        for scenario_table_name, db_table in reversed(self.db_tables.items()):  # Note this INCLUDES the SCENARIO table!
            if (scenario_table_name != 'Scenario') and db_table.db_table_name in dfs.keys():  # If in given set of tables to replace
                db_table._delete_scenario_table_from_db()  #VT 2022-03-05: this cannot work. Incomplete arguments!
        # 2. Insert new data
        for scenario_table_name, db_table in self.db_tables.items():  # Note this INCLUDES the SCENARIO table!
            if (scenario_table_name != 'Scenario') and db_table.db_table_name in dfs.keys():  # If in given set of tables to replace
                df = dfs[scenario_table_name]
                db_table.insert_table_in_db_bulk(df=df, mgr=self, connection=connection)  # The scenario_name is a column in the df

    ############################################################################################
    # CRUD operations on scenarios in DB:
    # - Delete scenario
    # - Duplicate scenario
    # - Rename scenario
    ############################################################################################
    def delete_scenario_from_db(self, scenario_name: str):
        """Delete a scenario. Uses a transaction (when enabled)."""
        if self.enable_transactions:
            print("Delete scenario within a transaction")
            with self.engine.begin() as connection:
                self._delete_scenario_from_db(scenario_name=scenario_name, connection=connection)
        else:
            self._delete_scenario_from_db(scenario_name=scenario_name, connection=self.engine)

    ##########################################################
    def duplicate_scenario_in_db(self, source_scenario_name: str, target_scenario_name: str):
        """Duplicate a scenario. Uses a transaction (when enabled)."""
        if self.enable_transactions:
            print("Duplicate scenario within a transaction")
            with self.engine.begin() as connection:
                self._duplicate_scenario_in_db(connection, source_scenario_name, target_scenario_name)
        else:
            self._duplicate_scenario_in_db(self.engine, source_scenario_name, target_scenario_name)

    def _duplicate_scenario_in_db(self, connection, source_scenario_name: str, target_scenario_name: str = None):
        """Is fully done in DB using SQL in one SQL execute statement
        :param source_scenario_name:
        :param target_scenario_name:
        :param connection:
        :return:
        """
        if target_scenario_name is None:
            new_scenario_name = self._find_free_duplicate_scenario_name(source_scenario_name)
        elif self._check_free_scenario_name(target_scenario_name):
            new_scenario_name = target_scenario_name
        else:
            raise ValueError(f"Target name for duplicate scenario '{target_scenario_name}' already exists.")

        self._duplicate_scenario_in_db_sql(connection, source_scenario_name, new_scenario_name)

    def _duplicate_scenario_in_db_sql(self, connection, source_scenario_name: str, target_scenario_name: str = None):
        """
        :param source_scenario_name:
        :param target_scenario_name:
        :param connection:
        :return:

        See https://stackoverflow.com/questions/9879830/select-modify-and-insert-into-the-same-table

        Problem: the table Parameter/parameters has a column 'value' (lower-case).
        Almost all of the column names in the DFs are lower-case, as are the column names in the ScenarioDbTable.
        Typically, the DB schema converts that the upper-case column names in the DB.
        But probably because 'VALUE' is a reserved word, it does NOT do this for 'value'. But that means in order to refer to this column in SQL,
        one needs to put "value" between double quotes.
        Problem is that you CANNOT do that for other columns, since these are in upper-case in the DB.
        Note that the kpis table uses upper case 'VALUE' and that seems to work fine

        Resolution: use SQLAlchemy to construct the SQL. Do NOT create SQL expressions by text manipulation.
        SQLAlchemy has the smarts to properly deal with these complex names.
        """
        if target_scenario_name is None:
            new_scenario_name = self._find_free_duplicate_scenario_name(source_scenario_name)
        elif self._check_free_scenario_name(target_scenario_name):
            new_scenario_name = target_scenario_name
        else:
            raise ValueError(f"Target name for duplicate scenario '{target_scenario_name}' already exists.")

        # TODO: TEST

        # 1. Insert scenario in scenario table
        source_scenario_seq = self._get_or_create_scenario_in_scenario_table(source_scenario_name, connection)
        new_scenario_seq = self._get_or_create_scenario_in_scenario_table(new_scenario_name, connection)

        # 2. Do 'insert into select' to duplicate rows in each table
        s: sqlalchemy.table = self.get_scenario_sa_table()
        for scenario_table_name, db_table in self.db_tables.items():
            if scenario_table_name == 'Scenario':
                continue

            t: sqlalchemy.table = db_table.table_metadata  # The table at hand
            # print("+++++++++++SQLAlchemy insert-select")
            select_columns = [s.c.scenario_seq if c.name == 'scenario_seq' else c for c in t.columns]  # Replace the t.c.scenario_name with s.c.scenario_name, so we get the new value
            # print(f"select columns = {select_columns}")
            select_sql = (sqlalchemy.select(select_columns)
                          .where(sqlalchemy.and_(t.c.scenario_seq == source_scenario_seq, s.c.scenario_seq == new_scenario_seq)))
            target_columns = [c for c in t.columns]
            sql_insert = t.insert().from_select(target_columns, select_sql)
            # print(f"sql_insert = {sql_insert}")

            # sql_insert = f"INSERT INTO {db_table.db_table_name} ({target_columns_txt}) SELECT '{target_scenario_name}',{other_source_columns_txt} FROM {db_table.db_table_name} WHERE scenario_name = '{source_scenario_name}'"
            connection.execute(sql_insert)

    def _find_free_duplicate_scenario_name(self, scenario_name: str, scenarios_df=None) -> Optional[str]:
        """Finds next free scenario name based on pattern '{scenario_name}_copy_n'.
        Will try at maximum 20 attempts.
        """
        max_num_attempts = 20
        for i in range(1, max_num_attempts + 1):
            new_name = f"{scenario_name}({i})"
            free = self._check_free_scenario_name(new_name, scenarios_df)
            if free:
                return new_name
        raise ValueError(f"Cannot find free name for duplicate scenario. Tried {max_num_attempts}. Last attempt = {new_name}. Rename scenarios.")
        return None

    def _check_free_scenario_name(self, scenario_name, scenarios_df=None) -> bool:
        if scenarios_df is None:
            scenarios_df = self.get_scenarios_df()
        free = (False if scenario_name in scenarios_df.index else True)
        return free

    ##############################################
    def rename_scenario_in_db(self, source_scenario_name: str, target_scenario_name: str):
        """Rename a scenario. Uses a transaction (when enabled)."""
        if self.enable_transactions:
            print("Rename scenario within a transaction")
            with self.engine.begin() as connection:
                # self._rename_scenario_in_db(source_scenario_name, target_scenario_name, connection=connection)
                self._rename_scenario_in_db_sql(connection, source_scenario_name, target_scenario_name)
        else:
            # self._rename_scenario_in_db(source_scenario_name, target_scenario_name)
            self._rename_scenario_in_db_sql(self.engine, source_scenario_name, target_scenario_name)

    def _rename_scenario_in_db_sql(self, connection, source_scenario_name: str, target_scenario_name: str = None):
        """Rename scenario.
        Uses 2 steps:
        1. Duplicate scenario
        2. Delete source scenario.

        Problem is that we use scenario_name as a primary key. You should not change the value of primary keys in a DB.
        Instead, first copy the data using a new scenario_name, i.e. duplicate a scenario. Next, delete the original scenario.

        Long-term solution: use a scenario_seq sequence key as the PK. With scenario_name as a ordinary column in the scenario table.

        Use of 'insert into select': https://stackoverflow.com/questions/9879830/select-modify-and-insert-into-the-same-table
        """
        # Just update the scenario_name:
        # 1. Get the scenario_seq
        # 2. Update the name
        s = self.get_scenario_sa_table()
        scenario_seq = self._get_scenario_seq(source_scenario_name, connection)
        if scenario_seq is not None:
            print(f"Rename scenario name = {source_scenario_name}, seq = {scenario_seq}")
            sql = s.update().where(s.c.scenario_seq == scenario_seq).values({s.c.scenario_name: target_scenario_name})
            connection.execute(sql)

        # # 1. Duplicate scenario
        # self._duplicate_scenario_in_db_sql(connection, source_scenario_name, target_scenario_name)
        # # 2. Delete scenario
        # self._delete_scenario_from_db(source_scenario_name, connection=connection)

    def _delete_scenario_from_db(self, scenario_name: str, connection):
        """Deletes all rows associated with a given scenario.
        Note that it only deletes rows from tables defined in the self.db_tables, i.e. will NOT delete rows in 'auto-inserted' tables!
        Must do a 'cascading' delete to ensure not violating FK constraints. In reverse order of how they are inserted.
        Also deletes entry in scenario table
        Uses SQLAlchemy syntax to generate SQL
        TODO: check with 'auto-inserted' tables
        TODO: batch all sql statements in single execute. Faster? And will that do the defer integrity checks?
        """
        insp = sqlalchemy.inspect(connection)
        tables_in_db = insp.get_table_names(schema=self.schema)
        scenario_sa_table = self.get_scenario_sa_table()
        for scenario_table_name, db_table in reversed(self.db_tables.items()):  # Note this INCLUDES the SCENARIO table!
            if db_table.db_table_name in tables_in_db:
                db_table._delete_scenario_table_from_db(scenario_name, connection, scenario_sa_table)

    def _get_or_create_scenario_in_scenario_table(self, scenario_name: str, connection) -> int:
        """Returns the scenario_seq of (the first) entry matching the scenario_name.
        If it doesn't exist, will insert a new entry.
        """
        # s = self.get_scenario_sa_table()
        # r = connection.execute(s.select(s.c.scenario_seq).where(s.c.scenario_name == scenario_name))
        # if (r is not None) and ((first := r.first()) is not None):  # Walrus operator!
        #     seq = first[0]
        # else:

        seq = self._get_scenario_seq(scenario_name, connection)
        if seq is None:
            s = self.get_scenario_sa_table()
            connection.execute(s.insert().values(scenario_name=scenario_name))
            r = connection.execute(s.select(s.c.scenario_seq).where(s.c.scenario_name==scenario_name))
            seq = r.first()[0]
        return seq

    def _get_scenario_seq(self, scenario_name: str, connection) -> Optional[int]:
        """Returns the scenario_seq of (the first) entry matching the scenario_name.
        """
        s = self.get_scenario_sa_table()
        # r = connection.execute(s.select(s.c.scenario_seq).where(s.c.scenario_name == scenario_name))
        r = connection.execute(s.select().where(s.c.scenario_name == scenario_name))
        if (r is not None) and ((first := r.first()) is not None):  # Walrus operator!
            # print(f"_get_scenario_seq: r={first}")
            seq = first[0]  # Tuple with values. First (0) is the scenario_seq. TODO: do more structured so we can be sure it is the scenario_seq!
        else:
            seq = None
        return seq


    ############################################################################################
    # Import from zip
    ############################################################################################
    def insert_scenarios_from_zip(self, filepath: str):
        """Insert (or replace) a set of scenarios from a .zip file into the DB.
        Zip is assumed to contain one or more .xlsx files. Others will be skipped.
        Name of .xlsx file will be used as the scenario name.

        :param filepath: filepath of a zip file
        :return:
        """
        with zipfile.ZipFile(filepath, 'r') as zip_file:
            for info in zip_file.infolist():
                scenario_name = pathlib.Path(info.filename).stem
                file_extension = pathlib.Path(info.filename).suffix
                if file_extension == '.xlsx':
                    # print(f"file in zip : {info.filename}")
                    xl = pd.ExcelFile(zip_file.read(info))
                    inputs, outputs = ScenarioManager.load_data_from_excel_s(xl)
                    print("Input tables: {}".format(", ".join(inputs.keys())))
                    print("Output tables: {}".format(", ".join(outputs.keys())))
                    self.replace_scenario_in_db(scenario_name=scenario_name, inputs=inputs, outputs=outputs)  #
                    print(f"Uploaded scenario: '{scenario_name}' from '{info.filename}'")
                else:
                    print(f"File '{info.filename}' in zip is not a .xlsx. Skipped.")

    #######################################################################################################
    # Utils
    #######################################################################################################
    @staticmethod
    def add_scenario_seq_to_dfs(scenario_seq: int, inputs: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        """Adds a `scenario_seq` column to each df.
        Or overwrites all values of that column already exists.
        This avoids to need for the MultiScenarioManager when loading and storing single scenarios."""
        outputs = {}
        for scenario_table_name, df in inputs.items():
            df['scenario_seq'] = scenario_seq
            outputs[scenario_table_name] = df
        return outputs

    @staticmethod
    def delete_scenario_seq_column(inputs: Inputs, outputs: Outputs) -> (Inputs, Outputs):
        """Drops the column `scenario_seq` from any df in either inputs or outputs.
        This is used to create a inputs/outputs combination similar to loading a single scenario from the DO Experiment.
        """
        new_inputs = {}
        new_outputs = {}
        for scenario_table_name, df in inputs.items():
            if 'scenario_seq' in df.columns:
                df = df.drop(columns=['scenario_seq'])
                new_inputs[scenario_table_name] = df
        for scenario_table_name, df in outputs.items():
            if 'scenario_seq' in df.columns:
                df = df.drop(columns=['scenario_seq'])
                new_outputs[scenario_table_name] = df
        return new_inputs, new_outputs


#######################################################################################################
# Input Tables
#######################################################################################################
class ScenarioTable(ScenarioDbTable):
    def __init__(self, db_table_name: str = 'scenario'):
        columns_metadata = [
            Column('scenario_seq', Integer(), autoincrement=True, primary_key=True),
            Column('scenario_name', String(256), primary_key=False, nullable=False),  # TODO: should we add a 'unique' constraint on the name?
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


#######################################################################################################
# Output Tables
#######################################################################################################
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