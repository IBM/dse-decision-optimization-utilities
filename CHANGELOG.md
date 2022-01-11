# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]## [0.5.4.0b]
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
- DataManager.extract_solution static method
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



