# Copyright IBM Corp. 2021, 2022
# IBM Confidential Source Code Materials
# This Source Code is subject to the license and security terms contained in the License.txt file contained in this source code package.
import os
import pathlib
from abc import abstractmethod
from typing import Dict, List, Optional

import docplex.mp.model
import pandas as pd
from docplex.mp.conflict_refiner import ConflictRefiner
from docplex.mp.solution import SolveSolution

from dse_do_utils import OptimizationEngine
from dse_do_utils.core.core01_data_manager import Core01DataManager
from dse_do_utils.datamanager import Outputs
from typing import TypeVar, Generic

DM = TypeVar('DM', bound='Core01DataManager')


class Core01OptimizationEngine(OptimizationEngine[DM]):
    """
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
        super().__init__(data_manager=data_manager, name=name)

        if solve_kwargs is None:
            solve_kwargs = {"log_output": True}
        self.solve_kwargs = solve_kwargs
        self.export_lp = export_lp
        self.export_sav = export_sav
        self.export_lp_path = export_lp_path
        self.enable_refine_conflict = enable_refine_conflict
        self.logger = data_manager.logger

    def run(self) -> Outputs:
        self.dm.prepare_data_frames()
        self.dm.pre_processing()

        self.create_dvars()
        self.create_objectives()
        self.set_objective()
        self.create_constraints()
        self.set_cplex_parameters()
        msol = self.solve()
        if msol is not None:
            self.extract_solution()
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

        if float(self.dm.param.mip_gap) > 0:
            self.mdl.parameters.mip.tolerances.mipgap = float(self.dm.param.mip_gap)

        if self.dm.param.handle_unscaled_infeasibilities:
            self._set_cplex_parameters_unscaled_infeasibilities()

        if self.dm.param.log_solution_quality_metrics:
            # Configure the mdl to generate quality metrics, will be available in mdl.solve_details.quality_metrics
            self.mdl.quality_metrics = True

    def solve(self) -> Optional[SolveSolution]:
        msol = self.mdl.solve(**self.solve_kwargs)
        self.dm.logger.info(
        f"Solve completed with status '{self.mdl.solve_details.status}' and time {self.mdl.solve_details.time:.2f} sec")
        self.export_as_lp_path(lp_file_name=self.mdl.name)
        if msol is not None:
            # TODO: enable print report?
            self.mdl.report()
        elif self.enable_refine_conflict:
            self.refine_conflict()
        return msol

    @abstractmethod
    def extract_solution(self, drop: bool = True) -> None:
        self.dm.logger.debug("Enter")

        # KPIs
        self.dm.kpis = self.get_kpi_output_table()

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
        crefiner = ConflictRefiner()  # Create an instance of the ConflictRefiner
        conflicts = crefiner.refine_conflict(self.mdl)  # Run the conflict refiner
        # ConflictRefiner.display_conflicts(conflicts) #Display the results
        for c in conflicts:
            print(c.element)  # Display conflict result in a little more compact format than ConflictRefiner.display_conflicts


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
                    df[f'{xDVarName}{column_name_post_fix}'] = [Core01OptimizationEngine.condition_values(dvar) for dvar in df[xDVarName]]
                    if drop and len(column_name_post_fix) > 0:
                        # Only drop if we created a new column
                        df = df.drop([xDVarName], axis=1)
        if drop and drop_column_names is not None:
            for column in drop_column_names:
                if column in df.columns:
                    df = df.drop([column], axis=1)
        return df
    
    def get_kpi_output_table(self) -> pd.DataFrame:
        """Overrides the default and uses the default `['NAME', 'VALUE']` columns."""
        all_kpis = [(kp.name, kp.compute()) for kp in self.mdl.iter_kpis()]
        df_kpis = pd.DataFrame(all_kpis, columns=['NAME', 'VALUE']).set_index('NAME')
        return df_kpis

    def export_as_lp_path(self, lp_file_name: str = 'my_lp_file') -> str:
        """
        Saves .lp file in self.export_lp_path
        Note: Does not conflict with `OptimizationEngine.export_as_lp()` which has a different signature.
        :return: file_path
        """
        filepath = None
        if self.export_lp:
            if pathlib.Path(lp_file_name).suffix != '.lp':
                lp_file_name = lp_file_name + '.lp'
            filepath = os.path.join(self.export_lp_path, lp_file_name)
            self.logger.debug(f"Exporting .lp file: {filepath}")
            self.mdl.export_as_lp(filepath)
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

    ##########################################
    # Tuning (TODO)
    ##########################################
    def cplex_tune_model(self):
        """DRAFT
        Run the cplex parameter tuning
        From https://stackoverflow.com/questions/53353970/where-can-i-find-the-documentation-of-docplex-automatic-tuning-tool
        Works but beware of too short time-limit
        Returns:

        """
        cpx = self.mdl.get_engine().get_cplex()
        status = cpx.parameters.tune_problem()
        if status == cpx.parameters.tuning_status.completed:
            print("tuned parameters:")
            for param, value in cpx.parameters.get_changed():
                print("{0}: {1}".format(repr(param), value))
        else:
            print("tuning status was: {0}".format(
                cpx.parameters.tuning_status[status]))

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

class CplexDot():
    """Function class that adds a series of dvars into a cplex sum expression.
    To be used as a custom aggregation in a groupby.
    Usage:
        df2 = df1.groupby(['a']).apply(CplexDot(engine.mdl, 'xDVar', 'volume')).to_frame(name='expr')

    For each group, creates an expression df2['expr'] = mdl.dot(group.xDVar, group.volume)
    In above usage, df2 is a DataFrame with the index based on the groupby keys and one column named 'expr'.
    """
    def __init__(self, mdl: docplex.mp.model.Model, column1: str, column2: str):
        """
        Args:
            mdl: Cplex Model instance
            column1 (str): Name of column_1 in DataFrame
            column1 (str): Name of column_2 in DataFrame
        """
        self.mdl = mdl
        self.column1 = column1
        self.column2 = column2
    def __call__(self, group):
        return self.mdl.dot(group[self.column1], group[self.column2])
