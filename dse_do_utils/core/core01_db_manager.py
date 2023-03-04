# Copyright IBM Corp. 2021, 2022
# IBM Confidential Source Code Materials
# This Source Code is subject to the license and security terms contained in the License.txt file contained in this source code package.

from typing import List, Dict
from collections import OrderedDict
from dse_do_utils.scenariodbmanager import ScenarioDbTable, ScenarioDbManager, ParameterTable, KpiTable, \
    BusinessKpiTable


class Core01ScenarioDbManager(ScenarioDbManager):
    def __init__(self, input_db_tables: Dict[str, ScenarioDbTable] = None, output_db_tables: Dict[str, ScenarioDbTable] = None,
                 credentials=None, schema: str = None, echo=False, multi_scenario: bool = True,
                 **kwargs):
        if input_db_tables is None:
            input_db_tables = OrderedDict([
                ('Parameter', ParameterTable()),
            ])
        if output_db_tables is None:
            output_db_tables = OrderedDict([
                ('kpis', KpiTable()),
                ('BusinessKPIs', BusinessKpiTable()),
            ])
        super().__init__(input_db_tables=input_db_tables, output_db_tables=output_db_tables, credentials=credentials,
                         schema=schema, echo=echo, multi_scenario=multi_scenario, **kwargs)
