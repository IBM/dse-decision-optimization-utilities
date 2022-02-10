# Copyright IBM All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

# -----------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------
# OptimizationEngine
# -----------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------
import docplex
import pandas as pd
import os
from docplex.mp.conflict_refiner import ConflictRefiner
from docplex.mp.progress import SolutionListener
from docplex.mp.model import Model
from typing import Sequence, List, Dict, Tuple, Optional

# from dse_do_utils import ScenarioManager
# Note that when in a package, we need to import from another modules in this package slightly differently (with the dot)
# Also, for DO in CPD25, we need to add scenariomanager as an added Python file and import as plain module
from docplex.mp.vartype import IntegerVarType, ContinuousVarType, BinaryVarType

try:
    # Import as part of package
    from .scenariomanager import ScenarioManager
    from .datamanager import DataManager
except:
    # import as part of DO Model Builder
    from scenariomanager import ScenarioManager
    from datamanager import DataManager


class OptimizationEngine(object):
    def __init__(self, data_manager: Optional[DataManager] = None, name: str = "MyOptimizationEngine"):
        self.mdl: Model = Model(name=name)
        self.dm = data_manager

    def integer_var_series(self, df: pd.DataFrame, **kargs) -> pd.Series:
        """Create a Series of integer dvar for each row in the DF. Most effective method. Best practice.
        Result can be assigned to a column of the df.
        Usage:
        df['xDVar'] = mdl.integer_var_series(df, name = 'xDVar')

        Args:
            self (docplex.mp.model): CPLEX Model
            df (DataFrame): dataframe
            **kargs: arguments passed to mdl.integer_var_list method. E.g. 'name'

        Returns:
            (pandas.Series) with integer dvars (IntegerVarType), index matches index of df
        """
        # We are re-using the index from the DF index:
        return OptimizationEngine.integer_var_series_s(self.mdl, df, **kargs)
        # return pd.Series(self.mdl.integer_var_list(df.index, **kargs), index = df.index)

    def continuous_var_series(self, df, **kargs) -> pd.Series:
        """Returns pd.Series[ContinuousVarType]"""
        return OptimizationEngine.continuous_var_series_s(self.mdl, df, **kargs)
        # return pd.Series(self.mdl.continuous_var_list(df.index, **kargs), index = df.index)

    def binary_var_series(self, df, **kargs) -> pd.Series:
        """Returns pd.Series[BinaryVarType]"""
        return OptimizationEngine.binary_var_series_s(self.mdl, df, **kargs)
        # return pd.Series(self.mdl.binary_var_list(df.index, **kargs), index = df.index)

    @staticmethod
    def integer_var_series_s(mdl: docplex.mp.model, df: pd.DataFrame, **kargs) -> pd.Series:
        """Returns pd.Series[IntegerVarType]"""
        return pd.Series(mdl.integer_var_list(df.index, **kargs), index=df.index)

    @staticmethod
    def continuous_var_series_s(mdl: docplex.mp.model, df: pd.DataFrame, **kargs) -> pd.Series:
        """Returns pd.Series[ContinuousVarType]."""
        return pd.Series(mdl.continuous_var_list(df.index, **kargs), index=df.index)

    @staticmethod
    def binary_var_series_s(mdl: docplex.mp.model, df: pd.DataFrame, **kargs) -> pd.Series:
        """Returns pd.Series[BinaryVarType]"""
        return pd.Series(mdl.binary_var_list(df.index, **kargs), index=df.index)

    def solve(self, refine_conflict: bool = False, **kwargs) -> docplex.mp.solution.SolveSolution:
        msol = self.mdl.solve(**kwargs)  # log_output=True
        if msol is not None:
            print('Found a solution')
            self.mdl.report()
            self.mdl.print_solution()
        else:
            print('No solution')
            if refine_conflict:
                print('Conflict Refiner:')
                crefiner = ConflictRefiner()  # Create an instance of the ConflictRefiner
                conflicts = crefiner.refine_conflict(self.mdl)  # Run the conflict refiner
                # ConflictRefiner.display_conflicts(conflicts) #Display the results
                for c in conflicts:
                    print(
                        c.element)  # Display conflict result in a little more compact format than ConflictRefiner.display_conflicts
        return msol

    def get_kpi_output_table(self) -> pd.DataFrame:
        all_kpis = [(kp.name, kp.compute()) for kp in self.mdl.iter_kpis()]
        df_kpis = pd.DataFrame(all_kpis, columns=['NAME', 'VALUE'])
        return df_kpis

    def export_as_lp(self, local_root: Optional[str] = None, copy_to_csv: bool = False) -> str:
        """Export .lp file of model in the 'DSX_PROJECT_DIR.datasets' folder.
        Convenience method.
        It can write a copy as a .csv file, so it can be exported to a local machine.
        If not in DSX, it will write to the local file system in the 'local_root/datasets' directory.
        Lp-filename is based on the mdl.name.

        Args:
            local_root (str): name of local directory. Will write .lp file here, if not in DSX
            copy_to_csv (bool): DEPRECATED. If true, will create a copy of the file with the extension `.csv`.
        Returns:
            path (str) path to lp file
        Raises:
            ValueError if root directory can't be established.
        """
        return OptimizationEngine.export_as_lp_s(self.mdl, local_root=local_root, copy_to_csv=copy_to_csv)

    def export_as_cpo(self, local_root: Optional[str] = None, copy_to_csv: bool = False):
        """Export .cpo file of model in the 'DSX_PROJECT_DIR.datasets' folder.
        It can write a copy as a .csv file, so it can be exported to a local machine.
        If not in DSX, it will write to the local file system in the 'local_root/datasets' directory.
        Convenience method.
        Cpo-filename is based on the mdl.name.

        Args:
            local_root (str): name of local directory. Will write .lp file here, if not in DSX
            copy_to_csv (bool):  DEPRECATED. If true, will create a copy of the file with the extension `.csv`.
        Returns:
            path (str) path to cpo file
        Raises:
            ValueError if root directory can't be established.
        """
        return OptimizationEngine.export_as_cpo_s(self.mdl, local_root=local_root, copy_to_csv=copy_to_csv)

    @staticmethod
    def export_as_lp_s(model, model_name: Optional[str] = None, local_root: Optional[str] = None, copy_to_csv: bool = False) -> str:
        """Export .lp file of model in the 'DSX_PROJECT_DIR.datasets' folder.
        It can write a copy as a .csv file, so it can be exported to a local machine.
        If not in WSL, it will write to the local file system in the 'local_root/datasets' directory.

        Args:
            model (docplex.mp.model): The CPLEX model to be exported
            model_name (str): name of .lp file. If none specified, will use the model.name.
                Specify if the model.name is not a valid file-name.
            local_root (str): name of local directory. Will write .lp file here, if not in WSL
            copy_to_csv (bool): DEPRECATED. If true, will create a copy of the file with the extension `.csv`.
        Returns:
            path (str) path to lp file
        Raises:
            ValueError if root directory can't be established.
        """
        # Get model name:
        if model_name is None:
            model_name = model.name
        # Get root directory:
        sm = ScenarioManager(local_root=local_root)  # Just to call the get_root_directory()
        # root_dir = sm.get_root_directory()
        datasets_dir = sm.get_data_directory()
        # Write regular lp-file:
        # lp_file_name_1 = os.path.join(root_dir, 'datasets', model_name + '.lp')
        lp_file_name_1 = os.path.join(datasets_dir, model_name + '.lp')
        model.export_as_lp(lp_file_name_1)  # Writes the .lp file

        ScenarioManager.add_file_as_data_asset_s(lp_file_name_1, model_name + '.lp')

        # platform = ScenarioManager.detect_platform()
        # if platform == platform.CPD40:
        #     ScenarioManager.add_data_file_using_ws_lib_s(lp_file_name_1)
        # if platform == platform.CPD25:
        #     ScenarioManager.add_data_file_to_project_s(lp_file_name_1, model_name + '.lp')
        # # Copy to csv (Not supported in CPD25. Not necessary.):
        # elif copy_to_csv:
        #     # lp_file_name_2 = os.path.join(root_dir, 'datasets', model_name + '_to_csv.lp')
        #     # csv_file_name_2 = os.path.join(root_dir, 'datasets', model_name + '_lp.csv')
        #     lp_file_name_2 = os.path.join(datasets_dir, model_name + '_to_csv.lp')
        #     csv_file_name_2 = os.path.join(datasets_dir, model_name + '_lp.csv')
        #     model.export_as_lp(lp_file_name_2)
        #     os.rename(lp_file_name_2, csv_file_name_2)
        # Return
        return lp_file_name_1

    @staticmethod
    def export_as_cpo_s(model, model_name: Optional[str] = None, local_root: Optional[str] = None, copy_to_csv: bool = False, **kwargs) -> str:
        """Export .cpo file of model in the 'DSX_PROJECT_DIR.datasets' folder.
        It can write a copy as a .csv file, so it can be exported to a local machine.
        If not in DSX, it will write to the local file system in the 'local_root/datasets' directory.

        Args:
            model (docplex.cp.model): The CPLEX model to be exported
            model_name (str): name of .lp file. If none specified, will use the model.name.
                Specify if the model.name is not a valid file-name.
            local_root (str): name of local directory. Will write .lp file here, if not in DSX
            copy_to_csv (bool): If true, will create a copy of the file with the extension `.csv`.
            **kwargs: Passed to model.export_model
        Returns:
            path (str) path to cpo file
        Raises:
            ValueError if root directory can't be established.
        """
        # Get model name:
        if model_name is None:
            model_name = model.name
        # Get root directory:
        sm = ScenarioManager(local_root=local_root)  # Just to call the get_root_directory()
        # root_dir = sm.get_root_directory()
        datasets_dir = sm.get_data_directory()
        # Write regular cpo-file:
        cpo_file_name_1 = os.path.join(datasets_dir, model_name + '.cpo')
        model.export_model(cpo_file_name_1)  # Writes the .cpo file
        # Copy to csv
        if copy_to_csv:
            cpo_file_name_2 = os.path.join(datasets_dir, model_name + '_to_csv.cpo')
            csv_file_name_2 = os.path.join(datasets_dir, model_name + '_cpo.csv')
            model.export_as_lp(cpo_file_name_2)
            os.rename(cpo_file_name_2, csv_file_name_2)
        # Return
        return cpo_file_name_1

    def add_mip_progress_kpis(self, mip_gap_kpi_name="Gap", solve_time_kpi_name="Solve Time",
                              best_bound_kpi_name="Best Bound", solution_count_kpi_name="Solution Count",
                              solve_phase_kpi_name="Solve Phase"):
        """Adds 5 KPIs to the self.mdl: 'Gap', 'Solve Time', 'Best Bound', 'Solution Count', 'Solve Phase'.

        Args:
            mip_gap_kpi_name (str):
            solve_time_kpi_name (str):
            best_bound_kpi_name (str):
            solution_count_kpi_name (str):
            solve_phase_kpi_name (str):

        Returns:

        """
        mdl = self.mdl
        mdl.progress_listener = MyProgressListener(mdl)
        mdl.add_progress_listener(mdl.progress_listener)
        if mip_gap_kpi_name is not None:
            mdl.add_kpi(lambda mdl, sol: mdl.progress_listener.mip_gap, mip_gap_kpi_name)
        if solve_time_kpi_name is not None:
            mdl.add_kpi(lambda mdl, sol: mdl.progress_listener.solve_time, solve_time_kpi_name)
        if best_bound_kpi_name is not None:
            mdl.add_kpi(lambda mdl, sol: mdl.progress_listener.best_bound, best_bound_kpi_name)
        if solution_count_kpi_name is not None:
            mdl.add_kpi(lambda mdl, sol: mdl.progress_listener.solution_count, solution_count_kpi_name)
        if solve_phase_kpi_name is not None:
            mdl.add_kpi(lambda mdl, sol: mdl.progress_listener.solve_phase, solve_phase_kpi_name)


    ################################################
    # MyProgress Listener
    ################################################


class MyProgressListener(SolutionListener):
    def __init__(self, mdl: docplex.mp.model):
        SolutionListener.__init__(self, mdl)
        self.solution_count = 0
        self.mip_gap = 0
        self.best_bound = 0
        self.solve_time = 0
        self.solve_phase = 0
        self.my_model = mdl

    def notify_progress(self, progress_data):
        self.solution_count += 1
        self.best_bound = progress_data.best_bound
        self.mip_gap = progress_data.mip_gap
        self.solve_time = progress_data.time
        try:
            self.solve_phase = self.my_model.solve_phase
        except AttributeError:
            pass
        # self.my_model.outputs = self.post_process()
