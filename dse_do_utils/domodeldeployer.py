# Copyright IBM All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

from typing import Sequence, List, Dict, Tuple, Optional
from watson_machine_learning_client import WatsonMachineLearningAPIClient
from dd_scenario import Client
import os
import shutil
import tarfile


class DOModelDeployer(object):
    """Deploys a DO Model in WML. For use in WS Cloud. Retrieves the model from the DO Model Builder.

    Usage::
        md = DOModelDeployer(wml_credentials, project, model_name, scenario_name, deployment_name, deployment_description)
        print(md.client.version)
        deployment_uid = md.deploy_model()
        print(deployment_uid)

    Make sure to use the watson-machine-learning-client-V4: version should look like '1.0.73'
    (with the last number to be 2 digits (instead of 3 for V3).

    """

    def __init__(self, wml_credentials: Dict, project, model_name: str, scenario_name: str,
                 deployment_name: str, deployment_description: str):
        self.wml_credentials = wml_credentials
        self.project = project
        self.model_name = model_name
        self.scenario_name = scenario_name
        self.deployment_name = deployment_name
        self.deployment_description = deployment_description

        # Initialize clients
        self.client = WatsonMachineLearningAPIClient(wml_credentials)
        self.mb_client = Client(pc=project.project_context)

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

    def deploy_model(self) -> str:
        """One call that deploys a model from the Model Builder scenario into WML.
        Creates a model archive from the extracted model code.
        Then uploads into WML and creates a deployment.

        Returns:
            deployment_uid (str): Deployment UID necessary to call the deployment.
        """
        self.create_archive()
        deployment_uid = self.deploy_archive()
        return deployment_uid

    ############################################
    # Create model archive
    ############################################
    def create_model_archive(self):
        """Creates a model archive on the default path:
        The archive contains one .py file: the do-model surrounded by boilerplate code to process
        the inputs and outputs dictionaries.
        Steps:
        1. Creates a directory `model`
        2. Write a file `model/main.py`
        3. Creates an archive file from the model directory
        """
        path = self.create_model_directory()
        file_path = os.path.join(path, 'main.py')
        self.write_main_file(file_path)
        self.create_archive()

    def create_model_directory(self) -> str:
        """Create a directory in the default path.
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
        pass

    def get_scenario(self):
        dd_model_builder = self.mb_client.get_model_builder(name=self.model_name)
        scenario = dd_model_builder.get_scenario(name=self.scenario_name)
        return scenario

    def create_archive(self):
        """Create archive.
        For now assume one folder `model` with one file `main.py`
        """
        def reset(tarinfo):
            tarinfo.uid = tarinfo.gid = 0
            tarinfo.uname = tarinfo.gname = "root"
            return tarinfo
        tar = tarfile.open("model.tar.gz", "w:gz")
        tar.add("model/main.py", arcname="main.py", filter=reset)
        tar.close()

    #########################################################
    # Deploy model
    #########################################################
    def deploy_archive(self):
        self.model_uid = self.wml_store_model()
        self.deployment_uid = self.wml_create_deployment(self.model_uid)
        return self.deployment_uid

    def wml_store_model(self) -> str:
        """Stores model in WML
        Returns:
            model_uid
        """
        mnist_metadata = self.get_wml_create_store_model_meta_props()
        model_details = self.client.repository.store_model(model='/home/dsxuser/work/model.tar.gz',
                                                           meta_props=mnist_metadata)
        model_uid = self.client.repository.get_model_uid(model_details)
        return model_uid

    def wml_create_deployment(self, model_uid) -> str:
        """Create deployment in WML
        Returns:
            deployment_uid
        """
        meta_props = self.get_wml_create_deployment_meta_props()
        deployment_details = self.client.deployments.create(model_uid, meta_props=meta_props)
        deployment_uid = self.client.deployments.get_uid(deployment_details)
        return deployment_uid

    def get_wml_create_store_model_meta_props(self):
        """Return the meta_props for the store of the model
        Separate method, so can easily be overridden
        """
        mnist_metadata = {
            self.client.repository.ModelMetaNames.NAME: self.deployment_name,
            self.client.repository.ModelMetaNames.DESCRIPTION: self.deployment_description,
            self.client.repository.ModelMetaNames.TYPE: "do-docplex_12.9",
            self.client.repository.ModelMetaNames.RUNTIME_UID: "do_12.9"
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
            self.client.deployments.ConfigurationMetaNames.COMPUTE: {'name': 'S', 'nodes': 1}
        }
        return meta_props






