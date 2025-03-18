# Copyright IBM Corp. 2021, 2022
# IBM Confidential Source Code Materials
# This Source Code is subject to the license and security terms contained in the License.txt file contained in this source code package.
import os
import pathlib
from abc import abstractmethod
from typing import Dict, List, Optional

import pandas as pd
from docplex import cp
from docplex.cp.solver.cpo_callback import CpoCallback
from docplex.mp.conflict_refiner import ConflictRefiner
from docplex.mp.solution import SolveSolution
from docplex.cp.parameters import CpoParameters
from docplex.cp.solution import CpoSolveResult, CpoRefineConflictResult

from dse_do_utils import OptimizationEngine
from dse_do_utils.core.core01_data_manager import Core01DataManager
from dse_do_utils.datamanager import Outputs
from typing import TypeVar, Generic

DM = TypeVar('DM', bound='Core01DataManager')


class Core01CpoOptimizationEngine(OptimizationEngine[DM]):
    """
    DRAFT. Needs a lot of updates to match CP Optimizer specifics!

    This class supports Python generics to specify the class of the DataManager.
    This allows an IDE like PyCharm and VSCode to check for methods and attributes
    and allows more easy navigation (i.e. control-click on name)

    Usage 1 - Define a use-case specific OptimizationEngine class::

        DM = TypeVar('DM', bound='FruitDataManager')
        class FruitOptimizationEngine(Core01OptimizationEngine[DM]):
            pass

    Usage 2 - When creating an instance::

        engine = FruitOptimizationEngine[FruitDataManager]
    """
    def __init__(self, data_manager: DM, name: str = None, solve_kwargs=None,
                 export_lp: bool = False, export_sav: bool = False, export_lp_path: str = '',
                 enable_refine_conflict: bool = False):
        super().__init__(data_manager=data_manager, name=name, is_cpo_model=True)

        if solve_kwargs is None:
            solve_kwargs = {"log_output": True}
        self.solve_kwargs = solve_kwargs
        self.export_lp = export_lp
        self.export_sav = export_sav
        self.export_lp_path = export_lp_path
        self.enable_refine_conflict = enable_refine_conflict
        self.logger = data_manager.logger

        self.cpo_params = CpoParameters()



    def run(self) -> Outputs:
        self.dm.prepare_data_frames()
        self.dm.pre_processing()

        self.create_dvars()
        self.create_objectives()
        self.set_objective()
        self.create_constraints()
        # self.set_cplex_parameters()
        self.set_cpo_parameters()
        msol = self.solve()
        if msol.is_solution():
            self.extract_solution(msol)
            self.post_processing()
            outputs = self.get_outputs()
        else:
            outputs = {}
        return outputs

    @abstractmethod
    def create_dvars(self) -> None:
        pass

    @abstractmethod
    def create_objectives(self) -> None:
        pass

    @abstractmethod
    def set_objective(self) -> None:
        pass

    @abstractmethod
    def create_constraints(self) -> None:
        pass

    def set_cplex_parameters(self) -> None:
        if int(self.dm.param.time_limit) > 0:
            self.mdl.parameters.timelimit = int(self.dm.param.time_limit)

        if int(self.dm.param.threads) > 0:
            self.mdl.parameters.threads = int(self.dm.param.threads)

        if self.dm.param.handle_unscaled_infeasibilities:
            self._set_cplex_parameters_unscaled_infeasibilities()

        if self.dm.param.log_solution_quality_metrics:
            # Configure the mdl to generate quality metrics, will be available in mdl.solve_details.quality_metrics
            self.mdl.quality_metrics = True

    def set_cpo_parameters(self):
        if self.cpo_params is None:
            self.cpo_params = CpoParameters()

        if int(self.dm.param.time_limit) > 0:
            self.cpo_params.TimeLimit = int(self.dm.param.time_limit)

        # self.cpo_params.KPIDisplay = 'MultipleLines'
        # self.cpo_params.ConflictRefinerTimeLimit = 60
        # self.cpo_params.LogPeriod = 10_000  # Number of branches, default 1000
        # self.cpo_params.LogVerbosity = 'Normal'  #'Terse'

    def solve(self) -> Optional[CpoSolveResult]:
        """
        Solve the model
        """
        msol = self.mdl.solve(params=self.cpo_params, **self.solve_kwargs)
        self.export_as_lp_path(lp_file_name=self.mdl.name)
        if msol.is_solution():
            pass
            # TODO: CPO equivalent of CPLEX report?
            # self.mdl.report()
        elif self.enable_refine_conflict:
            self.refine_conflict()
        return msol

    @abstractmethod
    def extract_solution(self, msol: CpoSolveResult, drop: bool = True) -> None:
        self.dm.logger.debug("Enter")

        # KPIs
        self.dm.kpis = self.get_kpi_output_table(msol)

    @abstractmethod
    def post_processing(self) -> None:
        self.dm.post_processing()

    def get_outputs(self) -> Outputs:
        return self.dm.get_outputs()

    ################################################################
    #  Utils
    ################################################################
    def refine_conflict(self):
        """
        TODO: refine to logger?
        TODO: control by parameter?
        TODO: support CP Optimizer
        :return:
        """
        self.logger.debug("Start ConflictRefiner")
        conflicts: CpoRefineConflictResult = self.mdl.refine_conflict()  # TODO: Is this working?
        conflicts.print_conflict()  # TODO: Deprecated
        # crefiner = ConflictRefiner()  # Create an instance of the ConflictRefiner
        # conflicts = crefiner.refine_conflict(self.mdl)  # Run the conflict refiner
        # # ConflictRefiner.display_conflicts(conflicts) #Display the results
        # for c in conflicts:
        #     print(c.element)  # Display conflict result in a little more compact format than ConflictRefiner.display_conflicts


    @staticmethod
    def condition_values(var):
        """Fix issues with CPLEX using a tolerance"""
        if isinstance(var, int):
            return var
        elif isinstance(var, float):
            return var
        else:
            return round(var.solution_value + 1e-6, 5)

    @staticmethod
    def df_extract_solution(df,
                            extract_dvar_names: List[str] = None,
                            drop_column_names: List[str] = None,
                            drop: bool = True,
                            column_name_post_fix: str = 'Sol'):
        """Generalized routine to extract a solution value.
        Can remove the dvar column from the df to be able to have a clean df for export into scenario.
        For each dvar column in extract_dvar_names, extract solution into a new column with the same name
        and the column_name_post_fix added.

        :param df
        :param extract_dvar_names:
        :param drop_column_names: List of columns to drop **in addition** to the columns in extract_dvar_names
        :param drop:
        :param column_name_post_fix:

        """

        if extract_dvar_names is not None:
            for xDVarName in extract_dvar_names:
                if xDVarName in df.columns:
                    df[f'{xDVarName}{column_name_post_fix}'] = [Core01CpoOptimizationEngine.condition_values(dvar) for dvar in df[xDVarName]]
                    if drop and len(column_name_post_fix) > 0:
                        # Only drop if we created a new column
                        df = df.drop([xDVarName], axis=1)
        if drop and drop_column_names is not None:
            for column in drop_column_names:
                if column in df.columns:
                    df = df.drop([column], axis=1)
        return df
    
    def get_kpi_output_table(self, msol: CpoSolveResult) -> pd.DataFrame:
        """Overrides the default and uses the default `['NAME', 'VALUE']` columns."""
        # print("   KPIs: {}".format(msol.get_kpis()))
        # all_kpis = [(kp.name, kp.compute()) for kp in self.mdl.get_kpis()]
        all_kpis = msol.get_kpis()
        # df_kpis = pd.DataFrame(dict(all_kpis), columns=['NAME', 'VALUE']).set_index('NAME')
        df_kpis = pd.DataFrame([{'NAME': key, 'VALUE': value} for key, value in all_kpis.items()])
        return df_kpis

    def export_as_lp_path(self, lp_file_name: str = 'my_cpo_file') -> str:
        """
        Saves .lp file in self.export_lp_path
        Note: Does not conflict with `OptimizationEngine.export_as_lp()` which has a different signature.
        :return: file_path
        """
        filepath = None
        if self.export_lp:
            if pathlib.Path(lp_file_name).suffix != '.cpo':
                lp_file_name = lp_file_name + '.cpo'
            filepath = os.path.join(self.export_lp_path, lp_file_name)
            self.logger.debug(f"Exporting .cpo file: {filepath}")
            self.mdl.export_as_cpo(filepath)
        return filepath

    def export_as_sav_path(self, sav_file_name: str = 'my_sav_file') -> str:
        """
        Saves .sav file in self.export_lp_path
        :return: file_path
        """
        filepath = None
        if self.export_sav:
            if pathlib.Path(sav_file_name).suffix != '.sav':
                sav_file_name = sav_file_name + '.sav'
            filepath = os.path.join(self.export_lp_path, sav_file_name)
            self.dm.logger.debug(f"Exporting .sav file: {filepath}")
            self.mdl.export_as_sav(filepath)
        return filepath

    ########################################################
    # Metrics
    ########################################################
    def _set_cplex_parameters_unscaled_infeasibilities(self):
        """CPLEX Parameters to help handle unscaled infeasibilities
        See:
        - https://www.ibm.com/docs/en/icos/22.1.0?topic=infeasibility-coping-ill-conditioned-problem-handling-unscaled-infeasibilities
        - https://orinanobworld.blogspot.com/2010/08/ill-conditioned-bases-and-numerical.html
        """
        self.mdl.parameters.read.scale = 1
        self.mdl.parameters.simplex.tolerances.markowitz = 0.90
        self.mdl.parameters.simplex.tolerances.feasibility = 1e-9
        self.mdl.parameters.emphasis.numerical = 1
        # self.mdl.parameters.lpmethod = 1  # 1: primal-simplex

    def log_solution_quality_metrics(self):
        """Log the solution quality metrics
        :return:
        """
        if self.dm.param.log_solution_quality_metrics:
            self.dm.logger.debug(f"Solution quality metrics:")
            max_key_length = max([len(key) for key in self.mdl.solve_details.quality_metrics.keys()], default=10)  # `default` option is just to ensure the code doesn't throw an exception in case there are no quality_metrics
            for key, value in self.mdl.solve_details.quality_metrics.items():
                self.dm.logger.debug(f"{key.ljust(max_key_length, ' ')} = {value:,}")

    def extract_engine_metrics(self):
        if self.solver_metrics is not None:
            return pd.DataFrame(self.solver_metrics).set_index('name')
        else:
            return pd.DataFrame(columns=['name', 'value']).set_index('name')

    #########################
    # Progress Tracking
    #########################
    def record_optimization_progress(self, data: List[Dict]):
        self.dm.add_optimization_progress(data)

############################################################
class CplexSum():
    """Function class that adds a series of dvars into a cplex sum expression.
    To be used as a custom aggregation in a groupby.
    Usage:
        df2 = df1.groupby(['a']).agg({'xDVar':CplexSum(engine.mdl)}).rename(columns={'xDVar':'expr'})

    Sums the dvars in the 'xDVar' column into an expression
    """
    def __init__(self, mdl):
        self.mdl = mdl
    def __call__(self, dvar_series):
        return self.mdl.sum(dvar_series)

#################################################################
class CpoProgressTrackerCallback(CpoCallback):
    """
    Callback for CP Optimizer. Not registered by default.
    Usage:
        * In the `__init__` of your OptimizationEngine, add:
        `self.mdl.add_solver_callback(CpoProgressTrackerCallback(self))`
        * Callback calls self.record_optimization_progress(), which calls self.dm.add_optimization_progress()
        * Results will be stored in `self.dm.optimization_progress_output`
        * dse-do-dashboard has 2 visualization-pages
    """
    def __init__(self, engine: Core01CpoOptimizationEngine[DM]):
        super().__init__()
        self.engine = engine
        self.progress_seq = 0

    def invoke(self, solver: cp.solver.solver.CpoSolver, event: str, sres: cp.solution.CpoSolveResult):
        # print(f"Callback event={event}")
        if event in ("Solution", "ObjBound"):
            obj_val = sres.get_objective_values()  # TODO: handle multiple return values
            obj_bnds = sres.get_objective_bounds()  # TODO: same
            obj_gaps = sres.get_objective_gaps()
            solvests = sres.get_solve_status()  # E.g. 'Feasible'
            srchsts = sres.get_search_status()  # E.g. 'SearchOngoing'
            solve_time = sres.get_info('SolveTime')
            print(f"CALLBACK: {event}: {solvests}, {srchsts}, objective: {obj_val} bounds: {obj_bnds}, gaps: {obj_gaps}, time: {solve_time}")

            # data = {
            #     'solve_time': sres.get_info('SolveTime'),
            #     'objective_value': sres.get_objective_values(),  #TODO: handle multiple return values
            #     'objective_bound': sres.get_objective_bounds(),
            #     'objective_gap': sres.get_objective_gaps(),
            # }
            solve_time = sres.get_info('SolveTime')
            if type(solve_time) is tuple:
                solve_time = solve_time[0]
            objective_value = sres.get_objective_values()  # TODO: handle multiple return values
            if type(objective_value) is tuple:
                objective_value = objective_value[0]
            objective_bound = sres.get_objective_bounds()  # TODO: same
            if type(objective_bound) is tuple:
                objective_bound = objective_bound[0]
            objective_gap = sres.get_objective_gaps()
            if type(objective_gap) is tuple:
                objective_gap = objective_gap[0]
            solve_status = sres.get_solve_status()  # E.g. 'Feasible'
            search_status = sres.get_search_status()  # E.g. 'SearchOngoing'
            kpis = sres.get_kpis()

            run_id: str = 'run_0'  # TODO

            if objective_value is not None and objective_bound is not None:
                seq = self.progress_seq
                data = []
                data.append({'run_id': run_id, 'progress_seq': seq, 'metric_type': 'engine', 'metric_name': 'solve_time',
                             'metric_value': solve_time, 'metric_text_value': None})
                data.append({'run_id': run_id, 'progress_seq': seq, 'metric_type': 'engine', 'metric_name': 'objective_value',
                             'metric_value': objective_value, 'metric_text_value': None})
                data.append({'run_id': run_id, 'progress_seq': seq, 'metric_type': 'engine', 'metric_name': 'objective_bound',
                             'metric_value': objective_bound, 'metric_text_value': None})
                data.append({'run_id': run_id, 'progress_seq': seq, 'metric_type': 'engine', 'metric_name': 'objective_gap',
                             'metric_value': objective_gap, 'metric_text_value': None})
                data.append({'run_id': run_id, 'progress_seq': seq, 'metric_type': 'engine', 'metric_name': 'solve_status',
                             'metric_value': None, 'metric_text_value': solve_status})
                data.append({'run_id': run_id, 'progress_seq': seq, 'metric_type': 'engine', 'metric_name': 'search_status',
                             'metric_value': None, 'metric_text_value': search_status})
                data.append({'run_id': run_id, 'progress_seq': seq, 'metric_type': 'engine', 'metric_name': 'event_type',
                             'metric_value': None, 'metric_text_value': event})
                if isinstance(kpis, Dict):
                    for kpi_name, kpi_value in kpis.items():
                        data.append({'run_id': run_id, 'progress_seq': seq, 'metric_type': 'kpi', 'metric_name': kpi_name,
                                     'metric_value': kpi_value, 'metric_text_value': None})

                self.engine.record_optimization_progress(data)
                self.progress_seq = self.progress_seq + 1


