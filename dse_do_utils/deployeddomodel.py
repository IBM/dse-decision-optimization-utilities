# Copyright IBM All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
import os
from typing import Optional, List
import base64
import io

import pandas as pd
# import sys
# from watson_machine_learning_client import WatsonMachineLearningAPIClient  # Deprecated
from dse_do_utils.datamanager import Inputs, Outputs


# from ibm_watson_machine_learning import APIClient  # New client


class DeployedDOModel(object):
    """
    New DeployedDOModel for CPD3.5 based on ibm_watson_machine_learning.APIClient

    Major steps:

        1. Create an instance of a DeployedDOModel, configuring parameters

    Internally, the processes uses the APIClient (former WatsonMachineLearningAPIClient) to communicate with the deployed model:

        2. Start the solve job.
        3. Monitor the running solve job. Runs in a loop, updates the current state.
        4. Once the job completes, get the optimization result.


    In the code::

        mdl.solve():
            solve_payload = self.get_solve_payload(inputs)  # Convert inputs to payload
            job_details, job_uid = self.execute_model_v1(solve_payload)
            job_details = self.monitor_execution_v1(job_details, job_uid)
            self.extract_solution_v1(job_details)
            return job_details


    Usage::

        # Simplest, using all default options:
        mdl = DeployedDOModel(wml_credentials, space_name, deployed_model_name)
        job_details = mdl.solve(inputs)
        print("Solve status: {}".format(mdl.solve_status))
        print("Objective: {}".format(mdl.objective))
        print("Output tables: {}".format(mdl.outputs.keys()))


    TODOs:

        1. Debug mode
        2. Get the cplex log file?
        3. Done - Add kill and stop methods
        4. Done - Configure polling interval


    """

    def __init__(self, wml_credentials,
                 space_name: Optional[str]= None, deployed_model_name: Optional[str]= None, deployment_id: Optional[str]=None,
                 default_max_oaas_time_limit_sec: Optional[int]= None, default_max_run_time_sec: Optional[int]= 600, monitor_loop_delay_sec: int = 5,
                 space_id: Optional[str] = None):
        """Initialize the interface object.
        For IBM Cloud/watsonx.ai, we'll need:
        1. Deployment Space name - the name of the deployment space, or
        2. Deployment Space GUID - the GUID of the Deployment Space (see Deployment spaces -> <space> -> 'Manage' tab)

        Then, we need either:
        1. Deployment model name - the name of the deployed model in the deployment space, or
        2. Deployment model id - the Deployment ID of deployed model in the deployment space

        Note: providing the ids is slightly more efficient. If proving the name, the DeployedDOModel will look for the Deployment Space GUID and/or the DeploymentID based on their names.

        Time limits:
        - Both are optional: if no value, no time-limit is imposed
        - These are default values. Can be overridden in solve method

        Args:
            deployed_model_name (str): name of deployed model (CPD)
            space_name (str): name of deployment space (CPD)
            deployment_id (str): Deployment UUID (WS Cloud)
            default_max_oaas_time_limit_sec (int): default oaas.timeLimit in seconds.
            default_max_run_time_sec (int): default maximum run time in seconds. Includes the queueing time.
            monitor_loop_delay_sec (int): delay in seconds in monitoring/polling loop
            space_id (str): space_id / space GUID. If not specified will be derived from the space_name.
        """

        # Inputs
        self.wml_credentials = wml_credentials
        self.space_name = space_name
        self.space_id = space_id
        self.model_name = deployed_model_name
        self.deployment_id = deployment_id
        self.default_max_oaas_time_limit_sec = default_max_oaas_time_limit_sec  # In seconds! None implies no time timit. Note the original oaas.timeLimit is in milli-seconds!
        self.default_max_run_time_sec = default_max_run_time_sec  #60  # In seconds: Job will be deleted. None implies no time timit.
        self.monitor_loop_delay_sec = monitor_loop_delay_sec  # In seconds
        # self.time_limit = 600  # in milliseconds. timeLimit for DO model cancel
        #         self.inputs = inputs
        #         self.debug = debug
        #         self.debug_file_dir = debug_file_dir
        #         self.log_file_name = log_file_name

        # State:
        self.solve_status: str = None
        self.objective = None
        self.solve_details: dict = {}
        self.outputs = {}
        self.run_time = 0  # Run-time of job in seconds
        self.job_details: dict = None
        self.log_lines: List[str] = None

        # Setup and connection to deployed model
        # from ibm_watson_machine_learning import APIClient
        from ibm_watsonx_ai import APIClient
        self.client = APIClient(wml_credentials)

        # space_id = [x['metadata']['id'] for x in self.client.spaces.get_details()['resources'] if
        #             x['entity']['name'] == space_name][0]
        if self.space_id is None:
            self.space_id = self.get_space_id(space_name)
        self.client.set.default_space(self.space_id)  # Also required when using deployment_id

        if self.deployment_id is None:
            self.deployment_id = self.get_deployment_id(deployed_model_name)

    def solve(self, inputs: Inputs, max_oaas_time_limit_sec: int = None, max_run_time_sec: int = None) -> dict:
        """Master routine. Initializes the job, starts the execution, monitors the results, post-processes the solution and cleans-up after.

        Args:
            inputs (dict of DataFrames): input tables
            max_oaas_time_limit_sec (int): will override the default from the constructor
            max_run_time_sec (int): will override the default from the constructor

        Calls the following methods (in order)::

            self.retrieve_solve_configuration()
            self.set_output_settings_in_solve_configuration()
            self.execute_model_v1()
            self.monitor_execution_v1()
            self.retrieve_debug_materials()
            self.cleanup()

        """
        job_details = self.solve_v2(inputs, max_oaas_time_limit_sec, max_run_time_sec)
        return job_details

    def get_solve_payload(self, inputs: Inputs, max_oaas_time_limit_sec: Optional[int] = None):
        input_data = [{"id": f"{table_name}.csv", "values": df} for table_name, df in inputs.items()]
        output_data = [
            {"id": ".*\.csv"},
            {"id": "log.txt"},  # Ensures the log.txt is added to the job_details output_data
                       ]
        solve_parameters = {"oaas.logTailEnabled": "true",
                            "oaas.logLimit": 20_000,
                            "oaas.logAttachmentName": 'log.txt'}
        if max_oaas_time_limit_sec is not None:
            solve_parameters['oaas.timeLimit'] = max_oaas_time_limit_sec * 1000,  # oaas.timeLimit needs to be specified in milli-seconds
        solve_payload = {self.client.deployments.DecisionOptimizationMetaNames.INPUT_DATA: input_data,
                         self.client.deployments.DecisionOptimizationMetaNames.OUTPUT_DATA: output_data,
                         self.client.deployments.DecisionOptimizationMetaNames.SOLVE_PARAMETERS: solve_parameters
                         #                              {"oaas.timeLimit": max_oaas_time_limit_sec * 1000,  # oaas.timeLimit needs to be specified in milli-seconds
                         #                               "oaas.logTailEnabled": "true",
                         #                               "oaas.logLimit": 10000,
                         #                               "oaas.logAttachmentName": 'log.txt'}
                         }
        print(f"max_oaas_time_limit_sec = {max_oaas_time_limit_sec}")
        return solve_payload


    # def solve_v1(self, inputs: Inputs, max_oaas_time_limit_sec: int = None, max_run_time_sec: int = None):
    #     """DEPRECATED
    #     Master routine. Initializes the job, starts the execution, monitors the results, post-processes the solution and cleans-up after.
    #
    #     Args:
    #         inputs (dict of DataFrames): input tables
    #         max_oaas_time_limit_sec (int): will override the default from the constructor
    #         max_run_time_sec (int): will override the default from the constructor
    #
    #     Calls the following methods (in order)::
    #
    #         self.retrieve_solve_configuration()
    #         self.set_output_settings_in_solve_configuration()
    #         self.execute_model_v1()
    #         self.monitor_execution_v1()
    #         self.retrieve_debug_materials()
    #         self.cleanup()
    #
    #     """
    #     if max_run_time_sec is None:
    #         max_run_time_sec = self.default_max_run_time_sec
    #     if max_oaas_time_limit_sec is None:
    #         max_oaas_time_limit_sec = self.default_max_oaas_time_limit_sec
    #     from time import sleep
    #     job_details = self.execute_model_v1(inputs, max_oaas_time_limit_sec)
    #     sleep(0.5)  # Give a little time for the job to start
    #     job_details = self.monitor_execution_v1(job_details, max_run_time_sec)
    #     self.extract_solution_v1(job_details)
    #     return job_details
    #
    #
    # def execute_model_v1(self, inputs: Inputs, max_oaas_time_limit_sec: Optional[int]):
    #     """DEPRECATED"""
    #     solve_payload = self.get_solve_payload(inputs, max_oaas_time_limit_sec)
    #     job_details = self.client.deployments.create_job(self.deployment_id, solve_payload)
    #     return job_details
    #
    # def monitor_execution_v1(self, job_details, max_run_time_sec: Optional[int] = None):
    #     """DEPRECATED
    #     Monitor the model execution by periodically calling the API to get the current execution status.
    #     Result stored in self.execution_status_json and self.execution_status.
    #
    #     """
    #     import time
    #     # from time import sleep
    #     start_time = time.time()  # in seconds
    #     # your code
    #     elapsed_time = 0
    #     job_uid = self.client.deployments.get_job_uid(job_details)
    #     job_status = DeployedDOModel.get_job_status(job_details)
    #     while job_status not in ['completed', 'failed', 'canceled']:
    #         print(f"{job_status}.... run-time={elapsed_time:.1f}")
    #         time.sleep(self.monitor_loop_delay_sec)
    #         # Just specifying include='status' reduces the payload significantly. If not, it will in,cude all the input tables
    #         job_details = self.client.deployments.get_job_details(job_uid, include="status")
    #         job_status = DeployedDOModel.get_job_status(job_details)
    #         elapsed_time = time.time() - start_time
    #         if max_run_time_sec is not None and elapsed_time > max_run_time_sec:
    #             self.client.deployments.delete_job(job_uid, hard_delete=True)
    #             print(f"Job deleted due to run-time exceeding maximum limit of {max_run_time_sec} seconds")
    #             self.solve_status = 'JOB DELETED'
    #             break
    #
    #     # Make sure to get the full job_details. In the above loop we only get the status
    #     job_details = self.client.deployments.get_job_details(job_uid)
    #     self.run_time = elapsed_time
    #     #         print(job_status)
    #     print(f"End monitor_execution_v1 with job_status = {job_status}, run-time={elapsed_time:.1f}")
    #     return job_details
    #
    # def extract_solution_v1(self, job_details):
    #     self.job_details = job_details
    #     job_status = DeployedDOModel.get_job_status(job_details)
    #     if job_status == 'completed':
    #         self.solve_status = self.get_solve_status(job_details)
    #         self.objective = self.get_solve_details_objective(job_details)
    #         self.outputs = self.get_outputs(job_details)
    #         self.solve_details = self.get_solve_details(job_details)

    def solve_v2(self, inputs: Inputs, max_oaas_time_limit_sec: int = None, max_run_time_sec: int = None) -> dict:
        """Master routine. Initializes the job, starts the execution, monitors the results, post-processes the solution and cleans-up after.

        Args:
            inputs (dict of DataFrames): input tables
            max_oaas_time_limit_sec (int): will override the default from the constructor
            max_run_time_sec (int): will override the default from the constructor

        Calls the following methods (in order)::

            self.retrieve_solve_configuration()
            self.set_output_settings_in_solve_configuration()
            self.execute_model_v1()
            self.monitor_execution_v1()
            self.retrieve_debug_materials()
            self.cleanup()

        """
        if max_run_time_sec is None:
            max_run_time_sec = self.default_max_run_time_sec
        if max_oaas_time_limit_sec is None:
            max_oaas_time_limit_sec = self.default_max_oaas_time_limit_sec
        from time import sleep
        job_uid = self.execute_model_v2(inputs, max_oaas_time_limit_sec)
        sleep(0.5)  # Give a little time for the job to start
        job_status = self.monitor_execution_v2(job_uid, max_run_time_sec)
        job_details = self.extract_solution_v2(job_uid)
        return job_details

    def execute_model_v2(self, inputs: Inputs, max_oaas_time_limit_sec: Optional[int]) -> str:
        """
        Args:
            inputs: inputs dict
            max_oaas_time_limit_sec: int - number of seconds for the WML job time limit.
        Returns:
            job_uid: str
        """
        solve_payload = self.get_solve_payload(inputs, max_oaas_time_limit_sec)
        job_details = self.client.deployments.create_job(self.deployment_id, solve_payload)
        job_uid = self.client.deployments.get_job_uid(job_details)
        return job_uid

    def monitor_execution_v2(self, job_uid: str, max_run_time_sec: Optional[int] = None) -> str:
        """Monitor the model execution by periodically calling the API to get the current execution status.
        Result stored in self.execution_status_json and self.execution_status.
        Time-out after max_run_time_sec. Job will be deleted if total monitor time exceeds this limit.

        Args:
            job_uid: str
            max_run_time_sec: int - Number of seconds maximum processing time (queued + run time) before the job must complete

        Returns:
            job_status: str
        """
        import time
        # from time import sleep
        start_time = time.time()  # in seconds
        # your code
        elapsed_time = 0
        job_status = self.get_job_status_v2(job_uid)
        while job_status not in ['completed', 'failed', 'canceled']:
            print(f"{job_status}.... run-time={elapsed_time:.1f}")
            time.sleep(self.monitor_loop_delay_sec)
            job_status = self.get_job_status_v2(job_uid)
            elapsed_time = time.time() - start_time
            if max_run_time_sec is not None and elapsed_time > max_run_time_sec:
                self.client.deployments.delete_job(job_uid, hard_delete=True)
                print(f"Job deleted due to run-time exceeding maximum limit of {max_run_time_sec} seconds")
                self.solve_status = 'JOB DELETED'
                break

        # Make sure to get the full job_details. In the above loop we only get the status
        # job_details = self.client.deployments.get_job_details(job_uid)
        self.run_time = elapsed_time
        #         print(job_status)
        print(f"End monitor_execution_v1 with job_status = {job_status}, run-time={elapsed_time:.1f}")
        return job_status

    def extract_solution_v2(self, job_uid: str) -> dict:
        job_details: dict = self.client.deployments.get_job_details(job_uid)
        self.job_details = job_details
        job_status = DeployedDOModel.get_job_status(job_details)
        if job_status == 'completed':
            self.solve_status = self.get_solve_status(job_details)
            self.objective = self.get_solve_details_objective(job_details)
            self.outputs = self.get_outputs(job_details)
            self.solve_details = self.get_solve_details(job_details)
            self.log_lines = self.get_log(job_details)
        else:
            print(f"Job_status not 'completed': cannot extract solution")
        return job_details

    def get_job_status_v2(self, job_uid: str) -> str:
        """Retrieves the job_status from a job.

        :param job_uid:
        :return:
            job_status: str - The job_status. Either: queued, running, completed, failed, canceled
        """
        # Just specifying include='status' reduces the payload significantly. If not, it will inlcude all the input tables
        # Q: Add ', solve_state' to include to get the log-tail? Answer: when running, the solve_state has no meaningful
        # information and does not have the latest_engine_activity
        job_details = self.client.deployments.get_job_details(job_uid, include="status")
        job_status = DeployedDOModel.get_job_status(job_details)
        return job_status

    @staticmethod
    def get_job_status(job_details: dict) -> str:
        """Extract job_status from the job_details
        Returns:
            Job state can be : queued, running, completed, failed, canceled."""
        return job_details['entity']['decision_optimization']['status']['state']

    @staticmethod
    def get_outputs(job_details: dict) -> Outputs:
        outputs = {}
        for output_table in job_details['entity']['decision_optimization']['output_data']:
            # table_name = output_table['id'][:-4]  # strips the '.csv'
            output_id = output_table['id']
            filename, file_extension = os.path.splitext(output_id)
            if file_extension == '.csv':
                df = pd.DataFrame(output_table['values'], columns=output_table['fields'])
                outputs[filename] = df
            # if output_id == 'log.txt':
            #     print(f"Detected log.txt in job_details:") #: {output_table['content']}")


        return outputs

    @staticmethod
    def get_log(job_details: dict) -> List[str]:
        """Extracts the log.txt from the job_details, if it exists.

        Returns:
            log_lines: List[str] - the lines of the log.txt
        """
        log_lines = []
        for output_table in job_details['entity']['decision_optimization']['output_data']:
            output_id = output_table['id']
            if output_id == 'log.txt':
                print(f"Detected log.txt in job_details:")
                for line in io.BytesIO(base64.b64decode(output_table['content'])):
                    log_lines.append(str(line))
                    print(line)
        return log_lines

    @staticmethod
    def get_solve_status(job_details: dict) -> str:
        """Retreives the solve_status from job_details. After job has completed"""
        return job_details['entity']['decision_optimization']['solve_state']['solve_status']

    @staticmethod
    def get_solve_details(job_details: dict) -> dict:
        """After job has completed"""
        return job_details['entity']['decision_optimization']['solve_state']['details']

    @staticmethod
    def get_solve_details_objective(job_details: dict):
        """After job has completed.
        Note: not sure where the objective is. Can be PROGRESS_CURRENT_OBJECTIVE or PROGRESS_BEST_OBJECTIVE"""
        try:
            objective = float(job_details['entity']['decision_optimization']['solve_state']['details']['PROGRESS_CURRENT_OBJECTIVE'])
        except:
            print("Cannot extract objective value")
            objective = 0
        return objective

    def get_space_id(self, space_name: str) -> str:
        """Find space_id from space_name."""
        space_id = [x['metadata']['id'] for x in self.client.spaces.get_details()['resources'] if
                    x['entity']['name'] == space_name][0]
        return space_id

    def get_deployment_id(self, model_name: str) -> str:
        """Find deployment_id from model_name."""
        deployment_id = [x['metadata']['id'] for x in self.client.deployments.get_details()['resources'] if
                         x['entity']['name'] == model_name][0]
        return deployment_id
