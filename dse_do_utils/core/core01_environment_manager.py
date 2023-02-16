import os
from os import environ
from typing import Dict

from dse_do_utils.scenariomanager import Platform
# from dse_do_dashboard.dash_app import HostEnvironment


class Core01EnvironmentManager():
    def __init__(self, db_connection: str = "", default_schema: str = 'DEFAULT_SCHEMA', project_root: str = None, data_directory: str = None):
        self.db_connection = db_connection
        self.default_schema = default_schema
        self.project_root = project_root
        self.data_directory = data_directory

    def get_project_db_credentials(self, db_connection_name: str = None) -> Dict:
        """Get DB credentials.
        If on CPD, get via connection
        If on local workstation, get via environment variables. Make sure you have a .env file."""
        if db_connection_name is None:
            db_connection_name = self.db_connection
        # print(f"db_connection = {db_connection}")
        try:
            # from ibm_watson_studio_lib import access_project_or_space
            # wslib = access_project_or_space()
            # db_credentials = wslib.get_connection(db_connection_name)
            db_credentials = self._get_project_db_credentials_from_cpd(db_connection_name)
            print(f"Retrieved DB connection {db_connection_name} from CPD")
        except:
            try:
                db_credentials = self._get_project_db_credentials_from_secrets(db_connection_name)
                print(f"Retrieved DB connection {db_connection_name} from my_secrets")
            except:
                # from dotenv import load_dotenv
                # load_dotenv()
                # db_credentials = {}
                # db_credentials['host'] = environ.get('DB_HOST')
                # db_credentials['port'] = environ.get('DB_PORT')
                # db_credentials['database'] = environ.get('DATABASE')
                # db_credentials['username'] = environ.get('DB_USER')
                # db_credentials['password'] = environ.get('DB_PASSWORD')
                # db_credentials['ssl'] = environ.get('DB_SSL')
                db_credentials = self._get_project_db_credentials_from_env(db_connection_name)
                print(f"Retrieved DB connection {db_connection_name} from .env")

        return db_credentials

    def _get_project_db_credentials_from_cpd(self, db_connection_name: str):
        """Get credentials from CPD"""
        from ibm_watson_studio_lib import access_project_or_space
        wslib = access_project_or_space()
        db_credentials = wslib.get_connection(db_connection_name)
        return db_credentials

    def _get_project_db_credentials_from_secrets(self, db_connection_name: str):
        """Get credentials from the local secrets module"""
        from my_secrets import get_db_connection
        db_credentials = get_db_connection(db_connection_name)
        return db_credentials

    def _get_project_db_credentials_from_env(self, db_connection_name: str):
        """Get credentials from .env"""
        from dotenv import load_dotenv
        load_dotenv()
        db_credentials = {}
        db_credentials['host'] = environ.get('DB_HOST')
        db_credentials['port'] = environ.get('DB_PORT')
        db_credentials['database'] = environ.get('DATABASE')
        db_credentials['username'] = environ.get('DB_USER')
        db_credentials['password'] = environ.get('DB_PASSWORD')
        db_credentials['ssl'] = environ.get('DB_SSL')
        return db_credentials

    # def get_host_environment(self) -> HostEnvironment:
    #     """Detect the host environment, i.e. CP4D or Local workstation.
    #     Can also be done by detecting linux: `if system().lower() == 'linux'`
    #     Need to check if this works properly for current cluster version
    #     """
    #     if 'PROJECT_NAME' in environ:   # This works in CP4D v4.0.2
    #         host_env = HostEnvironment.CPD402
    #     else:
    #         host_env = HostEnvironment.Local
    #     return host_env


    def get_host_platform(self) -> Platform:
        """Detect the host environment, i.e. CP4D or Local workstation.
        Can also be done by detecting linux: `if system().lower() == 'linux'`
        Need to check if this works properly for current cluster version
        """
        if 'PROJECT_NAME' in environ:   # This works in CP4D v4.0.2
            host_env = Platform.CPD40
        else:
            host_env = Platform.Local
        return host_env

    def get_schema(self) -> str:
        try:
            from dotenv import load_dotenv
            load_dotenv()
            schema = environ.get('SCHEMA', self.default_schema)
        except:
            schema = self.default_schema
        return schema

    def get_data_directory(self):
        if self.data_directory:
            local_data_directory = self.data_directory
        else:
            host_env = self.get_host_platform()
            if host_env == Platform.Local:
                if self.project_root:
                    local_data_directory = os.path.join(self.project_root, 'assets', 'data_asset')
                else:
                    print("Error: for local use, specify the project_root")
                    local_data_directory = None
            else:
                local_data_directory = None
        return local_data_directory
