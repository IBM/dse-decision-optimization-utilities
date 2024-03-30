# Copyright IBM Corp. 2021, 2022
# IBM Confidential Source Code Materials
# This Source Code is subject to the license and security terms contained in the License.txt file contained in this source code package.

from typing import Optional, List, Dict, TypeVar

import docplex
import pandas as pd
from docplex.mp.conflict_refiner import ConflictRefiner
from docplex.mp.linear import ZeroExpr
from docplex.mp.solution import SolveSolution

from dse_do_utils.core.core01_optimization_engine import Core01OptimizationEngine
from dse_do_utils.core.core02_data_manager import Core02DataManager


class LexGoalAgg():
    """For use in aggregation of goals in lexicographical optimization
    """
    def __init__(self, mdl):
        self.mdl = mdl

    def __call__(self, group):
        return self.mdl.sum(group.expr * group.weight)


DM = TypeVar('DM', bound='Core02DataManager')


class Core02OptimizationEngine(Core01OptimizationEngine[DM]):
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

    def __init__(self, data_manager: Core02DataManager, name: str = None, solve_kwargs: Dict = {"log_output": True},
                 export_lp: bool = False, export_sav: bool = False, export_lp_path: str = '',
                 enable_refine_conflict: bool = False):
        super().__init__(data_manager, name=name, solve_kwargs=solve_kwargs,
                         export_lp=export_lp, export_sav=export_sav, export_lp_path=export_lp_path,
                         enable_refine_conflict=enable_refine_conflict)
        # self.solver_metrics = None
        self.lex_opti_metrics_list: List[Dict] = []

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

    def record_lex_opti_metrics(self, level_id: str):
        solver_metrics = [
            {'lexOptiLevelId' : level_id, 'metricType': 'solver', 'metricName': 'solveTime', 'metricValue': self.mdl.solve_details.time},  # In seconds
            {'lexOptiLevelId' : level_id, 'metricType': 'solver', 'metricName': 'mipGap', 'metricValue': self.mdl.solve_details.gap},  # NaN when not a MIP
            {'lexOptiLevelId' : level_id, 'metricType': 'solver', 'metricName': 'solveStatus', 'metricTextValue': self.mdl.solve_details.status},
            {'lexOptiLevelId' : level_id, 'metricType': 'solver', 'metricName': 'objectiveValue', 'metricValue': self.mdl.objective_value},
            {'lexOptiLevelId' : level_id, 'metricType': 'solver', 'metricName': 'numVariables', 'metricValue': self.mdl.number_of_variables},
            {'lexOptiLevelId' : level_id, 'metricType': 'solver', 'metricName': 'numConstraints', 'metricValue': self.mdl.number_of_constraints},
        ]
        kpi_metrics = [{'lexOptiLevelId' : level_id, 'metricType': 'KPI', 'metricName': kp.name, 'metricValue':kp.compute()} for kp in self.mdl.iter_kpis()]
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

    def solve_with_lex_goals(self, **kwargs) -> Optional[SolveSolution]:
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

            # Deal with cases where objectiveExpr is None
            if not isinstance(level.objectiveExpr, docplex.mp.basic.Expr):
                self.dm.logger.debug(f"Skipping level: {level_id} due to no objective expression")
                continue

            # Solve level
            self.mdl.set_objective(level.sense, level.objectiveExpr)
            self.mdl.set_time_limit(level.timeLimit)
            self.mdl.parameters.mip.tolerances.mipgap = level.mipGap
            msol = self.mdl.solve(
                clean_before_solve=self.dm.param.handle_unscaled_infeasibilities, # Do a clean to better handle unscaled_infeasibilities
                **kwargs)  # cplex_parameters={'parameters.mip.tolerances.mipgap': level.mipGap}
            # self.dm.logger.info(f"Solve details = {self.mdl.solve_details}")
            self.dm.logger.info(f"Solve completed with status '{self.mdl.solve_details.status}' and time {self.mdl.solve_details.time:.2f} sec")
            # self.dm.add_time_point(f'CPLEX Solve Level {level_id}')
            lp_filepath = self.export_as_lp_path(f"{self.mdl.name}_{level.priority}_{level_id}.lp")
            sav_filepath = self.export_as_sav_path(f"{self.mdl.name}_{level.priority}_{level_id}.sav")
            # self.dm.logger.info(f"Exported level{level_id}.lp to {lp_filepath}")

            # Check if it solved
            if msol is None:
                # No solution found TODO SHOULD LOG SOMETHING - extract_engine_metrics_failed or something
                self.dm.logger.warning("No solution found.")
                self.refine_conflict()
                break
            else:
                self.mdl.report()

            # # Save the engine metrics
            self.record_lex_opti_metrics(level_id)  # Results in output table 'LexOptiMetrics'
            # self.record_solver_metrics(f'{level_id} ')
            self.log_solution_quality_metrics()  # To the self.dm.logger.debug

            self.dm.logger.debug(f"absTol: {level.absTol}, relTol: {level.relTol}")
            if level.sense == 'min':
                level_bound = level.objectiveExpr.solution_value + level.absTol + level.relTol * abs(level.objectiveExpr.solution_value)
                self.lex_c.append(self.mdl.add_constraint(level.objectiveExpr <= level_bound, f"LexLevelBound_{level_id}"))
            else:
                level_bound = level.objectiveExpr.solution_value - level.absTol - level.relTol * abs(level.objectiveExpr.solution_value)
                self.lex_c.append(self.mdl.add_constraint(level.objectiveExpr >= level_bound, f"LexLevelBound_{level_id}"))

            self.dm.logger.debug(f"{level_id} level constraint added")

        self.mdl.remove_constraints(self.lex_c)
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
                          .groupby(['lexOptiLevelId'])).apply(LexGoalAgg(self.mdl))
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
    def extract_solution(self, drop: bool = True) -> None:
        super().extract_solution(drop)

        self.dm.lex_opti_metrics_output = self.extract_lex_opti_metrics()

