# Copyright IBM All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

# -----------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------
# DOModelExporter
# -----------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------

import requests
import urllib3
import os
from datetime import datetime
from typing import List

urllib3.disable_warnings(
    urllib3.exceptions.InsecureRequestWarning)  # Supresses the "InsecureRequestWarning: Unverified HTTPS request is being made" you get when downloading from a CPD cluster.


class DOModelExporter(object):
    """Exports a DO model from CPD2.5 using curl/web-requests.
    By default, the export files are stored as datetime-stamped zip files in the Data Assets of the project.

    Can be used in 4 ways:
    1. Typical: only specify a list of the DO Model names to export.
    2. Export from another project in same cluster.
    3. Export from another project in another cluster.
    4. Generates the full curl commands. Then copy and paste them into a terminal that supports curl.

    1. Typical use:
        Initialize the exporter with a list of DO Model names and call the method `me.export_do_models()'.
        Must be run in the same project and cluster.
        The DO Model export files are stored in the Data Assets of this project.::
        Uses naming pattern: `{do_model_name}_export_{YYYYMMDD_hhmm}.zip`

            me = DOModelExporter(do_model_names = ['Model1', 'Model2'])
            me.export_do_models()

    2. Export from another project in same cluster:
        Need to specify the `project_id`. See below for how to get the project_id.
        Assumes current user is a collaborator on the other project (if not use the next use-case)::

            me = DOModelExporter(do_model_names = ['ProductionPlanning'],
                     project_id = 'ef365b2c-9f28-447a-a933-5de6560a1cfa')
            me.export_do_models()

    3. Export from another project in other cluster:
        Specify access_toke=None, user_name, password and project_id.
        Will retrieve the accessToken from the user-name and password::

        me = DOModelExporter(cpd_cluster_host = 'https://dse-cp4d25-cluster4.cpolab.ibm.com',
                     access_token = None,
                     user_name = user_name,
                     password = password,
                     do_model_names = ['ProductionPlanning'],
                     project_id = 'b7bf7fd8-aa50-4bd2-8364-02ea6d480895')
        me.export_do_models()

    4. Generate curl commands:
        a. Initialize the exporter: `me = DOModelExporter(cluster_name, user_name, password, do_model_name, project_id)`
        b. Get the access-token curl command: me.get_access_token_curl(). Extract the access_token string.
        b. Get the export-do-model curl command: me.get_do_model_export_curl(do_model_name, access_token).

        me = DOModelExporter(do_model_names=[],
                     user_name = user_name,
                     password = password)
        me.get_access_token_curl()
        access_token = 'xxxxxx'  # Get value from running the above curl command
        me.get_do_model_export_curl('ProductionPlanning', access_token)

        Curl commands can be run for instance from the Git Bash terminal that is part of Git for Windows.

    5. How to get the `project_id`:
        a. If not specifying a project_id in the constructor, it will get it automatically using the environment variable: `os.environ['PROJECT_ID']`.
        b. Run the  `os.environ['PROJECT_ID']` in a notebook in the target project.
        c. Parse the project_id from the Page Source of a web page in the target project.
            i. Manually.
                1. From any web-page of the CPD project, show the `Page Source`. (In Firefox: menu -> Web Developer -> Page Source)
                2. Do a find-in-page of the name of the project (control-F).
                3. Just before the first instance of the project name, there is a field `data_id`, e.g.: `data-id="21c8ac71-26c1-49a5-a567-d4c69a0d8158"`. Copy the data_id value.
                * Beware that the Page Source may contain other project-names and projects-IDs, so search on the full project name.
            ii. Using the method `DOModelExporter.get_project_id(project_name, page_source)`

            page_source = 'the page source copied from Page Source'
            project_id = DOModelExporter.get_project_id('Full_Project_Name', page_source)

    6. How to get the access_token:
        a. If not provided (i.e. no entry in the constructor arguments), exporter uses the environment variable `os.environ['USER_ACCESS_TOKEN']`.
        b. Run the `os.environ['USER_ACCESS_TOKEN']` in a notebook in the target project.
        c. Specify `access_token=None` in the constructor arguments (this is NOT the same as specifying a None value!).
        And specify a user-name and password. Exporter will retrieve the accessToken by calling a web-API.

    7. How to get the cpd_cluster_host?
        a. If not provided, the exporter will use the environment variable `os.environ['RUNTIME_ENV_APSX_URL']`
        b. For remote clusters. Beware of the URL of the cluster! DSE clusters may use some alias (e.g. `dse-cp4d25-cluster4.datascienceelite.com`) that is NOT accessable when running from within the same cluster.<br>
        When running this from the same cluster, use the 'original' cluster name (e.g. `dse-cp4d25-cluster4.cpolab.ibm.com`).
    """

    def __init__(self, do_model_names: List[str], **kwargs):
        """Setup the exporter with all the data required for the export.

        Args:
            do_model_names (List[str]): names of DO models to be exported
            cpd_cluster_host (str, Optional): name of the cluster, e.g. 'https://dse-cp4d25-cluster4.cpolab.ibm.com'.Make sure to include the 'https://'.
            access_token (str, Optional): access token. If None, it will collect the access_token from the host using the user-name and password. Only applicable of retrieving DO model from remote host.
            user_name (str, Optional): user-name. Required if access_token is None.
            password (str, Optional): password. Required if access_token is None.
            project_id (str, Optional): project ID (see else)
            export_directory (str, Optional): name of directory to store file. If '/project_data/data_asset/', it will also add as WS Data Asset
        """
        self.do_model_names = do_model_names
        self.cpd_cluster_host = kwargs.get('cpd_cluster_host', os.environ['RUNTIME_ENV_APSX_URL'])
        self.project_id = kwargs.get('project_id', os.environ['PROJECT_ID'])
        self.access_token = kwargs.get('access_token', os.environ['USER_ACCESS_TOKEN'])
        self.user_name = kwargs.get('user_name', None)
        self.password = kwargs.get('password', None)
        # self.export_file_name = kwargs.get('export_file_name',
        #                                    f"{do_model_name}_export_{datetime.now().strftime('%Y%m%d_%H%M')}.zip")
        self.export_directory = kwargs.get('export_directory', '/project_data/data_asset/')

    def get_access_token_curl(self):
        """Return the curl command to retreive the accessToken.
        Based on the cluster_name, user_name and password.
        """
        curl_command = f"curl -k -X GET \
  {self.cpd_cluster_host}/v1/preauth/validateAuth \
  -H 'Accept: */*' \
  -H 'Accept-Encoding: gzip, deflate' \
  -u '{self.user_name}:{self.password}'"
        return curl_command

    def get_do_model_export_curl(self, do_model_name: str, access_token: str):
        """Return the curl command to retreive the accessToken.
        Based on the cluster_name, user_name and password.
        """
        export_file_name = DOModelExporter._get_export_file_name(do_model_name)
        curl_command = f"curl -k -v -X GET \
  '{self.cpd_cluster_host}/v2/decisions/{do_model_name}/archive?projectId={self.project_id}' \
  -H 'Accept: application/zip' \
  -H 'Authorization: Bearer {access_token}' \
  --output {export_file_name}"
        return curl_command

    @staticmethod
    def get_project_id(project_name: str, page_source: str) -> str:
        """Extracts the project ID from a page source.

        Args:
            project_name (str): full name of the project
            page_source (str): the page source of a page of the project in CPD
        Returns:
            project_id (str)

        """
        project_name_match = f">{project_name}</a>"
        project_name_start = page_source.find(project_name_match)
        if project_name_start == -1:
            print(f"Could not find project using '{project_name_match}'")
            project_id = None
        else:
            start_project_id = page_source.rfind('data-id=', 0, project_name_start) + 9
            end_project_id = page_source.find('"', start_project_id)
            project_id = page_source[start_project_id:end_project_id]
        return project_id

    def get_access_token_web(self):
        """Runs web request to get the personal access-token.
        Based on the cluster_name, user_name and password.
        Stores it in self.access_token
        """
        if self.user_name is None or self.password is None:
            print("User-name and password need to be specified in order to retrieve accessToken")
            return None

        headers = {
            'Accept': '*/*',
            'Accept-Encoding': 'gzip, deflate',
        }
        url = f'{self.cpd_cluster_host}/v1/preauth/validateAuth'
        response = requests.get(url, headers=headers, verify=False, auth=(self.user_name, self.password))
        if response.status_code == 200:
            print("Success retrieving accessToken.")
            self.access_token = response.json()['accessToken']
        elif response.status_code == 401:
            print("Error retrieving accessToken: {}".format(response.json()['message']))
            self.access_token = None
        else:
            print("Error retrieving accessToken. Status code = {}".format(response.status_code))
            self.access_token = None
        return response

    def get_do_model_export_web(self, do_model_name: str):
        """Runs web-request to get DO model export.
        Based on the cluster_name, access_token, do_model_name.
        Stores result as a Data Asset
        """
        headers = {
            'Accept': 'application/zip',
            'Authorization': 'Bearer {}'.format(self.access_token),
        }

        params = (
            ('projectId', self.project_id),
        )

        url = f"{self.cpd_cluster_host}/v2/decisions/{do_model_name}/archive"
        response = requests.get(url, headers=headers, params=params, verify=False)

        if response.status_code == 200:
            # Success
            print("Success downloading DO Model. Writing to file.")
            file_path = self.write_do_model_to_file(do_model_name, response)
            print(f"Exported DO model in {file_path}")

        elif response.status_code == 404:
            print("Error downloading DO Model: {}".format(response.json()['errors'][0]['message']))
        elif response.status_code == 400:
            print("Error downloading DO Model. Status code = {}. Check project_id.".format(response.status_code))
        else:
            print("Error downloading. Status code = {}".format(response.status_code))
        return response

    @staticmethod
    def _get_export_file_name(do_model_name: str):
        return f"{do_model_name}_export_{datetime.now().strftime('%Y%m%d_%H%M')}.zip"

    def write_do_model_to_file(self, do_model_name: str, response):
        import os
        export_file_name = DOModelExporter._get_export_file_name(do_model_name)
        file_path = os.path.join(self.export_directory, export_file_name)
        with open(file_path, 'wb') as f:
            f.write(response.content)
        # If CPD2.5 then also add as asset:
        if self.export_directory == '/project_data/data_asset/':
            print("Adding export file to Data Assets of this project.")
            with open(file_path, 'rb') as f:
                from project_lib import Project
                project = Project.access()
                project.save_data(file_name=export_file_name, data=f, overwrite=True)
        return file_path

    def export_do_models(self):
        """End-to-end run. Gets the access token and then the DO model export."""
        # If access_token is None, first retrieve it from the host using the un/pw. This should be the exception.
        if self.access_token is None:
            response = self.get_access_token_web()  # Sets access_token internally
        # Regular export DO model
        if self.access_token is not None:
            for do_model_name in self.do_model_names:
                self.get_do_model_export_web(do_model_name)
        else:
            print("AccessToken is None, not possible to export DO models.")
