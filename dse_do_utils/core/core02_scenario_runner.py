# Copyright IBM All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import dataclass

import pandas as pd
from dse_do_utils.core.core01_optimization_engine import Core01OptimizationEngine

from dse_do_utils.core.core01_data_manager import Core01DataManager

from dse_do_utils import ScenarioManager, OptimizationEngine
from dse_do_utils.datamanager import Inputs, Outputs, DataManager
from dse_do_utils.scenariodbmanager import ScenarioDbManager
from logging import Logger, getLogger
from typing import Any, Dict, Optional, Tuple, NamedTuple, Type, List, Union

from dse_do_utils.scenariomanager import Platform
from dse_do_utils.scenariorunner import ScenarioConfig, ScenarioGenerator


@dataclass  # (frozen=True)
class Core02ScenarioConfig(ScenarioConfig):
    lex_opti_levels: Dict = None  # Dict compatible with pd.DataFrame.__init__()
    lex_opti_goals: Dict = None  # Dict compatible with pd.DataFrame.__init__()


class Core02ScenarioGenerator(ScenarioGenerator):
    """Adds LexOptiLevel and LexOptiGoal configuration
    """

    def __init__(self,
                 inputs: Inputs,
                 scenario_config: ScenarioConfig) -> None:
        super().__init__(inputs=inputs, scenario_config=scenario_config)

    def generate_scenario(self):
        new_inputs = super().generate_scenario()  # Does the Parameter table

        new_inputs['LexOptiLevel'] = self.get_lex_opti_levels()
        new_inputs['LexOptiGoals'] = self.get_lex_opti_goals()

        return new_inputs

    def get_lex_opti_levels(self) -> pd.DataFrame:
        """Applies overrides to the Parameter table based on the ScenarioConfig.parameters.
        """
        if self.scenario_config.lex_opti_levels is None:
            df = self.inputs['LexOptiLevel']
        else:
            df = pd.DataFrame(self.scenario_config.lex_opti_levels)
        return df

    def get_lex_opti_goals(self) -> pd.DataFrame:
        """Applies overrides to the Parameter table based on the ScenarioConfig.parameters.
        """
        if self.scenario_config.lex_opti_goals is None:
            df = self.inputs['LexOptiGoal']
        else:
            df = pd.DataFrame(self.scenario_config.lex_opti_goals)
        return df




