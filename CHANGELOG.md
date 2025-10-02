# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

[Unreleased]## [0.5.7.2b2]
### Fixed
- DeployedDOModel - avoid warning in Python 3.12 'SyntaxWarning'

## [0.5.7.2b1] - 2025-07-03
### Added
- DOModelDeployer: option to deploy from a local do_main_model.py (instead of extracting the model from a DO Experiment)
- DOModelDeployer added `model_meta_props_type` and `base_sw_name` constructor arguments to handle different cplex releases.
- ScenarioManager: remove timezone from datetime values in DataFrame. This avoids issues with exporting using the ExcelWriter, which does not support datetime with timezone.
### Fixed
- ScenarioDbManager.replace_scenario_in_db: fixed mutable default arguments
- ScenarioDbManager._replace_scenario_in_db_transaction: fixed mutable default arguments
- DOModelDeployer fixed mutable default arguments
- DOModelDeployer and DeployedDOModel switching from ibm_watson_machine_learning to ibm_watsonx_ai
- DOModelDeployer and DeployedDOModel switching from `get_uid()` to `get_id()` at various places using the `APIClient`


## [0.5.7.2b0] - 2025-05-08
### Added
- Optimization Progress Tracking in CPO. CPO callback to record progress of search. Supports reporting and visualization.
- core01_cpo_optimization_engine.CpoProgressTrackerCallback
- Core01CpoOptimizationEngine.record_optimization_progress()
- Core01OptimizationEngine optimization progress tracking, using same format as CPO.
- Core01DataManager APIs clear_optimization_progress/add_optimization_progress/get_optimization_progress_as_wide_df
- core01_db_manager.Core01OptimizationProgressTable
- Core01CpoOptimizationEngine.set_cpo_parameters now supports CPO `Workers` parameter based on `threads` parameter
- Core01DataManager.get_kpi_value and .get_business_kpi_value for use in dashboard
- Core01DataManager.business_kpis output dataframe added (similar to .kpis)
### Fixed
- Tested with Python 3.11 and CPLEX 22.1.2
- ScenarioDbManager.insert_scenarios_from_zip fixed FutureWarning reading zipped Excel file.
- ScenarioGenerator.get_parameters: FutureWarning fix allowing mixed dypes
- ScenarioDbManager._duplicate_scenario_in_db_sql: fixed error unpacking column list

## [0.5.7.1]- 2025-03-17
### Changed
- Core01OptimizationEngine.post_processing(). Removed `@abstractmethod`.
- ScenarioDbManager.insert_scenarios_from_zip, added `pathlib.Path` as input type
### Fixed
- Core01DataManager.__init__(): setting logger.log_level
- ScenarioRunner._run_once(): setting logger.log_level
- Core01CpoOptimizationEngine.get_kpi_output_table extraction of kpis in DataFrame
- BACKWARD INCOMPATIBILITY - ScenarioDbManager.fixNanNoneNull now includes the string `None`. This resolves issues with SqLite returning NULL as the string 'None'.
- Core01CpoOptimizationEngine.run(): fixed check for feasible solution
### Tests
- Tested with SQLAlchemy 2.0

## [0.5.7.0]- 2024-11-26
### Changed
- BACKWARD INCOMPATIBILITY - ScenarioDbManager.__init__: changed default values for db_type=DatabaseType.SQLite. For other uses (DB2 or PostgreSQL, always specify the db_type.
- BACKWARD INCOMPATIBILITY - ScenarioDbManager.__init__: changed default values for enable_scenario_seq=True, future=True. This reflects the current best practices.
- BACKWARD INCOMPATIBILITY - Removed ScenarioDbManager from `dse_do_utils.__init__.py`. This avoids the dependency on sqlalchemy with use of dse_do_utils where the ScenarioDbManager is not used. 
Introduces a slight backward incompatibility. Need to import as: `from dse_do_utils.scenariodbmanager import ScenarioDbManager` 
- Removed (deprecated) `module_reload()` from `dse_do_utils.__init__.py`. In notebooks `autoreload` works well, 
- Generics in ScenarioRunner
- Removed deprecated optional argument `dtypes` from `Core01DataManager.prepare_output_data_frames()`
- Fixed mutable default arguments in scenariodbmanager module
### Added
- CplexDot in core01_optimization_engine: generic function class to use groupby aggregation and the mdl.dot() function.
- PlotlyManager - self.ref_dm, self.ms_inputs, self.ms_outputs property declarations and documentation
- PlotlyManager.plotly_kpi_compare_bar_charts and .get_multi_scenario_table for scenario compare
- Core01DataManager and Core01OptimizationEngine: added support for parameter `mipGap`. Sets the `mdl.parameters.mip.tolerances.mipgap` if value > 0
- DataManager.extract_solution adds option `allow_mixed_type_columns`. If True allows dvar/expr in column to be a regular Python value and not have the `solution_value` attribute

## [0.5.6.0]- 2023-05-13
### Changed
- Bumping version to 0.5.6.0 given the amount of changes and additions

## [0.5.5.2b6] - 2024-05-12
### Added
- DeployedDOModel.monitor_execution_v1 efficiency improvement: only polls for the 'status'
- DeployedDOModel.solve refactoring
- DeployedDOModel retrieves the full log file
- DeployedDOModel increased default hardware spec nodes
- DOModelDeployerLocal to deploy DO model in WML from a local (non-CP4D/wx.ai) machine

## [0.5.5.2b5] - 2024-05-07
### Added
- ScenarioDbManager.duplicate_scenario_in_db returns scenario_name
### Fixed
- ScenarioRunner.get_parameters can handle case where inputs do not (yet) have a 'Parameter' or 'Parameters' tab
- DataManager.extract_solution_v1 if argument `round_decimals` = 0 then convert column type to int 

## [0.5.5.2b4] - 2024-04-10
### Added
- DataManager.extract_solution_v1 argument `round_decimals` to allow rounding of solution value
- DataManager.extract_solution_v1 argument `extract_dvar_names` can also be a `Dict[str, str]` where the value if the solumn column name. 
- DataManager.extract_solution_v1 argument `solution_column_name_post_fix` to allow custom post fix (instead of hard-coded 'Sol')
- ScenarioRunner logs Excel input file name
- utils.df_itertuples_with_index_names()
- Core02ScenarioGenerator and Core02ScenarioConfig: configure LexOptiLevels and LexOptiGoals
- Core01DataManager.remove_zero_quantity_output to filter rows from a df where a solution column is less than the threshold
- DataManager.get_parameter_value improved handling of datetime when reading directly from Excel
### Fixed
- Small error in ScenarioRunner.insert_outputs_in_db

## [0.5.5.2b3]- 2023-07-05
### Added
- Core01EnvironmentManager.find_project_root_directory
- MapManager.add_bar_chart_in_map
- DataManager.extract_solution_v1 adds option to drop small values to zero
### Changed
- Core01DataManager.prepare_df now merges local dtypes with self.dtypes, where overlapping local dtypes take priority

## [0.5.5.2b2]- 2023-06-08
### Added
- Core01OptimizationEngine, Core02OptimizationEngine, PlotlyManager - added support for DataManager generics
- Core01EnvironmentManager can define logging scope
### Changed
- Core01DataManager logger now uses `__name__`
- Core01DataManager - removed deprecated logger methods

## [0.5.5.2b1]- 2023-05-23
### Changed
- Support enable_refine_conflict in Core02OptimizationEngine and ScenarioRunner
- Requires Pandas 2.0 which fixes an issue with SQLAlchemy 2.0 Future

## [0.5.5.2b0]- 2023-05-02
### Added
- DataManager class generics to OptimizationEngine, Core01OptimizationEngine
### Changed
- core01_environment_manager.HostEnvironment is now an enum.IntEnum to allow comparing integer values
- OptimizationEngine.integer_var_series_s etc. define the dtype='object' to avoid FutureWarning
- ScenarioManager.write_data_to_excel switch from pd.ExcelWriter.save() to .close() to avoid FutureWarning

## [0.5.5.1]- 2023-03-06
### Changed
- README documentation updates.
- Removing deprecated modules `deployeddmmodelcpd21.py`, `scenariodbmanager2.py`
### Fixed
- setup.py to include the dse_do_utils.core subpackage

## [0.5.5.0]- 2023-03-04
### Changed
- Bumping version to 0.5.5.0 given the amount of changes and additions

## [0.5.4.6b4]- 2023-03-03
### Fixed
- ScenarioDbManager.insert_table_in_db_bulk only fix NaNs for known columns.

## [0.5.4.6b3]- 2023-02-26
## Added
- dse_do_utils.core Core01ScenarioDbManager, Core02DataManager, Core02OptimizationEngine, Core02ScenarioDbManager
- ScenarioDbManager.extend_columns_constraints utility method to help avoid mutable default arguments
- ScenarioManager.write_data_to_excel parameter `unique_file_name: bool = True` writes file with unique name 
if it is open in Excel and would have caused a PermissionError.
### Changed
- dse_do_utils.core with Core01DataManager, Core01OptimizationEngine, Core01EnvironmentManager updates
### Fixed
- ScenarioDbManager._set_df_column_types handles DateTime column type

## [0.5.4.6b2]- 2023-02-13
## Added
- dse_do_utils.core with Core01DataManager, Core01OptimizationEngine, Core01EnvironmentManager
### Fixed
- Fix ScenarioDbManager.duplicate_scenario_in_db future warning
- Fix ScenarioDbManager.get_data_directory using Platform.Local
- Fix ScenarioDbManager.get_root_directory partially (CPD40 and Local)

## [0.5.4.6b1]- 2023-02-06
## Added
- ScenarioDbManager support for custom_naming_convention of FK (and other) constraints
### Changed
- ScenarioDbManager._drop_all_tables_transaction tries 3 methods (in order) to drop all tables using: 1. Reflect, 2. Inspect, 3. self.metadata
- ScenarioDbManager supports SQLAlchemy 1.4 with future=True (to prepare for SQLAlchemy 2.0)
### Fixed
- Fix insert new scenario with scenarioSeq=True (ScenarioDbManager._get_or_create_scenario_in_scenario_table)
- Fix ScenarioDbManager.duplicate_scenario_in_db when future=True warning about cartesian product.

## [0.5.4.6b0]- 2023-01-10
## Added
- ScenarioDbTable.fixNanNoneNull: convert more 'nan' values to None and thus to a correct NULL in DB
- ScenarioDbManager supports PostgreSQL

## [0.5.4.5] - 2022-12-08
### Changed
- DeployedDOModel.get_solve_details_objective uses PROGRESS_CURRENT_OBJECTIVE instead of PROGRESS_BEST_OBJECTIVE and adds exception handling
- setup.py avoids import of dse_do_utils to get __version__
## Added
- RunConfig.export_sav option

## [0.5.4.5b4] - 2022-11-15
### Added
- OptimizationEngine.create_do_model() to instantiate as CPOptimizer model
- OptimizationEngine CPOptimizer methods to create dvar as DataFrame columns
- OptimizationEngine.semicontinuous_var_series
- OptimizationEngine.semiinteger_var_series 
### Changed
- ScenarioDbManager: before any DB insert (bulk and row-by-row), replace NaN with None to avoid FK problems in DB2

## [0.5.4.5b3] - 2022-10-17
### Added
- Support for scenarioSeq in ScenarioDbManager

## [0.5.4.5b2] - 2022-10-02
### Changed
- ScenarioRunner and ScenarioGenerator refactoring

## [0.5.4.5b1] - 2022-09-22
### Added
- ScenarioRunner and ScenarioGenerator

## [0.5.4.5b0] - 2022-09-06
### Changed
- ScenarioDbManager.resolve_metadata_column_conflicts: resolve conflicts where a ScenarioDbTable subclass redefines a column.
- ScenarioDbManager._insert_table_in_db_by_row automatically inserts None for columns in defined schema, but missing in DataFrame.

## [0.5.4.4] - 2022-04-28
### Added
- ScenarioManager.load_data_from_zip_csv_s: loading input data from a zipped archive of csv files
- ScenarioManager.write_data_to_zip_csv_s: writing input/output data as a zipped archive of csv files
### Removed
- ScenarioManager.write_data_to_csv_s no longer adds files as data assets

## [0.5.4.3] - 2022-04-21
### Changed
- Fixed indentation bug in domodeldeployer
- Update of CONTRIBUTING.md
- Format thousands for num rows in db-insert progress print message
### Added
- DOModelDeployer support for gz/zip package files
- ScenarioManager.load_data_from_parquet and .write_data_to_parquet
- ScenarioDbManager.__init__ added parameter `enable_debug_print` to print connection string

## [Unreleased]## [0.5.4.3b0]
### Changed
- Fixed bug in ScenarioDbManager._check_schema_name if schema is None (e.g. when using SQLite)
- ScenarioDbTable.insert_table_in_db_bulk selects columns present in both the df and the schema. Avoids error when column is defined in DB but not in df.
### Added
- Added 'group' as reserved table name
- Added `local_relative_data_path` in ScenarioManager.__init__() to allow more flexibility in defining local paths
- ScenarioDbManager.__init__ added parameter `enable_astype: bool = True`: If True, force data-type of DataFrame to match schema before (bulk) insert.

## [0.5.4.2] - 2022-02-24
### Changed
- ScenarioDManager.read_scenario_input_tables_from_db now only returns Inputs (vs the tuple (Inputs,Outputs)). This could cause some backward incompatibility.
- OptimizationEngine.get_kpi_output_table now returns Dataframe with capitalized column names: 'NAME' and 'VALUE' to make consistent with DO Experiment kpis.
### Added
- MapManager.get_tooltip_table to get a tooltip formatted as table
- ScenarioDbManager.read_multi_scenario_tables_from_db reads multiple scenarios in same DataFrames (for scenario compare feature)
- ScenarioDbTable.get_sa_column works also on reflected Table, which supports use of cell-updates with a AutoScenarioDbTable 
- ScenarioDbManager._check_schema_name: warns if schema name is mixed case (which is causing problems).

## [0.5.4.1] - 2022-01-24
### Changed
- Fixed bug in ScenarioDbManager._read_scenario_tables_from_db
- Fixed bug in ScenarioDbManager.update_scenario_output_tables_in_db
- Fixed bug in ScenarioManager.add_file_as_data_asset when using CPDaaS
- Fixed bug in ScenarioManager.load_data_from_excel when using CPDaaS
- DOModelDeployer working in CPD4.0.3
### Added
- Added DataManager.set_parameters()
- Added print of num rows and columns inserting in ScenarioDbManager.update_scenario_output_tables_in_db
- ScenarioDbManager.insert_scenarios_from_zip
- ScenarioManager.insert_scenarios_from_zip
- AutoScenarioDbTable reflection to get SQLAlchemy table metadata from DB. Fixes bug using AutoScenarioDbTable.
- ScenarioManager.load_data_from_excel now accepts excel_file_name with and without `.xlsx` extension
- ScenarioManager.write_data_to_excel now accepts excel_file_name with and without `.xlsx` extension

## [0.5.4.0] - 2022-01-11
### Changed
- ScenarioDbManager - Converted text SQL operations to SQLAlchemy operations to support any column-name (i.e. lower, upper, mixed, reserved words)
- Updated ScenarioDbManager.read_scenario_tables_from_db to selectively read tables from a scenario
### Added
- ScenarioDbManager - Edit cells in tables
- ScenarioDbManager - Duplicate, Rename and Delete scenario
- ScenarioDbManager.read_scenario_input_tables_from_db main API to read input for solve
- ScenarioDbManager.update_scenario_output_tables_in_db main API to store solve output

## [0.5.3.1] - 2021-12-30
### Changed
- (critical) ScenarioDbManager - Replaced OrderedDict with Dict as type. Was causing a syntax error. 

## [0.5.3.0] - 2021-12-30
### Changed
- ScenarioDbManager - refactoring, cleanup and documentation
### Added
- ScenarioDbManager - enable_sqlite_fk feature to include FK checks in SQLite
- ScenarioDbManager - enable_transactions feature to use transactions and rollbacks
- ScenarioDbManager - automatically insert a ScenarioTable in input tables
- plotly_cpd_workaround with go.Figure._show method
### Removed
- ScenarioDbTable - removed db_table_name to snake_case conversion
- plotlymanager - go.Figure._show method (moved to separate module)

## [Unreleased]## [0.5.2.1b]
### Changed
- (critical) Fix IPython import for `_show()` workaround in PlotlyManager to avoid import exception when running on local workstation

## [0.5.2.0] - 2021-12-26
### Changed
- (minor) Release dates in this change log
- ScenarioDbManager support for DB2 in cloud
- Fixed AutoScenarioDbTable functionality in ScenarioDbManager
- Bumped-up version to 0.5.2 due to many changes
### Added
- Optional forced platform/version in ScenarioManager
- DataManager.print_inputs_outputs_summary() method
- inputs and outputs arguments to ScenarioManager.__init__
- Mixed-case db_table_name warning in ScenarioDbTable
- DB-table-name reserved word warning in ScenarioDbTable
- plotlymanager module
- Cached read of scenarios table in ScenarioDbManager
### Removed
- (minor) Removed support for DSX as platform choice

## [0.5.1.0] - 2021-11-30
### Changed
- Writing data asset in CP4DaaS (as of 30 Nov 2021)
- Data asset folder location in CP4D v4.0.2 (with new git)
- Save Excel/lp/csv files using ibm_watson_studio_lib in CPD v4.0.2 in ScenarioManager
### Added
- DataManager.extract_solution_v1 static method
- DataManager.get_raw_table_by_name method

## [0.5.0.1] - 2021-10-29
### Changed
- ScenarioManager.write_data_into_scenario now supports a template scenario name when creating a new scenario.

## [0.5.0.0] - 2021-08-14
### Changed
- Replace dd-scenario with decision-optimization-client==1.0.0 package (essential for CP4D 4.0)
- Deprecated the DOModelExporter: dev does not support exporting a DO model in any way.
- Fixed bug in ScenarioManager.create_new_scenario when using a template scenario
### Added
- 

## [0.4.1.0] - 2021-07-16
### Added
- MultiScenarioManager
- ScenarioManager.load_data_from_excel_s load subset of tables
- First draft of the ScenarioDbManager (undocumented)
- Fixes to DeployedDOModel to make it CPD 3.5 compatible (new WML client)
- Bumping the version from 0.4.0.2b to 0.4.1.0b due to the many changes
- DataManager.prepare_data_frames method

## [0.4.0.1]  - 2020-12-14
### Added
- ScenarioManager.write_data_to_excel returns Excel filepath

### Changed
- Fix in DataManager.df_crossjoin_ai to make compatible with Pandas 1.0

## [0.4.0.0] - 2020-06-23
### Changed
- Support for WS Cloud (project context in Client)
- More flexibility on accepting Boolean values as float or int parameter 
### Added
- Python data types in code

## [0.3.0.1] - 2020-03-04
### Added
- DOModelExporter: export DO models in CPDv2.5
- cpd25utilities: some data asset read and write functions

## [0.3.0.0] - 2020-02-22
### Changed
- Support for CPD2.5
- Writing files and add them as Data Asset in CPD v2.5
- Only for Python 3.6
- Adding try-except to import dse_do_utils modules to support DO Model Builder adding modules as additional files.
- Maintained backward compatibility with CPD v2.1

## [0.2.2.3] - 2019-07-10
### Added
- DataManager.get_parameter_value supports datetime

### Changed
- Import of `widgets` added to each usage in ScenarioPicker. 
- Update of README

## [0.2.2.2] - 2019-07-08
### Added
- This CHANGELOG.md
- Uploaded to [PyPI](pypi.org)

### Changed
- None

### Removed
- None

## [0.2.2.1] - 2019-05-25
### Changed
- Documentation
- Available on [PyPI Test](test.pypi.org)



