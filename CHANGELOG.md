# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
## [0.5.1.0b]
### Changed
- data asset folder location in CP4D v4.0.2 (with new git)

## [0.5.0.1]
### Changed
- ScenarioManager.write_data_into_scenario now supports a template scenario name when creating a new scenario.
### Added
- DataManager.extract_solution static method

## [0.5.0.0]
### Changed
- Replace dd-scenario with decision-optimization-client==1.0.0 package (essential for CP4D 4.0)
- Deprecated the DOModelExporter: dev does not support exporting a DO model in any way.
- Fixed bug in ScenarioManager.create_new_scenario when using a template scenario
### Added
- 

## [0.4.1.0]
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



