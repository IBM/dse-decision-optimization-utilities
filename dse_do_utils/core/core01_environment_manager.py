import enum
import logging
import os
from os import environ
from typing import Dict, Optional, List


# from dse_do_dashboard.dash_app import HostEnvironment


class HostEnvironment(enum.IntEnum):
    """
    TODO: this HostEnvironment needs to match the from dse_do_dashboard.dash_app import HostEnvironment
    However, we should avoid circular dependencies
    """
    Local = 1
    CPD402 = 2  


class Core01EnvironmentManager():
    def __init__(self, db_connection: str, default_schema: str,
                 project_root: Optional[str] = None, data_directory: Optional[str] = None,
                 log_level: Optional[str] = None,
                 log_scope: Optional[List[str]] = None):
        if log_scope is None:
            log_scope = ['']  # Implies the root logger. If you don't want logger, specify log_scope as an empty list
        self.db_connection = db_connection
        self.default_schema = default_schema
        self.project_root = project_root
        self.data_directory = data_directory
        self.log_level = log_level
        if log_level is not None:
            self.set_loggers(level=log_level, scope=log_scope)

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

    def get_host_environment(self) -> HostEnvironment:
        """Detect the host environment, i.e. CP4D or Local workstation.
        Can also be done by detecting linux: `if system().lower() == 'linux'`
        Need to check if this works properly for current cluster version
        TODO: this HostEnvironment needs to match the from dse_do_dashboard.dash_app import HostEnvironment
        Tis needs to be replaced in the dse_do_dashboard.dash_app using the dse_do_utils.scenariomanager.Platform
        """
        if 'PROJECT_NAME' in environ:   # This works in CP4D v4.0.2
            host_env = HostEnvironment.CPD402
        else:
            host_env = HostEnvironment.Local
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
            host_env = self.get_host_environment()
            if host_env == HostEnvironment.Local:
                if self.project_root:
                    local_data_directory = os.path.join(self.project_root, 'assets', 'data_asset')
                else:
                    print("Error: for local use, specify the project_root")
                    local_data_directory = None
            else:
                local_data_directory = None
        return local_data_directory

    # def set_root_logger(self, level: str = 'DEBUG'):
    #     """Sets the properties of the root logger.
    #     In subsequent code, use `logger = logging.getLogger()`.
    #     Valid values for level = [CRITICAL, ERROR, WARNING, INFO, DEBUG]
    #     """
    #     logger = logging.getLogger()
    #     logger.setLevel(level)
    #     c_handler = logging.StreamHandler()
    #     c_handler.setLevel(level)
    #
    #     # Create formatters and add it to handlers
    #     c_format = logging.Formatter('%(asctime)s %(levelname)s: %(module)s.%(funcName)s - %(message)s')
    #     c_handler.setFormatter(c_format)
    #
    #     # Add handlers to the logger
    #     logger.addHandler(c_handler)

    def set_loggers(self, level: str = 'DEBUG', scope: Optional[List[str]] = None):
        """Sets the properties of loggers.
        Typically, log messages are created by `logger = logging.getLogger(__name__)`.
        Valid values for level = [CRITICAL, ERROR, WARNING, INFO, DEBUG]
        scope is a list of logger names for which we add handlers and the log-level
        An empty string is the root logger.
        Logger names use a hierarchical name space.
        In the dse_do_utils, grabbing logging.getLogger(__name__) woyuld have a name like `dse_do_utils.xxxxx.yyyy`
        Messages are propagated up in the hierarchy, so we can set properties of the logger named `dse_do_utils`.
        If you use a custom package that has classes subclassing from dse_do_utils, use a list like
        ['fruit', 'ds_do_utils'] to receive all log messages.
        If scope is None, the root hanlder is added. If you don't want logger, specify log_scope as an empty list
        The default sets the properties of the root logger.
        This will mean that messages from other packages, like docplex, will be included in the log
        """
        if scope is None:
            scope = ['']  # Implies the root logger. If you don't want logger, specify log_scope as an empty list
        c_handler = logging.StreamHandler()
        # c_handler.setLevel(level)

        # Create formatters and add it to handlers
        c_format = logging.Formatter('%(asctime)s %(levelname)s: %(module)s.%(funcName)s - %(message)s')
        c_handler.setFormatter(c_format)

        if scope is not None:
            for logger_name in scope: # e.g. ['fruit', 'dse_do_utils']:
                logger = logging.getLogger(logger_name)
                logger.setLevel(level)

                # Remove all existing handlers (See https://stackoverflow.com/questions/7484454/removing-handlers-from-pythons-logging-loggers)
                while logger.hasHandlers():
                    logger.removeHandler(logger.handlers[0])
                logger.addHandler(c_handler)
