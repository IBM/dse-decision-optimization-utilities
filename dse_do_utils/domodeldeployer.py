# Copyright IBM All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

from typing import Sequence, List, Dict, Tuple, Optional
# from ibm_watson_machine_learning import APIClient
import os
import shutil
import tarfile
from dse_do_utils.scenariomanager import ScenarioManager
import time
import pathlib
import tempfile


class DOModelDeployer(object):
    """Deploys a DO Model in WML. For use in CPD 4.0. Retrieves the model from the DO Model Builder.

    Usage::

        md = DOModelDeployer(wml_credentials, model_name, scenario_name, space_name,
                             package_paths, file_paths,
                             deployment_name, deployment_description)
        deployment_uid = md.deploy_model()
        print(deployment_uid)

        How to add Python modules in the root:
        - Specify paths to modules (.py files) in `file_paths`. These modules are included in the root of the project
          and can be accessed using `from my_module import MyClass`. This is similar to the additional files in the DO Experiment.
          These files can be located anywhere in JupyterLab.
        How to add a Python package:
        1. From conda

    """

    def __init__(self, wml_credentials: Dict, model_name: str, scenario_name: str, space_name: str,
                 package_paths: List[str]=[],
                 file_paths: List[str]=[],
                 deployment_name: str = 'xxx', deployment_description: str = 'xxx', project=None,
                 tmp_dir: str = None):
        """
        Support for custom packages:
        1. For packages in conda/PyPI: through the yaml.
        2. For other custom packages: make sure you have the zip/gz package file (.whl doesn't (yet) work)
        Specify the path(s) to the zip/gz files in package_paths.
        Yaml and multiple package files can be combined

        :param wml_credentials
        :param model_name (str): name of DO Experiment
        :param scenario_name (str): name of scenario with the Python model
        :param space_name (str): name of deployment space
        :param package_paths (List[str]): list paths to zip/gz packages that will be included.
        :param file_paths (List[str]): list paths to files that will be included along side the model. Components can be imported using `from my_file import MyClass`
        :param space_name (str): name of deployment space
        :param project (project_lib.Project): for WS Cloud, not required for CP4D on-prem. See ScenarioManager(). Used to connect to DO Experiment.
        :param tmp_dir (str): path to directory where the intermediate files will be written. Make sure this exists. Can be used for debugging to inspect the files. If None, will use `tempfile` to generate a temporary folder that will be cleaned up automatically.
        """
        self.wml_credentials = wml_credentials
        self.project = project
        self.model_name = model_name
        self.scenario_name = scenario_name
        #         self.space_name = space_name
        self.deployment_name = deployment_name
        self.deployment_description = deployment_description

        self.package_paths = package_paths
        self.file_paths = file_paths
        self.tmp_dir = tmp_dir

        # Initialize clients
        from ibm_watson_machine_learning import APIClient
        self.client = APIClient(wml_credentials)
        space_id = self.guid_from_space_name(space_name)  # TODO: catch error if space_name cannot be found?
        result = self.client.set.default_space(space_id)
        #         print(f"client space_id = {space_id}, result={result}")
        self.scenario_manager = ScenarioManager(model_name=model_name, scenario_name=scenario_name, project=project)

        # State
        self.model_uid = None
        self.deployment_uid = None

        # Code templates
        self.main_header_py = \
"""
from docplex.util.environment import get_environment
from os.path import splitext
import pandas
from six import iteritems

def get_all_inputs():
    '''Utility method to read a list of files and return a tuple with all
    read data frames.
    Returns:
        a map { datasetname: data frame }
    '''
    result = {}
    env = get_environment()
    for iname in [f for f in os.listdir('.') if splitext(f)[1] == '.csv']:
        with env.get_input_stream(iname) as in_stream:
            df = pandas.read_csv(in_stream)
            datasetname, _ = splitext(iname)
            result[datasetname] = df
    return result

def write_all_outputs(outputs):
    '''Write all dataframes in ``outputs`` as .csv.

    Args:
        outputs: The map of outputs 'outputname' -> 'output df'
    '''
    for (name, df) in iteritems(outputs):
        csv_file = '%s.csv' % name
        print(csv_file)
        with get_environment().get_output_stream(csv_file) as fp:
            if sys.version_info[0] < 3:
                fp.write(df.to_csv(index=False, encoding='utf8'))
            else:
                fp.write(df.to_csv(index=False).encode(encoding='utf8'))
    if len(outputs) == 0:
        print("Warning: no outputs written")

def __iter__(self): return 0
# Load CSV files into inputs dictionnary
inputs = get_all_inputs()
outputs = {}

###########################################################
# Insert model below
###########################################################
"""
        self.main_footer_py = \
"""
###########################################################

# Generate output files
write_all_outputs(outputs)
"""
        self.yaml = \
"""
dependencies:
  - pip:
    - dse-do-utils==0.5.4.0
"""

    def deploy_model(self) -> str:
        """One call that deploys a model from the Model Builder scenario into WML.
        Creates a model archive from the extracted model code.
        Then uploads into WML and creates a deployment.

        Returns:
            deployment_uid (str): Deployment UID necessary to call the deployment.
        """
        if self.tmp_dir is None:
            with tempfile.TemporaryDirectory() as path:
                model_archive_file_path = self.create_model_archive(path)
                yaml_file_path = self.write_yaml_file(os.path.join(path, "main.yml"))
                deployment_uid = self.deploy_archive(model_archive_file_path, yaml_file_path)
        else:
            model_archive_file_path = self.create_model_archive(self.tmp_dir)
            yaml_file_path = self.write_yaml_file(os.path.join(self.tmp_dir, "main.yml"))
            deployment_uid = self.deploy_archive(model_archive_file_path, yaml_file_path)
        return deployment_uid

    ############################################
    # Create model archive
    ############################################
    def create_model_archive(self, path: str):
        """Creates a model archive on the path:
        The archive contains one .py file: the do-model surrounded by boilerplate code to process
        the inputs and outputs dictionaries.
        Steps:
        1. Write a file `path/main.py`
        2. Creates an archive file in path
        3. Adds the main.py
        4. Adds packages
        5. Adds (module) files
        """

        main_file_path = os.path.join(path, 'main.py')
        self.write_main_file(main_file_path)
        file_path = self.create_archive(main_file_path, path)
        return file_path

    def create_model_directory(self) -> str:
        """Create a directory 'model' in the default path.
        Will remove/clear first if exists.

        Return:
            path
        """
        path = 'model'
        if os.path.isdir(path):
            shutil.rmtree(path)
        os.makedirs(path)
        return path

    def write_main_file(self, file_path: str):
        """Write the code for the main.py file.
        Adds the code template header and footer.
        """
        scenario = self.get_scenario()
        with open(file_path, "w") as f:
            f.write(self.main_header_py)
            f.write('\n')
            f.write(scenario.get_asset_data('model.py').decode('ascii'))
            f.write('\n')
            f.write(self.main_footer_py)

    def write_yaml_file(self, file_path: str = './main.yml'):
        """Write the code for the main.py file.
        Adds the code template header and footer.
        """
        with open(file_path, "w") as f:
            f.write(self.yaml)
        return file_path


    def get_scenario(self):
        scenario = self.scenario_manager.get_do_scenario(self.model_name, self.scenario_name)
        return scenario

    def create_archive(self, main_file_path: str, path: str):
        """Create archive.
        For now assume one folder `model` with one file `main.py`

        :param main_file_path: file path of main.py file
        :param path: folder where archive will be written
        """
        def reset(tarinfo):
            tarinfo.uid = tarinfo.gid = 0
            tarinfo.uname = tarinfo.gname = "root"
            return tarinfo
        tar_file_path = os.path.join(path, "model.tar.gz")
        tar = tarfile.open(tar_file_path, "w:gz")
        #         tar.add("model/main.py", arcname="main.py", filter=reset)
        tar.add(main_file_path, arcname="main.py", filter=reset)

        def filter_package(tarinfo):
            tarinfo.uid = tarinfo.gid = 0
            tarinfo.uname = tarinfo.gname = "root"
            if pathlib.Path(tarinfo.name).stem == '__pycache__':
                return None
            return tarinfo

        for package_path in self.package_paths:
            package_name = pathlib.Path(package_path).stem
            print(f"Including package '{package_name}'")
            tar.add(package_path, arcname=package_name, filter=filter_package)

        for file_path in self.file_paths:
            file_name = pathlib.Path(file_path).name
            print(f"Including file '{file_name}'")
            tar.add(file_path, arcname=file_name, filter=filter_package)

        tar.close()
        return tar_file_path

    #########################################################
    # Deploy model
    #########################################################
    def deploy_archive(self, model_archive_file_path, yaml_file_path):
        print(f"model_archive_file_path={model_archive_file_path}, yaml_file_path={yaml_file_path}")
        self.model_uid = self.wml_store_model(model_archive_file_path, yaml_file_path)
        self.deployment_uid = self.wml_create_deployment(self.model_uid)
        return self.deployment_uid

    def wml_store_model(self, model_archive_file_path, yaml_file_path) -> str:
        """Stores model in WML
        Returns:
            model_uid
        """
        yaml_pkg_ext_id = self.create_package_extension(yaml_file_path)  # Rename to `create_yaml_package_extension`
        pkg_ext_ids=[yaml_pkg_ext_id]

        #Add wheels/zips:
        for package_zip_filepath in self.package_paths:
            pkg_ext_ids.append(self.create_zip_package_extension(package_zip_filepath))

        sw_spec_id = self.create_software_specification(pkg_ext_ids)
        mnist_metadata = self.get_wml_create_store_model_meta_props(sw_spec_id)
        model_details = self.client.repository.store_model(model=model_archive_file_path,
                                                           meta_props=mnist_metadata)
        model_uid = self.client.repository.get_model_uid(model_details)
        return model_uid

    def create_zip_package_extension(self, package_zip_filepath: str) -> str:
        """See https://notebooks.githubusercontent.com/view/ipynb?browser=chrome&color_mode=auto&commit=37188b1a8b48be2bef34b35b55f01cba0d29ed19&device=unknown&enc_url=68747470733a2f2f7261772e67697468756275736572636f6e74656e742e636f6d2f49424d2f776174736f6e2d6d616368696e652d6c6561726e696e672d73616d706c65732f333731383862316138623438626532626566333462333562353566303163626130643239656431392f637064342e302f6e6f7465626f6f6b732f707974686f6e5f73646b2f6465706c6f796d656e74732f637573746f6d5f6c6962726172792f5573652532307363696b69742d6c6561726e253230616e64253230637573746f6d2532306c696272617279253230746f2532307072656469637425323074656d70657261747572652e6970796e62&logged_in=false&nwo=IBM%2Fwatson-machine-learning-samples&path=cpd4.0%2Fnotebooks%2Fpython_sdk%2Fdeployments%2Fcustom_library%2FUse+scikit-learn+and+custom+library+to+predict+temperature.ipynb&platform=android&repository_id=277618282&repository_type=Repository&version=98"""
        package_name = pathlib.Path(package_zip_filepath).stem
        print(f"Including package '{package_name}'")
        meta_prop_pkg_extn = {
            self.client.package_extensions.ConfigurationMetaNames.NAME: package_name,
            self.client.package_extensions.ConfigurationMetaNames.DESCRIPTION: "Pkg extension for custom lib",
            self.client.package_extensions.ConfigurationMetaNames.TYPE: "pip_zip"
        }

        pkg_extn_details = self.client.package_extensions.store(meta_props=meta_prop_pkg_extn, file_path=package_zip_filepath)
        # print(pkg_extn_details)
        pkg_extn_uid = self.client.package_extensions.get_uid(pkg_extn_details)
        #         pkg_extn_url = self.client.package_extensions.get_href(pkg_extn_details)
        return pkg_extn_uid

    def wml_create_deployment(self, model_uid) -> str:
        """Create deployment in WML
        Returns:
            deployment_uid
        """
        meta_props = self.get_wml_create_deployment_meta_props()
        deployment_details = self.client.deployments.create(model_uid, meta_props=meta_props)
        deployment_uid = self.client.deployments.get_uid(deployment_details)
        return deployment_uid

    def get_wml_create_store_model_meta_props(self, sw_spec_id):
        """Return the meta_props for the store of the model
        Separate method, so can easily be overridden
        """
        mnist_metadata = {
            self.client.repository.ModelMetaNames.NAME: self.deployment_name,
            self.client.repository.ModelMetaNames.DESCRIPTION: self.deployment_description,
            self.client.repository.ModelMetaNames.TYPE: "do-docplex_20.1",
            self.client.repository.ModelMetaNames.SOFTWARE_SPEC_UID: sw_spec_id
        }
        return mnist_metadata

    def get_wml_create_deployment_meta_props(self):
        """Return the meta_props for the creation of the deployment
        Separate method, so can easily be overridden
        """
        meta_props = {
            self.client.deployments.ConfigurationMetaNames.NAME: self.deployment_name,
            self.client.deployments.ConfigurationMetaNames.DESCRIPTION: self.deployment_description,
            self.client.deployments.ConfigurationMetaNames.BATCH: {},
            self.client.deployments.ConfigurationMetaNames.HARDWARE_SPEC: {'name': 'S', 'nodes': 1}
        }
        return meta_props

    #################################################################################
    def create_package_extension(self, yaml_file_path:str) -> str:
        current_time = time.asctime()
        meta_prop_pkg_ext = {
            self.client.package_extensions.ConfigurationMetaNames.NAME: "conda_ext_" + current_time,
            self.client.package_extensions.ConfigurationMetaNames.DESCRIPTION: "Pkg extension for conda",
            self.client.package_extensions.ConfigurationMetaNames.TYPE: "conda_yml",
        }

        # Storing the package and saving it's uid
        pkg_ext_id = self.client.package_extensions.get_uid(self.client.package_extensions.store(meta_props=meta_prop_pkg_ext,
                                                                                                 file_path=yaml_file_path))
        return pkg_ext_id

    def create_software_specification(self, pkg_ext_ids: List[str] = []) -> str:
        """Allow for multiple package_extensions"""
        current_time = time.asctime()
        # Look for the do_20.1 software specification
        base_sw_id = self.client.software_specifications.get_uid_by_name("do_20.1")

        # Create a new software specification using the default do_20.1 one as the base for it
        meta_prop_sw_spec = {
            self.client.software_specifications.ConfigurationMetaNames.NAME: "do_20.1_ext_"+current_time,
            self.client.software_specifications.ConfigurationMetaNames.DESCRIPTION: "Software specification for DO example",
            self.client.software_specifications.ConfigurationMetaNames.BASE_SOFTWARE_SPECIFICATION: {"guid": base_sw_id}
        }
        sw_spec_id = self.client.software_specifications.get_uid(self.client.software_specifications.store(meta_props=meta_prop_sw_spec)) # Creating the new software specification
        for pkg_ext_id in pkg_ext_ids:
            self.client.software_specifications.add_package_extension(sw_spec_id, pkg_ext_id) # Adding the previously created package extension to it
        return sw_spec_id

    ##############################################################################
    def guid_from_space_name(self, space_name: str) -> str:
        """Get space_id from deployment space name.
        TODO: handle exception if space_name not found.
        """
        spaces = self.client.spaces.get_details()
        return (next(item for item in spaces['resources'] if item['entity']["name"] == space_name)['metadata']['id'])


########################################################################################
# DO Model Deployer for use on a local machine (instead of CP4D)
########################################################################################

class DOModelDeployerLocal(object):
    """EXPERIMENTAL
    Please note this code is experimental. There are a number of aspects HARD-CODED. Please review the source code and override where necessary.

    Deploys a DO Model in WML. For use in CPD 4.0 and SaaS. Retrieves the model from the DO Model Builder.

    Usage::

        md = DOModelDeployer(wml_credentials, space_name,
                             package_paths, file_paths,
                             deployment_name, deployment_description)
        deployment_uid = md.deploy_model()
        print(deployment_uid)

    """
    def __init__(self, wml_credentials: Dict, space_name: str,
                 package_paths: Optional[List[str]] = None,
                 file_paths: Optional[List[str]] = None,
                 deployment_name: Optional[str] = 'xxx', deployment_description: Optional[str] = 'xxx',
                 tmp_dir: Optional[str] = None):

        self.wml_credentials = wml_credentials
        self.space_name = space_name
        self.package_paths = (package_paths if package_paths is not None else [])
        self.file_paths = (file_paths if file_paths is not None else [])
        self.deployment_name = deployment_name
        self.deployment_description = deployment_description
        self.tmp_dir = tmp_dir

        # Initialize clients
        from ibm_watson_machine_learning import APIClient
        self.client = APIClient(wml_credentials)
        space_id = self.guid_from_space_name(space_name)  # TODO: catch error if space_name cannot be found?
        result = self.client.set.default_space(space_id)

        # State
        self.model_uid = None
        self.deployment_uid = None

        # Code templates
        self.main_header_py = \
"""
from docplex.util.environment import get_environment
from os.path import splitext
import pandas
from six import iteritems

def get_all_inputs():
    '''Utility method to read a list of files and return a tuple with all
    read data frames.
    Returns:
        a map { datasetname: data frame }
    '''
    result = {}
    env = get_environment()
    for iname in [f for f in os.listdir('.') if splitext(f)[1] == '.csv']:
        with env.get_input_stream(iname) as in_stream:
            df = pandas.read_csv(in_stream)
            datasetname, _ = splitext(iname)
            result[datasetname] = df
    return result

def write_all_outputs(outputs):
    '''Write all dataframes in ``outputs`` as .csv.

    Args:
        outputs: The map of outputs 'outputname' -> 'output df'
    '''
    for (name, df) in iteritems(outputs):
        csv_file = '%s.csv' % name
        print(csv_file)
        with get_environment().get_output_stream(csv_file) as fp:
            if sys.version_info[0] < 3:
                fp.write(df.to_csv(index=False, encoding='utf8'))
            else:
                fp.write(df.to_csv(index=False).encode(encoding='utf8'))
    if len(outputs) == 0:
        print("Warning: no outputs written")

def __iter__(self): return 0
# Load CSV files into inputs dictionnary
inputs = get_all_inputs()
outputs = {}

###########################################################
# Insert model below
###########################################################
"""
        self.main_footer_py = \
"""
###########################################################

# Generate output files
write_all_outputs(outputs)
"""
        self.yaml = \
"""
dependencies:
  - pip:
    - dse-do-utils
    - sqlalchemy
"""

    def guid_from_space_name(self, space_name: str) -> str:
        """Get space_id from deployment space name.
        TODO: handle exception if space_name not found.
        """
        spaces = self.client.spaces.get_details()
        return (next(item for item in spaces['resources'] if item['entity']["name"] == space_name)['metadata']['id'])

    def deploy_model(self) -> str:
        """One call that deploys a model from the Model Builder scenario into WML.
        Creates a model archive from the extracted model code.
        Then uploads into WML and creates a deployment.

        Returns:
            deployment_uid (str): Deployment UID necessary to call the deployment.
        """
        if self.tmp_dir is None:
            with tempfile.TemporaryDirectory() as path:
                model_archive_file_path = self.create_model_archive(path)
                yaml_file_path = self.write_yaml_file(os.path.join(path, "main.yml"))
                deployment_uid = self.deploy_archive(model_archive_file_path, yaml_file_path)
        else:
            model_archive_file_path = self.create_model_archive(self.tmp_dir)
            yaml_file_path = self.write_yaml_file(os.path.join(self.tmp_dir, "main.yml"))
            deployment_uid = self.deploy_archive(model_archive_file_path, yaml_file_path)
        return deployment_uid

    ############################################
    # Create model archive
    ############################################
    def create_model_archive(self, path: str):
        """Creates a model archive on the path:
        The archive contains one .py file: the do-model surrounded by boilerplate code to process
        the inputs and outputs dictionaries.
        Steps:
        1. Write a file `path/main.py`
        2. Creates an archive file in path
        3. Adds the main.py
        4. Adds packages
        5. Adds (module) files
        """

        main_file_path = os.path.join(path, 'main.py')
        self.write_main_file(main_file_path)
        file_path = self.create_archive(main_file_path, path)
        return file_path

    def create_model_directory(self) -> str:
        """Create a directory 'model' in the default path.
        Will remove/clear first if exists.

        Return:
            path
        """
        path = 'model'
        if os.path.isdir(path):
            shutil.rmtree(path)
        os.makedirs(path)
        return path

    def write_main_file(self, file_path: str):
        """Write the code for the main.py file.
        Adds the code template header and footer.
        """
        with open(file_path, "w") as f:
            f.write(self.main_header_py)
            f.write('\n')
            # f.write(scenario.get_asset_data('model.py').decode('ascii')) # Get from DO Experiment
            f.write(self.get_model_py())
            f.write('\n')
            f.write(self.main_footer_py)

    def get_model_py(self) -> str:
        """Return the optimization model. Assume the usual inputs and outputs dicts."""
        model_py = "print('Hello World')"
        return model_py

    def write_yaml_file(self, file_path: str = './main.yml'):
        """Write the code for the main.py file.
        Adds the code template header and footer.
        """
        with open(file_path, "w") as f:
            f.write(self.yaml)
        return file_path

    def create_archive(self, main_file_path: str, path: str):
        """Create archive.
        For now assume one folder `model` with one file `main.py`

        :param main_file_path: file path of main.py file
        :param path: folder where archive will be written
        """
        def reset(tarinfo):
            tarinfo.uid = tarinfo.gid = 0
            tarinfo.uname = tarinfo.gname = "root"
            return tarinfo
        tar_file_path = os.path.join(path, "model.tar.gz")
        tar = tarfile.open(tar_file_path, "w:gz")
        #         tar.add("model/main.py", arcname="main.py", filter=reset)
        tar.add(main_file_path, arcname="main.py", filter=reset)

        def filter_package(tarinfo):
            tarinfo.uid = tarinfo.gid = 0
            tarinfo.uname = tarinfo.gname = "root"
            if pathlib.Path(tarinfo.name).stem == '__pycache__':
                return None
            return tarinfo

        for package_path in self.package_paths:
            package_name = pathlib.Path(package_path).stem
            print(f"Including package '{package_name}'")
            tar.add(package_path, arcname=package_name, filter=filter_package)

        for file_path in self.file_paths:
            file_name = pathlib.Path(file_path).name
            print(f"Including file '{file_name}'")
            tar.add(file_path, arcname=file_name, filter=filter_package)

        tar.close()
        return tar_file_path

    #########################################################
    # Deploy model
    #########################################################
    def deploy_archive(self, model_archive_file_path, yaml_file_path):
        print(f"model_archive_file_path={model_archive_file_path}, yaml_file_path={yaml_file_path}")
        self.model_uid = self.wml_store_model(model_archive_file_path, yaml_file_path)
        self.deployment_uid = self.wml_create_deployment(self.model_uid)
        return self.deployment_uid

    def wml_store_model(self, model_archive_file_path, yaml_file_path) -> str:
        """Stores model in WML
        Returns:
            model_uid
        """
        yaml_pkg_ext_id = self.create_package_extension(yaml_file_path)  # Rename to `create_yaml_package_extension`
        pkg_ext_ids=[yaml_pkg_ext_id]

        #Add wheels/zips:
        for package_zip_filepath in self.package_paths:
            pkg_ext_ids.append(self.create_zip_package_extension(package_zip_filepath))

        sw_spec_id = self.create_software_specification(pkg_ext_ids)
        mnist_metadata = self.get_wml_create_store_model_meta_props(sw_spec_id)
        model_details = self.client.repository.store_model(model=model_archive_file_path,
                                                           meta_props=mnist_metadata)
        # model_uid = self.client.repository.get_model_uid(model_details)  # deprecated: use get_model_id
        model_uid = self.client.repository.get_model_id(model_details)
        return model_uid

    def create_zip_package_extension(self, package_zip_filepath: str) -> str:
        """See https://notebooks.githubusercontent.com/view/ipynb?browser=chrome&color_mode=auto&commit=37188b1a8b48be2bef34b35b55f01cba0d29ed19&device=unknown&enc_url=68747470733a2f2f7261772e67697468756275736572636f6e74656e742e636f6d2f49424d2f776174736f6e2d6d616368696e652d6c6561726e696e672d73616d706c65732f333731383862316138623438626532626566333462333562353566303163626130643239656431392f637064342e302f6e6f7465626f6f6b732f707974686f6e5f73646b2f6465706c6f796d656e74732f637573746f6d5f6c6962726172792f5573652532307363696b69742d6c6561726e253230616e64253230637573746f6d2532306c696272617279253230746f2532307072656469637425323074656d70657261747572652e6970796e62&logged_in=false&nwo=IBM%2Fwatson-machine-learning-samples&path=cpd4.0%2Fnotebooks%2Fpython_sdk%2Fdeployments%2Fcustom_library%2FUse+scikit-learn+and+custom+library+to+predict+temperature.ipynb&platform=android&repository_id=277618282&repository_type=Repository&version=98
        TYPE can only be 'pip_zip' and package format must be a .zip (See https://dataplatform.cloud.ibm.com/docs/content/wsj/analyze-data/ml-create-custom-software-spec.html?context=cpdaas)

        """
        package_name = pathlib.Path(package_zip_filepath).stem
        print(f"Including package '{package_name}'")
        meta_prop_pkg_extn = {
            self.client.package_extensions.ConfigurationMetaNames.NAME: package_name,
            self.client.package_extensions.ConfigurationMetaNames.DESCRIPTION: "Pkg extension for custom lib",
            self.client.package_extensions.ConfigurationMetaNames.TYPE: "pip_zip"
        }

        pkg_extn_details = self.client.package_extensions.store(meta_props=meta_prop_pkg_extn, file_path=package_zip_filepath)
        # print(pkg_extn_details)
        pkg_extn_uid = self.client.package_extensions.get_uid(pkg_extn_details)
        #         pkg_extn_url = self.client.package_extensions.get_href(pkg_extn_details)
        return pkg_extn_uid

    def wml_create_deployment(self, model_uid) -> str:
        """Create deployment in WML
        Returns:
            deployment_uid
        """
        meta_props = self.get_wml_create_deployment_meta_props()
        deployment_details = self.client.deployments.create(model_uid, meta_props=meta_props)
        deployment_uid = self.client.deployments.get_uid(deployment_details)
        return deployment_uid

    def get_wml_create_store_model_meta_props(self, sw_spec_id):
        """Return the meta_props for the store of the model
        Separate method, so can easily be overridden
        """
        mnist_metadata = {
            self.client.repository.ModelMetaNames.NAME: self.deployment_name,
            self.client.repository.ModelMetaNames.DESCRIPTION: self.deployment_description,
            self.client.repository.ModelMetaNames.TYPE: "do-docplex_22.1",
            self.client.repository.ModelMetaNames.SOFTWARE_SPEC_UID: sw_spec_id
        }
        return mnist_metadata

    def get_wml_create_deployment_meta_props(self):
        """Return the meta_props for the creation of the deployment
        Separate method, so can easily be overridden

        Note that 1 node is too slow: somehow causes extended running overhead, where the CPLEX model itself can solve quickly
        Also, 2 nodes still only gives CPLEX one thread.
        """
        meta_props = {
            self.client.deployments.ConfigurationMetaNames.NAME: self.deployment_name,
            self.client.deployments.ConfigurationMetaNames.DESCRIPTION: self.deployment_description,
            self.client.deployments.ConfigurationMetaNames.BATCH: {},
            self.client.deployments.ConfigurationMetaNames.HARDWARE_SPEC: {'name': 'S', 'nodes': 2}  # 1 CPU is very slow
        }
        return meta_props

    #################################################################################
    def create_package_extension(self, yaml_file_path: str) -> str:
        current_time = time.asctime()
        meta_prop_pkg_ext = {
            self.client.package_extensions.ConfigurationMetaNames.NAME: "conda_ext_" + current_time,
            self.client.package_extensions.ConfigurationMetaNames.DESCRIPTION: "Pkg extension for conda",
            self.client.package_extensions.ConfigurationMetaNames.TYPE: "conda_yml",
        }

        # Storing the package and saving it's uid
        pkg_ext_id = self.client.package_extensions.get_uid(self.client.package_extensions.store(meta_props=meta_prop_pkg_ext,
                                                                                                 file_path=yaml_file_path))
        return pkg_ext_id

    def create_software_specification(self, pkg_ext_ids: Optional[List[str]] = None) -> str:
        """Allow for multiple package_extensions"""
        pkg_ext_ids = (pkg_ext_ids if pkg_ext_ids is not None else [])

        current_time = time.asctime()
        # Look for the do_22.1 software specification
        base_sw_id = self.client.software_specifications.get_uid_by_name("do_22.1")

        # Create a new software specification using the default do_20.1 one as the base for it
        meta_prop_sw_spec = {
            self.client.software_specifications.ConfigurationMetaNames.NAME: "do_22.1_ext_"+current_time,
            self.client.software_specifications.ConfigurationMetaNames.DESCRIPTION: "Software specification for DO example",
            self.client.software_specifications.ConfigurationMetaNames.BASE_SOFTWARE_SPECIFICATION: {"guid": base_sw_id}
        }
        sw_spec_id = self.client.software_specifications.get_uid(self.client.software_specifications.store(meta_props=meta_prop_sw_spec)) # Creating the new software specification
        for pkg_ext_id in pkg_ext_ids:
            self.client.software_specifications.add_package_extension(sw_spec_id, pkg_ext_id) # Adding the previously created package extension to it
        return sw_spec_id



