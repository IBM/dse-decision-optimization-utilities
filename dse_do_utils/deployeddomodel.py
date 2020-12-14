# Copyright IBM All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import pandas as pd
# import sys
from watson_machine_learning_client import WatsonMachineLearningAPIClient


class DeployedDOModel(object):
    """
    New DeployedDOModel for CPD2.5

    Major steps:

        1. Create an instance of a DeployedDOModel, configuring parameters

    Internally, the processes uses the WatsonMachineLearningAPIClient to communicate with the deployed model:

        2. Start the solve job.
        3. Monitor the running solve job. Runs in a loop, updates the current state.
        4. Once the job completes, get the optimization result.


    In the code::

        mdl.solve():
            solve_payload = self.get_solve_payload(inputs)  # Convert inputs to payload
            job_details, job_uid = self.execute_model(solve_payload)
            job_details = self.monitor_execution(job_details, job_uid)
            self.extract_solution(job_details)
            return job_details


    Usage::

        # Simplest, using all default options:
        mdl = DeployedDOModel(wml_credentials, space_name, model_name)
        job_details = mdl.solve(inputs)
        print("Solve status: {}".format(mdl.solve_status))
        print("Objective: {}".format(mdl.objective))
        print("Output tables: {}".format(mdl.outputs.keys()))


    TODOs:

        1. Debug mode
        2. Get the cplex log file?
        3. Add kill and stop methods
        4. Configure polling interval


    """

    def __init__(self, wml_credentials, space_name=None, model_name=None, deployment_uid=None):
        """Initialize the interface object.
        If the deployment_uuid is specified (WS Cloud), the space_name and model_name are optional.
        If no deployment_uuid (CPD), specify both the model and space name.
        Will find UUID based on space and model id.

        Args:
            model_name (str): name of deployed model (CPD)
            space_name (str): name of deployment space (CPD)
            deployment_uuid (str): Deployment UUID (WS Cloud)
        """

        # Inputs
        self.wml_credentials = wml_credentials
        self.space_name = space_name
        self.model_name = model_name
        self.deployment_uid = deployment_uid
        self.max_run_time = 60  # seconds: Job will be deleted
        # self.time_limit = 600  # in milliseconds. timeLimit for DO model cancel
        #         self.inputs = inputs
        #         self.debug = debug
        #         self.debug_file_dir = debug_file_dir
        #         self.log_file_name = log_file_name

        # State:
        self.solve_status = None
        self.objective = None
        self.solve_details = {}
        self.outputs = {}
        self.run_time = 0  # Run-time of job in seconds
        self.job_details = None

        # Setup and connection to deployed model
        self.client = WatsonMachineLearningAPIClient(wml_credentials)

        if self.deployment_uid is None:
            space_id = [x['metadata']['id'] for x in self.client.spaces.get_details()['resources'] if
                        x['entity']['name'] == space_name][0]
            self.client.set.default_space(space_id)
            self.deployment_uid = [x['metadata']['guid'] for x in self.client.deployments.get_details()['resources'] if
                                   x['entity']['name'] == model_name][0]

    def solve(self, inputs, time_limit=1000, max_run_time=60):
        """Master routine. Initializes the job, starts the execution, monitors the results, post-processes the solution and cleans-up after.

        Args:
            inputs (dict of DataFrames): input tables

        Calls the following methods (in order)::

            self.retrieve_solve_configuration()
            self.set_output_settings_in_solve_configuration()
            self.execute_model()
            self.monitor_execution()
            self.retrieve_debug_materials()
            self.cleanup()

        """
        from time import sleep
        job_details = self.execute_model(inputs, time_limit)
        sleep(0.5)  # Give a little time for the job to start
        job_details = self.monitor_execution(job_details, max_run_time)
        self.extract_solution(job_details)
        return job_details

    #                 self.cleanup()

    def get_solve_payload(self, inputs, time_limit):
        input_data = [{"id": f"{table_name}.csv", "values": df} for table_name, df in inputs.items()]
        output_data = [{"id": ".*\.csv"}]
        solve_payload = {self.client.deployments.DecisionOptimizationMetaNames.INPUT_DATA: input_data,
                         self.client.deployments.DecisionOptimizationMetaNames.OUTPUT_DATA: output_data,
                         self.client.deployments.DecisionOptimizationMetaNames.SOLVE_PARAMETERS:
                             {"oaas.timeLimit": time_limit,
                              "oaas.logTailEnabled": "true",
                              "oaas.logLimit": 10000,
                              "oaas.logAttachmentName": 'log.txt'}}
        print(f"Time-limit = {time_limit}")
        return solve_payload

    def execute_model(self, inputs, time_limit):
        solve_payload = self.get_solve_payload(inputs, time_limit)
        job_details = self.client.deployments.create_job(self.deployment_uid, solve_payload)
        return job_details

    def monitor_execution(self, job_details, max_run_time):
        """Monitor the model execution by periodically calling the API to get the current execution status.
        Result stored in self.execution_status_json and self.execution_status.

        TODO: Time-out?
        TODO: control the loop delay?
        """
        import time
        # from time import sleep
        start_time = time.time()  # in seconds
        # your code
        elapsed_time = 0
        job_uid = self.client.deployments.get_job_uid(job_details)
        job_status = DeployedDOModel.get_job_status(job_details)
        while job_status not in ['completed', 'failed', 'canceled']:
            print(f"{job_status}.... run-time={elapsed_time:.1f}")
            time.sleep(5)
            job_details = self.client.deployments.get_job_details(job_uid)
            job_status = DeployedDOModel.get_job_status(job_details)
            elapsed_time = time.time() - start_time
            if elapsed_time > max_run_time:
                self.client.deployments.delete_job(job_uid, hard_delete=True)
                print(f"Job deleted due to run-time exceeding maximum limit of {max_run_time} seconds")
                self.solve_status = 'JOB DELETED'
                break

        self.run_time = elapsed_time
        print(job_status)
        return job_details

    @staticmethod
    def get_job_status(job_details):
        """Job states can be : queued, running, completed, failed, canceled."""
        return job_details['entity']['decision_optimization']['status']['state']

    def extract_solution(self, job_details):
        self.job_details = job_details
        job_status = DeployedDOModel.get_job_status(job_details)
        if job_status == 'completed':
            self.solve_status = self.get_solve_status(job_details)
            self.objective = self.get_solve_details_objective(job_details)
            self.outputs = self.get_outputs(job_details)
            self.solve_details = self.get_solve_details(job_details)


    @staticmethod
    def get_outputs(job_details):
        outputs = {}
        for output_table in job_details['entity']['decision_optimization']['output_data']:
            table_name = output_table['id'][:-4]  # strips the '.csv'
            df = pd.DataFrame(output_table['values'], columns=output_table['fields'])
            outputs[table_name] = df
        return outputs

    @staticmethod
    def get_solve_status(job_details):
        """After job has completed"""
        return job_details['entity']['decision_optimization']['solve_state']['solve_status']

    @staticmethod
    def get_solve_details(job_details):
        """After job has completed"""
        return job_details['entity']['decision_optimization']['solve_state']['details']

    @staticmethod
    def get_solve_details_objective(job_details):
        """After job has completed"""
        return job_details['entity']['decision_optimization']['solve_state']['details']['PROGRESS_BEST_OBJECTIVE']





