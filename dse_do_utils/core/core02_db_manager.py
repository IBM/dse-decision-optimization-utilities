# Copyright IBM Corp. 2021, 2022
# IBM Confidential Source Code Materials
# This Source Code is subject to the license and security terms contained in the License.txt file contained in this source code package.

from typing import List, Dict
from sqlalchemy import Table, Column, String, Integer, Float, ForeignKey, ForeignKeyConstraint, DateTime, Boolean
from collections import OrderedDict
from dse_do_utils.scenariodbmanager import ScenarioDbTable, ParameterTable, KpiTable, BusinessKpiTable
from utils.core.core01_db_manager import Core01ScenarioDbManager


class Core02LexOptiLevelTable(ScenarioDbTable):
    def __init__(self, db_table_name: str = 'lex_opti_level', columns_ext: List[Column] = [], constraints_ext: List[ForeignKeyConstraint] = []):
        columns = [
            Column('lexOptiLevelId', String(256), primary_key=True),
            Column('priority', Integer(), primary_key=False, nullable=False),
            Column('sense', String(3), primary_key=False),
            Column('timeLimit', Integer(), primary_key=False),
            Column('mipGap', Float(), primary_key=False),
            Column('relTol', Float(), primary_key=False),
            Column('absTol', Float(), primary_key=False),
            Column('isActive', Boolean(), primary_key=False),
        ]
        constraints = []
        columns.extend(columns_ext)
        constraints.extend(constraints_ext)
        super().__init__(db_table_name, columns, constraints)


class Core02LexOptiGoalTable(ScenarioDbTable):
    def __init__(self, db_table_name: str = 'lex_opti_goal', columns_ext: List[Column] = [], constraints_ext: List[ForeignKeyConstraint] = []):
        columns = [
            Column('lexOptiGoalId', String(256), primary_key=True),
            Column('lexOptiLevelId', String(256), primary_key=False),
            Column('weight', Float(), primary_key=False),
            Column('isActive', Boolean(), primary_key=False),
        ]
        constraints = [
            ForeignKeyConstraint(['lexOptiLevelId'], ['lex_opti_level.lexOptiLevelId']),
        ]
        columns.extend(columns_ext)
        constraints.extend(constraints_ext)
        super().__init__(db_table_name, columns, constraints)


# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#  Output Tables
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class Core02LexOptiMetricsTable(ScenarioDbTable):
    def __init__(self, db_table_name: str = 'lex_opti_metrics', columns_ext: List[Column] = [], constraints_ext: List[ForeignKeyConstraint] = []):
        columns = [
            Column('lexOptiLevelId', String(256), primary_key=True),
            Column('metricType', String(256), primary_key=True),
            Column('metricName', String(256), primary_key=True),
            Column('metricValue', Float(), primary_key=False),
            Column('metricTextValue', String(256), primary_key=False),
        ]
        constraints = [
            # ForeignKeyConstraint(['lexOptiLevelId'], ['lex_opti_level.lexOptiLevelId']),  #VT20221220 Do NOT enforce this constraint since the LexOptiLevel table may not exist and is dynamically generated
        ]
        columns.extend(columns_ext)
        constraints.extend(constraints_ext)
        super().__init__(db_table_name, columns, constraints)

# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
#  DB Manager
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
class Core02ScenarioDbManager(Core01ScenarioDbManager):
    """
    Note: we cannot have the __init__ add tables on top of tables defined in super(),
    otherwise, it will not be possible to replace/extend the individual tables.
    So we have to ensure we include all applicable input and output tables.
    """
    def __init__(self, input_db_tables: Dict[str, ScenarioDbTable]=None, output_db_tables: Dict[str, ScenarioDbTable]=None, 
                 credentials=None, schema: str = None, echo=False,
                 **kwargs):
        if input_db_tables is None:
            input_db_tables = OrderedDict([
                ('Parameter', ParameterTable()),
                ('LexOptiLevel', Core02LexOptiLevelTable()),
                ('LexOptiGoal', Core02LexOptiGoalTable()),
            ])
        if output_db_tables is None:
            output_db_tables = OrderedDict([
                ('kpis', KpiTable()),
                ('BusinessKPIs', BusinessKpiTable()),
                ('LexOptiMetrics', Core02LexOptiMetricsTable()),
            ])
        super().__init__(input_db_tables=input_db_tables, output_db_tables=output_db_tables, credentials=credentials, schema=schema, echo=echo, **kwargs)
