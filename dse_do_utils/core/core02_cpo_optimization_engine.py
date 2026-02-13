# Copyright IBM Corp. 2021, 2022
# IBM Confidential Source Code Materials
# This Source Code is subject to the license and security terms contained in the License.txt file contained in this source code package.

from typing import Optional, List, Dict, TypeVar

import docplex
import pandas as pd
from docplex.cp.solution import CpoSolveResult
from docplex.mp.conflict_refiner import ConflictRefiner
from docplex.mp.linear import ZeroExpr
from docplex.mp.solution import SolveSolution

from dse_do_utils.core.core01_cpo_optimization_engine import Core01CpoOptimizationEngine, CpoProgressTrackerCallback
from dse_do_utils.core.core01_optimization_engine import Core01OptimizationEngine
from dse_do_utils.core.core02_data_manager import Core02DataManager
from dse_do_utils.core.core02_optimization_engine import LexGoalAgg

# class LexGoalAgg():
#     """For use in aggregation of goals in lexicographical optimization
#     """
#     def __init__(self, mdl):
#         self.mdl = mdl
#
#     def __call__(self, group):
#         return self.mdl.sum(group.expr * group.weight)


DM = TypeVar('DM', bound='Core02DataManager')


class Core02CpoOptimizationEngine(Core01CpoOptimizationEngine[DM]):
    """Adds Lexicographical Optimization

    How To enable Lexicographical Optimization:
    1. Add tables `LexOptiLevel` and `LexOptiGoal` to the spreadsheet (if applicable, include in __index__!)
    2. Subclass the optimization-engine, data-manager and scenario-db-manager from their Core2 classes
    3. In OptimizationEngine, override the method `lex_get_goal_expr()`
    4. In DataManager, override abstract methods `get_default_lex_opti_level_table` and `get_default_lex_opti_goal_table`
    4. In ScenarioDBManager, add the
        `('LexOptiLevel', Core02LexOptiLevelTable()),
         ('LexOptiGoal', Core02LexOptiGoalTable()),`
        to the input_db_tables
    """

    def __init__(self, data_manager: DM, name: str = None, solve_kwargs=None,
                 export_lp: bool = False, export_sav: bool = False, export_lp_path: str = '',
                 enable_refine_conflict: bool = False):
        if solve_kwargs is None:
            solve_kwargs = {"log_output": True, 'verbose': 1, 'trace_log': True,
                            'LogVerbosity': 'Terse',  # Quiet, Terse, Normal, and Verbose
                            }
            # solve_kwargs = {"log_output": True}
        super().__init__(data_manager, name=name, solve_kwargs=solve_kwargs,
                         export_lp=export_lp, export_sav=export_sav, export_lp_path=export_lp_path,
                         enable_refine_conflict=enable_refine_conflict)
        self.lex_opti_metrics_list: List[Dict] = []
        self.objective = None

    ####################################################################################
    #  Solve
    ####################################################################################
    def solve(self) -> Optional[SolveSolution]:
        """
        Note: `**kwargs` for mdl.solve are in self.solve_kwargs
        :return:
        """

        # self.dm.add_time_point('Prior CPLEX Solver')
        self.dm.logger.debug("Enter")
        if self.dm.param.enable_lex_optimization:
            msol = self.solve_with_lex_goals(**self.solve_kwargs)
        else:
            msol = super().solve()
        # if msol is not None:
        #     # TODO: should we always print the report? Or do we need an additional 'debug/log' parameter
        #     self.mdl.report()

        # self.dm.add_time_point('CPLEX Solver End')
        # self.dm.add_summary_duration('Total - CPLEX Solving',
        #                              from_key='Prior CPLEX Solver',
        #                              to_key='CPLEX Solver End')
        return msol

    def record_lex_opti_metrics(self, level_id: str, msol: CpoSolveResult) -> None:
        solve_time = msol.get_info('SolveTime')
        if type(solve_time) is tuple:
            solve_time = solve_time[0]
        objective_gap = msol.get_objective_gaps()
        if type(objective_gap) is tuple:
            objective_gap = objective_gap[0]
        solve_status = msol.get_solve_status()
        objective_value = msol.get_objective_values()
        if type(objective_value) is tuple:
            objective_value = objective_value[0]
        statistics = self.mdl.get_statistics()
        kpis = msol.get_kpis()

        solver_metrics = [
            {'lexOptiLevelId' : level_id, 'metricType': 'solver', 'metricName': 'solveTime', 'metricValue': solve_time},  # In seconds
            {'lexOptiLevelId' : level_id, 'metricType': 'solver', 'metricName': 'mipGap', 'metricValue': objective_gap},  # NaN when not a MIP
            {'lexOptiLevelId' : level_id, 'metricType': 'solver', 'metricName': 'solveStatus', 'metricTextValue': solve_status},
            {'lexOptiLevelId' : level_id, 'metricType': 'solver', 'metricName': 'objectiveValue', 'metricValue': objective_value},
            {'lexOptiLevelId' : level_id, 'metricType': 'solver', 'metricName': 'numVariables', 'metricValue': statistics.get_number_of_variables()},
            {'lexOptiLevelId' : level_id, 'metricType': 'solver', 'metricName': 'numConstraints', 'metricValue': statistics.get_number_of_constraints()},
        ]
        # kpi_metrics = [{'lexOptiLevelId' : level_id, 'metricType': 'KPI', 'metricName': kp.name, 'metricValue':kp.compute()} for kp in self.mdl.iter_kpis()]
        kpi_metrics = []
        if isinstance(kpis, Dict):
            for kpi_name, kpi_value in kpis.items():
                kpi_metrics.append({'lexOptiLevelId' : level_id, 'metricType': 'KPI', 'metricName': kpi_name, 'metricValue': kpi_value})
        self.lex_opti_metrics_list.extend(solver_metrics)
        self.lex_opti_metrics_list.extend(kpi_metrics)
        if self.dm.param.log_solution_quality_metrics:
            quality_metrics = [{'lexOptiLevelId' : level_id, 'metricType': 'solution_quality', 'metricName': key, 'metricValue': value} for key, value in self.mdl.solve_details.quality_metrics.items()]
            self.lex_opti_metrics_list.extend(quality_metrics)

    def extract_lex_opti_metrics(self) -> pd.DataFrame:
        if len(self.lex_opti_metrics_list) > 0:
            df = pd.DataFrame(self.lex_opti_metrics_list).set_index(['lexOptiLevelId', 'metricType', 'metricName'], verify_integrity=True)
        else:
            df = pd.DataFrame(columns=['lexOptiLevelId', 'metricType', 'metricName', 'metricValue', 'metricTextValue']).set_index(['lexOptiLevelId', 'metricType', 'metricName'])
        return df

    # def record_solver_metrics(self, prefix=""):
    #     """ Record solver metrics """
    #
    #     if self.solver_metrics is None:
    #         self.solver_metrics = dict()
    #         self.solver_metrics['name'] = list()
    #         self.solver_metrics['value'] = list()
    #
    #     self.solver_metrics['name'].extend(
    #         [prefix + 'time to solve level ',
    #          prefix + 'mip gap',
    #          prefix + 'number of variables',
    #          prefix + 'number of constraints',
    #          prefix + 'time limit'])
    #
    #     self.solver_metrics['value'].append(self.mdl.solve_details.time)
    #     #self.solver_metrics['value'].append(self.mdl.solve_details.status)
    #     self.solver_metrics['value'].append(self.mdl.parameters.mip.tolerances.mipgap.value)
    #     self.solver_metrics['value'].append(self.mdl.number_of_variables)
    #     self.solver_metrics['value'].append(self.mdl.number_of_constraints)
    #     self.solver_metrics['value'].append(self.mdl.parameters.timelimit.value)

    def solve_with_lex_goals(self, **kwargs) -> Optional[CpoSolveResult]:
        msol = None
        self.dm.logger.debug("Enter")
        levels_df = self.get_lex_optimization_levels()
        self.lex_c = []
        for level in levels_df.itertuples():
            level_id = level.Index
            self.dm.logger.debug(f"Solving level: {level_id}")

            # Skip this level if not active
            if not level.isActive:
                self.dm.logger.debug(f"Skipping inactive level: {level_id}")
                continue

            # Deal with cases where objectiveExpr is None or NaN
            if pd.isna(level.objectiveExpr):
                self.dm.logger.debug(f"Skipping level: {level_id} due to no objective expression")
                continue

            # Solve level
            if self.objective is not None:
                self.mdl.remove(self.objective)  # Remove previous objective
            self.objective = level.objectiveExpr
            if level.sense == 'min':
                self.objective = self.mdl.minimize(level.objectiveExpr)
                # self.mdl.minimize(self.objective)
            else:
                self.objective = self.mdl.maximize(level.objectiveExpr)
                # self.mdl.maximize(self.objective)
            self.mdl.add(self.objective)  # Do we need this?

            # Callback
            if self.dm.param.enable_optimization_progress_tracking:
                if self.optimization_progress_tracking_callback is not None:
                    self.mdl.remove_solver_callback(self.optimization_progress_tracking_callback)
                self.optimization_progress_tracking_callback = self.get_solver_callback(lex_opti_level_id=level_id)
                self.mdl.add_solver_callback(self.optimization_progress_tracking_callback)

            # self.mdl.set_time_limit(level.timeLimit)
            # self.mdl.parameters.mip.tolerances.mipgap = level.mipGap  # TODO: set the CPO mipgap!
            msol: CpoSolveResult = self.mdl.solve(
                TimeLimit=level.timeLimit,
                **kwargs)
            # self.dm.logger.info(f"Solve completed with status '{self.mdl.solve_details.status}' and time {self.mdl.solve_details.time:.2f} sec")
            self.dm.logger.info(f"Solve completed with status '{msol.get_solve_status()}' and time {msol.get_info('SolveTime'):.2f} sec")

            lp_filepath = self.export_as_lp_path(f"{self.mdl.name}_{level.priority}_{level_id}.lp")
            sav_filepath = self.export_as_sav_path(f"{self.mdl.name}_{level.priority}_{level_id}.sav")

            # Check if it solved
            if msol is None or not msol.is_solution():
                # No solution found TODO SHOULD LOG SOMETHING - extract_engine_metrics_failed or something
                self.dm.logger.warning("No solution found.")
                self.refine_conflict()
                break
            else:
                # self.mdl.report() # TODO: how to get a report of the solution?
                pass

            # # Save the engine metrics
            self.record_lex_opti_metrics(level_id, msol)  # Results in output table 'LexOptiMetrics'
            # self.record_solver_metrics(f'{level_id} ')
            self.log_solution_quality_metrics()  # To the self.dm.logger.debug

            self.dm.logger.debug(f"absTol: {level.absTol}, relTol: {level.relTol}")
            objective_value = msol.get_objective_values()
            if type(objective_value) is tuple:
                objective_value = objective_value[0]
            if level.sense == 'min':
                level_bound = objective_value + level.absTol + level.relTol * abs(objective_value)
                self.lex_c.append(self.mdl.add(level.objectiveExpr <= level_bound)) #, f"LexLevelBound_{level_id}"))
            else:
                level_bound = objective_value - level.absTol - level.relTol * abs(objective_value)
                self.lex_c.append(self.mdl.add(level.objectiveExpr >= level_bound))  # , f"LexLevelBound_{level_id}"))

            self.dm.logger.debug(f"{level_id} level constraint added with bound {level_bound}")

            # self.dm.logger.debug(f"{level_id} level set starting point for next level solve.")
            self.mdl.set_starting_point(msol.get_solution())

        # self.mdl.remove(self.lex_c)  # TODO VT_20260128: do we need this, giving an error
        return msol

    def lex_get_goal_expr(self, goal_id):
        """ABSTRACT method. TO BE OVERRIDDEN!"""
        # if goal_id == 'backlogCost':
        #     return self.backlog_cost
        # elif goal_id == 'unfulfilledDemandCost':
        #     return self.unfulfilled_demand_cost
        # elif goal_id == 'inventoryCost':
        #     return self.inventory_cost
        # elif goal_id == 'productionCost':
        #     return self.production_cost
        # elif goal_id == 'transportationCost':
        #     return self.transportation_cost
        # elif goal_id == 'warehouseFixedCost':
        #     return self.warehouse_option_fixed_cost
        # elif goal_id == 'warehouseVariableCost':
        #     return self.warehouse_variable_cost
        # elif goal_id == 'externalSupplyCost':
        #     return self.external_supply_cost
        # elif goal_id == 'targetInventorySlackCost':
        #     return self.target_inventory_slack_cost

        self.dm.logger.warning(f"Error: cannot find goal expression for {goal_id}")
        return 0

    def get_lex_optimization_levels(self):
        goals_df = self.dm.lex_opti_goals.reset_index()
        goals_df = goals_df[goals_df.isActive]

        if len(goals_df) == 0:
            self.dm.logger.warning('No lexicographic goals set')
            return self.dm.lex_opti_levels.join(goals_df)

        goals_df['expr'] = goals_df.apply(lambda row: self.lex_get_goal_expr(row.lexOptiGoalId), axis=1)

        level_expr_df = ((goals_df[['lexOptiLevelId', 'expr', 'weight']]
                          .groupby(['lexOptiLevelId'])).apply(LexGoalAgg(self.mdl), include_groups=False)
                         .to_frame(name='objectiveExpr')
                         )
        levels_df = (self.dm.lex_opti_levels
                     .join(level_expr_df)
                     .sort_values('priority', ascending=True)  # Priority 1 first
                     )
        # Note that in some cases the objectiveExpr is None in case level has no (active) goals
        # Deal with that later
        # Setting ot to zero or ZeroExpr(self.mdl) is going to fail later
        # levels_df['objectiveExpr'] = levels_df['objectiveExpr'].fillna(ZeroExpr(self.mdl))  #
        return levels_df

    def refine_conflict(self):
        """
        TODO: refine to logger?
        TODO: control by parameter?
        TODO: configure conflict_reporting_limit

        Notes:
        There can be no solution due to unbounded problem.
        As a result, the ConflictRefiner fails, thus the try-except
        :return:
        """
        self.dm.logger.info("Start ConflictRefiner.")
        try:
            crefiner = ConflictRefiner()  # Create an instance of the ConflictRefiner
            conflicts = crefiner.refine_conflict(self.mdl, display=True)  # Run the conflict refiner
            # ConflictRefiner.display_conflicts(conflicts) #Display the results
            conflict_reporting_limit = 100
            if len(conflicts) > conflict_reporting_limit:
                self.dm.logger.warning(f"Number of conflicts {len(conflicts)} exceeds reporting limit ({conflict_reporting_limit})")
            i = 0
            for c in conflicts:
                print(c.element)  # Display conflict result in a little more compact format than ConflictRefiner.display_conflicts
                i=i+1
                if i > conflict_reporting_limit:
                    print("Truncated conflict reporting")
                    break
        except:
            print("ConflictRefiner could not find a conflict")


    ####################################################################################
    #  Extract Solution
    ####################################################################################
    def extract_solution(self, msol: CpoSolveResult, drop: bool = True) -> None:
        super().extract_solution(msol, drop)

        self.dm.lex_opti_metrics_output = self.extract_lex_opti_metrics()

    def get_progress_tracker_callback(self) -> CpoProgressTrackerCallback:
        """Override this method to return a callback that tracks the progress of the lexicographical optimization levels. The callback will be called by the CPO solver at each new incumbent solution, with the current solution and its metrics as input. The callback can then extract the relevant metrics and store them in the optimization engine for later analysis or display.
        """
        return Core02CpoProgressTrackerCallback(self)

#################################################################
# Lexicographical Optimization Progress callback
#################################################################
class Core02CpoProgressTrackerCallback(CpoProgressTrackerCallback):
    """Callback to track the progress of the lexicographical optimization levels.
    To be returned by the method `get_progress_tracker_callback` of the optimization engine, and will be called by the CPO solver at each new incumbent solution, with the current solution and its metrics as input. The callback can then extract the relevant metrics and store them in the optimization engine for later analysis or display.
    """
    def __init__(self, engine: Core02CpoOptimizationEngine[DM]):
        super().__init__(engine=engine)
        ## TODO: how to track the level?
