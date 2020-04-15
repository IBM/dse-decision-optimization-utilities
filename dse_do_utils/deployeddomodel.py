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




import requests
import json
import pandas as pd
import sys

class DeployedDOModel_CPD21(object):
    """
    Note: the deployment in CPDv2.5 has completely changed. This class is NOT compatible with CPDv2.5.

    Major steps:
    1. Create an instance of a DeployedDOModel, configuring parameters (e.g. the URL and access token)

    Internally, the processes uses GETs to communicate with the deployed model:

    1. Get configuration data from the service (:meth:`~DeployedDOModel.retrieve_solve_configuration`). This will give a URL to start a job. (`self.solve_config_json`)
    2. Start the solve job. Returns info/urls to monitor the running job. (`self.job_config_json`)
    3. Monitor the running solve job. Runs in a loop, updates the current state. (`self.execution_status_json`)
    4. Once the job completes, get the optimization result.
    5. Clean-up the resources


    In the code::

        mdl.solve():
            self.retrieve_solve_configuration()
            self.set_output_settings_in_solve_configuration()
            self.execute_model()
            self.monitor_execution()
            self.retrieve_debug_materials()
            self.cleanup()


    Note on InsecureRequestWarning
    If the option `verify=False` is being used for REST calls, the following warning is generated (for each REST API call):
    ```
    InsecureRequestWarning: Unverified HTTPS request is being made. Adding certificate verification is strongly advised. See: https://urllib3.readthedocs.io/en/latest/advanced-usage.html#ssl-warnings
    InsecureRequestWarning)
    ```
    With the option suppress_warnings=True, all warnings in the mdl.solve() API are suppressed/ignored

    TODOs:

    1. Turning the option to False doesn't work, i.e. skipping parameter `oaas.dumpZipName` will result in no attachments!
    Work-around for now is to always add this option, let the server generate the dump and log file, but not download the zip and log files if debug = False
    And always cleanup after.
    3. Test kill and stop methods

    """

    def __init__(self, url=None, server=None, route=None, service_name=None, model_name=None, token=None, inputs=None,
                 attachment_type='CONTAINER', suppress_warnings=True, debug=False, debug_file_dir='../datasets', log_file_name='log.txt'):
        """Initialize the interface object.

        Usage::

            # Specifying url in parts (do not specify the `url`):
            mdl = DeployedDOModel(token=token, inputs=inputs, server=server, route=route, service_name=service_name, model_name=model_name, attachment_type=attachment_type, debug=debug, debug_file_dir=debug_file_dir, log_file_name=log_file_name)
            # Specifying url in one string (do not specify the `server`, `route`, etc):
            mdl = DeployedDOModel(url=url, token=token, inputs=inputs, attachment_type=attachment_type, debug=debug, debug_file_dir=debug_file_dir, log_file_name=log_file_name)
            # Simplest, using all default options:
            mdl = DeployedDOModel(url=url, token=token, inputs=inputs)
            mdl.solve()
            print("Solve status: {}".format(mdl.get_solve_status()))
            print("Objective: {}".format(mdl.get_objective()))
            print("Output tables: {}".format(mdl.outputs.keys()))
            print("Debug file name: {}".format(mdl.get_debug_dump_name_and_url()[0]))
            print("Log file name: {}".format(mdl.get_log_file_name_and_url()[0]))


        Either provide the full url, or all of server, route, service_name and model_name.

        Args:
            url (str): full URL of the execution service. If specified, the values for server, route, service_name and model_name are ignored.
            server (str): name of server
            route (str): route
            service_name (str): name of service
            model_name (str): name of deployed model
            token (str): deployment token
            inputs (dict of DataFrames): input tables
            attachment_type (str): 'CONTAINER' or 'INLINE_TABLE', default = 'CONTAINER'
            suppress_warnings (bool): if True, all warnings, in particular the InsecureRequestWarning will be suppressed
            debug (bool): if True, will fetch the dump<>.zip file and write into the datasets folder. (Currently the option `False` is not working and causes no output!)
            debug_file_dir (str): Path for `dump<>.zip` file and the `log.txt` file
            log_file_name (str): Name of log file

        """

        # Inputs
        self.url = url
        self.server = server
        self.route = route
        self.service_name = service_name
        self.model_name = model_name
        self.execution_token = token
        self.inputs = inputs
        self.attachment_type = attachment_type
        self.suppress_warnings = suppress_warnings
        self.debug = debug
        self.debug_file_dir = debug_file_dir
        self.log_file_name = log_file_name

        # State:
        self.service_configuration_json = None  # Available after `retrieve_solve_configuration`
        self.solve_config_json = None
        self.solve_config = None  # Will be manipulated and used as input for job execution
        # self.job_configuration_json = None
        self.job_config_json = None  # Available after `execute_model`
        self.execution_status_json = None  # Available after `monitor_execution` has been able to get the first update from the running job. Will be updated while the job is running.
        self.execution_status = None  # Available after `monitor_execution`
        self.solve_state = None  # Retrieved after successful run, from execution_status_json
        self.solve_details = None   # Retrieved after successful run, from execution_status_json
        self.solution_json = None  # Will contain the solution json, if the model run was successful
        self.outputs = {}

    ##################################################################################################
    # Getters
    ##################################################################################################
    def get_headers(self):
        return {"Authorization": self.execution_token}

    def get_execution_service_model_url(self):
        """Return the URL for the first call to the optimization service. Retrieves the service_configuration_json
        """
        if self.url is None:
            execution_service_model_url = "https://{}/dsvc/v1/{}/domodel/{}/model/{}".format(self.server, self.route,
                                                                                             self.service_name,
                                                                                             self.model_name)
        else:
            execution_service_model_url = self.url
        return execution_service_model_url

    #     def get_execution_service_url(self):
    #         return "https://{}/dsvc/v1/{}/domodel/{}".format(self.server, self.route, self.service_name)

    def get_solve_url(self):
        """Return the URL to start the execution of the solve job.
        Can only be called after the call to `retrieve_solve_configuration`
        """
        url = None
        if self.solve_config_json is not None:
            url = [x['uri'] for x in self.solve_config_json['deploymentDescription']['links'] if x['target'] == 'solve'][0]
        return url

    def get_solve_config(self):
        """Return the current solve_config.
        Note that the self.solve_config will e first set after the `retrieve_solve_configuration`.
        Next, it will be manipulated to add debugging information.
        Can only be called after the call to `retrieve_solve_configuration`
        """
        #         solve_config = None
        #         if self.solve_config_json is not None:
        #             solve_config = self.solve_config_json['deploymentDescription']['solveConfig']
        return self.solve_config

    def get_job_url(self):
        """Return the URL of the running job.
        Will be called repeatedly while monitoring the execution of the job.
        Can only be called after the call to `execute_model`
        """
        url = None
        if self.job_config_json is not None:
            url = [x['href'] for x in self.job_config_json['links'] if x['rel'] == 'self'][0]
        return url

    def get_stop_job_url(self):
        """Return the URL to stop a running job.
        TODO: test
        Can only be called after the call to `execute_model`
        """
        url = None
        if self.job_config_json is not None:
            url = [x['href'] for x in self.job_config_json['links'] if x['rel'] == 'stop'][0]
        return url

    def get_kill_job_url(self):
        """Return the URL to kill a running job.
        TODO: test
        Can only be called after the call to `execute_model`
        """
        url = None
        if self.job_config_json is not None:
            url = [x['href'] for x in self.job_config_json['links'] if x['rel'] == 'kill'][0]
        return url

    def get_debug_file_url(self):
        """Return the URL of the debug file.
        To be used to retrieve the debug<>.zip file.
        Also used to clean-up the remote debug file.
        Is the self.debug_file_data_url minus the `/data` at the end
        """
        debug_file_url = None
        zip_name, url = self.get_debug_dump_name_and_url()
        if url is not None:
            debug_file_url = url[:-5]  # strip the '/data' from the end
        return debug_file_url

    def get_log_file_url(self):
        """Return the URL of the log file.
        To be used to retrieve the log file.
        Also used to clean-up the remote log file.
        """
        file_name, url = self.get_log_file_name_and_url()
        return url

    def get_execution_status(self):
        status = None
        if self.execution_status_json is not None:
            status = self.execution_status_json['solveState']['executionStatus']
        return status

    def get_objective(self):
        """Available after post process (both CONTAINER and INLINE_TABLE)"""
        objective = None
        if self.solution_json is not None:
            objective = self.solution_json['CPLEXSolution']['header']['objectiveValue']
        return objective

    def get_solve_status(self):
        """Available during and after the job monitoring. String with values 'NOT_STARTED', 'RUNNING', "PROCESSED", "FAILED", "INTERRUPTED", more? """
        status = None
        if self.solve_state is not None:
            status = self.solve_state['solveStatus']
        return status

    def get_solution_name_and_url(self):
        """Returns the name ('solution.json') and the URL of the solution data.
        This applies to both `CONTAINER` and `INLINE_TABLE` modes.
        """
        solution_name = None
        url = None
        if self.execution_status_json is not None:
            for o in self.execution_status_json['outputAttachments']:
                attachment_name = o['name']
                if attachment_name == 'solution.json':
                    solution_name = attachment_name
                    url = o['url']
        return solution_name, url

    def get_debug_dump_name_and_url(self):
        """Returns the name of the dump<>.zip file and the url to the data of the dump<>.zip file.
        Can be called after the first time the job monitor has retrieved the self.execution_status_json
        """
        zip_name = None
        url = None
        if self.execution_status_json is not None:
            for o in self.execution_status_json['outputAttachments']:
                if "dump_" in o['name']:
                    zip_name = o['name']
                    url = o['url']
        return zip_name, url

    def get_log_file_name_and_url(self):
        """Returns the name of the log.txt file and the url to the data.
        Can be called after the first time the job monitor has retrieved the self.execution_status_json
        """
        log_name = None
        url = None
        if self.execution_status_json is not None:
            for o in self.execution_status_json['outputAttachments']:
                if self.log_file_name == o['name']:
                    log_name = o['name']
                    url = o['url']
        return log_name, url

    ##################################################################################################
    # Main solve steps
    ##################################################################################################

    def solve(self):
        """Master routine. Initializes the job, starts the execution, monitors the results, post-processes the solution and cleans-up after.

        Calls the following methods (in order)::

            self.retrieve_solve_configuration()
            self.set_output_settings_in_solve_configuration()
            self.execute_model()
            self.monitor_execution()
            self.retrieve_debug_materials()
            self.cleanup()

        """
        from time import sleep
        import warnings
        with warnings.catch_warnings():
            # TODO: turn-off the ignore warning is NOT working
            if self.suppress_warnings:
                warnings.simplefilter("ignore")
            try:
                self.retrieve_solve_configuration()
                self.set_output_settings_in_solve_configuration()
                self.execute_model()
                sleep(0.5)  # Give a little time for the job to start
                self.monitor_execution()
                self.retrieve_debug_materials()  # Make sure to run this to get any debug_file_url. Should be run independently of how the job was terminated
            except Exception as e:
                print(e)
                import traceback
                traceback.print_exc()
                self.cleanup()

    def retrieve_solve_configuration(self):
        """Call REST API to GET the solve configuration. Result in self.solve_config_json
        """
        r = requests.get(self.get_execution_service_model_url(), headers=self.get_headers(), verify=False)
        self.solve_config_json = r.json()

    def set_output_settings_in_solve_configuration(self):
        """Updates the self.solve_config to define the required output and debug results
        """
        self.solve_config = self.solve_config_json['deploymentDescription']['solveConfig']

        # TODO: what will the option `"oaas.logStreaming":"false"` do in solveParameters? Create a log file?
        # TODO: if we can create a log file, we probably need to add it as an attachment?
        # Note: simply adding `"oaas.logStreaming":"false"` does NOT add an attachment.
        if self.debug:
            self.solve_config['solveParameters'] = {"oaas.dumpZipName": "", "oaas.logAttachmentName": self.log_file_name}
        else:
            # TODO/Bug: not adding the parameter `oaas.dumpZipName` will result in no attachments!
            # Work-around for now is to always add this option, but not download if debug = False
            # self.solve_config['solveParameters'] = {}
            self.solve_config['solveParameters'] = {"oaas.dumpZipName": "",
                                                    "oaas.logAttachmentName": self.log_file_name}
        if self.attachment_type == 'CONTAINER':
            self.solve_config['attachments'].append(
                {'category': 'output', 'type': 'CONTAINER', 'containerId': 'debug', 'name': '.*\\.zip'})  # Notebook
        elif self.attachment_type == 'INLINE_TABLE':
            self.solve_config['attachments'].append(
                {'category': 'output', 'type': 'INLINE_TABLE', 'name': '.*', })  # Alain

            #     print(self.get_solve_config())

    def execute_model(self):
        """Call REST API to start the solve of the model. Returns the execution data in self.execution_result.
        Contains urls to monitor, stop or kill the job
        """
        r = requests.post(self.get_solve_url(), files=self.get_input_files(), headers=self.get_headers(), verify=False)
        self.job_config_json = r.json()

    def stop_job(self):
        """Call REST API to stop the solve of the model.
        TODO: test
        """
        r = requests.post(self.get_stop_job_url(), headers=self.get_headers(), verify=False)
        # Note: the r has no json! Do not try r.json().

    def kill_job(self):
        """Call REST API to kill the solve of the model.
        TODO: test
        """
        r = requests.post(self.get_kill_job_url(), headers=self.get_headers(), verify=False)
        # Note: the r has no json! Do not try r.json().

    def get_input_files(self):
        """Return the inputs for submission to the job execution run.

        Challenge: the solve_config should be the first element in the self.files dict.
        Work-around: use an OrderedDict. Not sure of this always works, i.e. if the
        """
        import collections
        inputs = self.inputs
        files = collections.OrderedDict()
        files['solveconfig'] = json.dumps(self.get_solve_config())
        for i in inputs:
            files[i + '.csv'] = inputs[i].to_csv(index=False)
        return files

    def monitor_execution(self):
        """Monitor the model execution by periodically calling REST API to get the current execution status.
        Result stored in self.execution_status_json and self.execution_status.

        TODO: what are all possible values for execution_status? Are we stopping under the right conditions?
        TODO: stop if we get an unknown status?
        TODO: Time-out?
        TODO: control the loop delay?
        """
        from time import sleep
        while True:
            r = requests.get(self.get_job_url(), headers=self.get_headers(), verify=False)
            self.execution_status_json = r.json()
            self.execution_status = self.get_execution_status()  # Gets the status from self.execution_status_json
            #         status = self.execution_status_json['solveState']['executionStatus']
            #         self.status = status
            print("Execution status = {}".format(self.execution_status))
            if self.execution_status == "PROCESSED":
                self.post_process_processed()
                break
            elif self.execution_status == "FAILED":
                self.post_process_failed()
                break
            elif self.execution_status == "INTERRUPTED":
                self.post_process_interrupted()
                break
            sleep(1)

    def post_process_processed(self):
        """Post-process the succesfully completed solve job.
        Called when execution reached status 'PROCESSED'.
        """
        #     print(self.execution_status_json.keys())

        # solveState and solveDetails json is the same for types CONTAINER and INLINE_TABLE
        self.solve_state = self.execution_status_json['solveState']
        self.solve_details = self.execution_status_json['solveDetails']
        """
        Example of a solve_state:
        {u'workerVersionUsed': u'1.0-ws-v1.2.3.0-b33', u'updatedAt': 1551221728881, u'solveStatus': u'OPTIMAL_SOLUTION', 
        u'details': {u'PROGRESS_BEST_OBJECTIVE': u'10750.0', u'MODEL_DETAIL_KPIS': u'["Production Cost", "Backlog Cost"]', 
        u'MODEL_DETAIL_CONSTRAINTS': u'13', u'MODEL_DETAIL_INTEGER_VARS': u'36', u'PROGRESS_CURRENT_OBJECTIVE.history': 
        u'[[1551221728.67, 10750]]', u'MODEL_DETAIL_BOOLEAN_VARS': u'0', u'MODEL_DETAIL_TYPE': u'MILP', u'MODEL_DETAIL_CONTINUOUS_VARS': u'0', 
        u'PROGRESS_CURRENT_OBJECTIVE': u'10750', u'PROGRESS_GAP': u'0.0', u'MODEL_DETAIL_NONZEROS': u'72', u'KPI.Backlog Cost': u'1000', 
        u'KPI.Production Cost': u'9750'}, u'executionStatus': u'PROCESSED'}

        Example of a solve_details:
        {u'submittedAt': 1551221727825, u'endedAt': 1551221728881, u'endReportedAt': 1551221728918, u'systemDetails': 
        {u'worker.cores.total': u'4', u'worker.process.cpu.set': u'0-15', u'worker.process.peak.memory': u'120212', u'worker.cores.default': u'1', 
        u'worker.data.write.bytes': u'4266', u'worker.process.peak.swap': u'0', u'worker.processing.duration': u'943', u'worker.jms.write.chars': u'6439', 
        u'worker.heap.max': u'524288', u'worker.data.read.bytes': u'71234', u'worker.jms.write.duration': u'10', u'worker.data.read.duration': u'21', 
        u'worker.setup.duration': u'1', u'worker.log.write.duration': u'4', u'worker.data.write.duration': u'47', u'worker.log.write.chars': u'1300', 
        u'worker.heap.used': u'127181', u'worker.process.processing.duration': u'722', u'worker.process.max.memory': u'524288'}, 
        u'processorId': u'testdeploy2-domodel-prodplanningtrial2-55d9c8d7c8-89j25', u'startedAt': 1551221727914}
        """

        #     print("---solve details---")
        #     print(self.execution_status_json['solveDetails'])
        #     print("---solve state---")
        #     print(self.execution_status_json['solveState'])

        # Retrieve the solution.json:
        self.solution_json = self.retrieve_solution()

        # Get the output tables:
        if self.attachment_type == 'CONTAINER':
            self.post_process_container()
        elif self.attachment_type == 'INLINE_TABLE':
            self.post_process_inline_table()

    def post_process_container(self):
        """Post-process 'CONTAINER' type job.
        Called when execution reached status 'PROCESSED' and attachment_type='CONTAINER'.
        """
        #     print("post_process_container")
        #     print(self.execution_status_json.keys())
        #     for o in self.execution_status_json['outputAttachments']:
        #             print o['name'] + '  ' + o['url']

        self.outputs = {}
        for o in self.execution_status_json['outputAttachments']:
            attachment_name = o['name']
            data_url = o['url']
            if attachment_name[-4:] == '.csv':
                table_name = attachment_name[:-4]
                #             print(table_name)
                self.outputs[table_name] = self.post_process_container_get_dataframe(data_url)
            # elif attachment_name == 'solution.json':
            #      self.post_process_retrieve_solution(data_url)
            # elif "dump_" in attachment_name:
            #     #         elif attachment_name[-4:] == '.zip':
            #     self.retrieve_file(attachment_name, data_url)
            # elif self.log_file_name == attachment_name:
            #     self.retrieve_file(attachment_name, data_url)

    def post_process_inline_table(self):
        """Post-process 'INLINE_TABLE' type job.
        when execution reached status 'PROCESSED' and attachment_type='INLINE_TABLE'.

        In 'INLINE_TABLE' all output table data is already in the execution_status_json.
        This data is in the form of json (not in csv format like the 'CONTAINER' type).
        The solution data is not included and needs to be retrieved via a URL, just like with the 'CONTAINER' type.
        """
        #     print(self.execution_status_json.keys())

        #     print("post_process_inline_table")
        #     print(self.execution_status_json.keys())
        self.outputs = {}
        for o in self.execution_status_json['outputAttachments']:
            attachment_name = o['name']
            category = o['category']
            attachment_type = o['type']
            #         print(attachment_type)
            #         print(category)
            #         print(attachment_name)
            if category == 'output' and attachment_type == 'INLINE_TABLE':
                table = o['table']
                #             print(attachment_name)
                self.outputs[attachment_name] = self.post_process_inline_table_get_dataframe(table)
            # elif attachment_name == 'solution.json':
            #     # Note: the attachment_type == 'REST', which means the contents is a URL to get the solution, not the solution itself.
            #     data_url = o['url']
            #     self.post_process_retrieve_solution(data_url)
            #     #         elif attachment_name[-4:] == '.zip':
            # elif "dump_" in attachment_name:
            #     data_url = o['url']
            #     self.retrieve_file(attachment_name, data_url)
            #     pass

    def post_process_container_get_dataframe(self, data_url):
        """Call REST API to GET the data from a table attachment and load into a DataFrame.
        """
        if sys.version_info[0] < 3:
            from StringIO import StringIO
        else:
            from io import StringIO

        r = requests.get(data_url, headers=self.get_headers(), verify=False)
        df = pd.read_csv(StringIO(r.content))
        return df

    @staticmethod
    def post_process_inline_table_get_dataframe(table):
        """Converts the 'table' to a DataFrame.
        Applies to 'INLINE_TABLE' attachment type.

        table is a dict with 2 keys:
        1. name: string
        2. rows: list of dicts with 1 key: `values`: list of strings/integers/floats
        """

        """
        Example of a table:
        {u'name': u'kpis', 
         u'rows': [{u'values': [u'"NAME"', u'"VALUE"']},
        {u'values': [u'"Production Cost"', u'"9750"']},
        {u'values': [u'"Backlog Cost"', u'"1000"']}]}
        """

        if sys.version_info[0] < 3:
            from StringIO import StringIO
        else:
            from io import StringIO

        csv = StringIO()
        for row in table['rows']:
            line = ",".join(str(x) for x in row[
                'values'])  # Note: need to convert each value in the values row to a string, otherwise the join doesn't work
            csv.write(line + '\n')
            #         print("line = {}".format(line))
        csv.seek(
            0)  # Returns the pointer to the start of the file. If not, 'reading' the file will start at the end and return nothing.
        df = pd.read_csv(csv)
        return df

    def retrieve_solution(self):
        """Call REST API to retrieve the solution.json.

        Returns:

        """
        solution_json = None
        solution_name, url = self.get_solution_name_and_url()
        if url is not None:
            r = requests.get(url, headers=self.get_headers(), verify=False)
            obj = r.json()
            solution_json = obj
        return solution_json

    # def post_process_retrieve_solution(self, data_url):
    #     """Call REST API to GET the solution data.
    #     Called when execution reached status 'PROCESSED' and attachment_type='CONTAINER' or 'INLINE_TABLE'
    #     """
    #
    #     r = requests.get(data_url, headers=self.get_headers(), verify=False)
    #     obj = r.json()
    #     self.solution_json = obj
    #     #     self.objective = obj['CPLEXSolution']['header']['objectiveValue']
    #     #     print("Solution")
    #     #     print(obj)
    #     #     print('----------')
    #     #     print(obj['CPLEXSolution']['header'].keys())
    #     print("Objective = {}".format(obj['CPLEXSolution']['header']['objectiveValue']))

    def retrieve_debug_materials(self):
        """The dump zip and log files is saved in the self.debug_file_dir folder.
        This dump zip file can be used to create a new scenario. (Using the right-hand-side panel in the Model Builder, 'Create Scenario From file'.)
        """
        # Do not download the files if not in debug mode
        # This is a work-around for the bug that we always need to generate the dump file on the server, otherwise there are no output attachments.
        if not self.debug:
            return

        zip_name, url = self.get_debug_dump_name_and_url()
        if url is not None:
            self.retrieve_file(zip_name, url)

        log_name, url = self.get_log_file_name_and_url()
        if url is not None:
            self.retrieve_file(log_name, url)

    def retrieve_file(self, file_name, url):
        """Call REST API to GET the data of the file
        The file is saved in de debug folder.

        Can be used for the dump<>.zip file or the log.txt file
        This dump zip file can be used to create a new scenario (Using the right-hand-side panel in the Model Builder, 'Create Scenario From file')

        Note that if we get here, there exists a log or dump file on the deployed service. Make sure this gets cleaned up.
        """
        z = requests.get(url, headers=self.get_headers(), stream=True, verify=False)
        import os
        file_path = os.path.join(self.debug_file_dir, file_name)
        f = open(file_path, 'wb')
        # f = open('../datasets/' + zip_name, 'wb')
        for chunk in z.iter_content(chunk_size=512 * 1024):
            if chunk:
                f.write(chunk)
            f.close()


    # def retreive_debug_dump_zip(self, zip_name, url):
    #     """Call REST API to GET the data of the dump<>.zip file
    #     The dump zip file is saved in notebook folder.
    #     This dump zip file can be used to create a new scenario (Using the right-hand-side panel in the Model Builder, 'Create Scenario From file')
    #
    #     Make sure this is always run to get any debug file url (if it was generated), so we can clean it up.
    #     TODO: allow for configuration of whether debug file is retrieved.
    #     Note that if we get here, there exists a dump file on the deployed service. Make sure this gets cleaned up. Cleanup will happen if the self.debug_file_data_url is set.
    #     """
    #     # Store the url so we can clean it up later
    #     #     self.debug_file_data_url = url
    #
    #     #     print('zipName = {}'.format(zip_name))
    #     #     print('Debug Data URL = {}'.format(url))
    #     z = requests.get(url, headers=self.get_headers(), stream=True, verify=False)
    #     f = open('../datasets/' + zip_name, 'wb')
    #     for chunk in z.iter_content(chunk_size=512 * 1024):
    #         if chunk:
    #             f.write(chunk)
    #         f.close()

    def post_process_failed(self):
        """Called when execution reached status 'FAILED'.
        """
        print("Failure message: " + self.execution_status_json['solveState']['failureInfo']['message'])

    def post_process_interrupted(self):
        """Called when execution reached status 'INTERRUPTED'.
        """
        print("Interruption status: " + self.execution_status_json['solveState']['interruptionStatus'])

    def cleanup(self):
        """Call REST API to clean-up the job and, if applicable, the debug file.
        Delete the job from the execution service as well as the debug file from the "debug" container, to free space on the cluster.
        """
        # Clean-up the job:
        job_url = self.get_job_url()
        if job_url is not None:
            requests.delete(job_url, headers=self.get_headers(), verify=False)

        # Clean-up the dump file:
        debug_file_url = self.get_debug_file_url()
        if debug_file_url is not None:
            requests.delete(debug_file_url, headers=self.get_headers(), verify=False)

        # Clean-up the log file
        log_file_url = self.get_log_file_url()
        if log_file_url is not None:
            requests.delete(log_file_url, headers=self.get_headers(), verify=False)
