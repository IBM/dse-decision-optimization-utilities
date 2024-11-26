# Copyright IBM All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
from typing import Generic, TypeVar, Optional, Dict

import pandas as pd
import plotly.express as px
import plotly.graph_objs as go
# from typing import List, Dict, Tuple, Optional
from dse_do_utils.datamanager import DataManager, Inputs

# import plotly
# import plotly.graph_objs as go

# def _show(self):
#     """Work-around for showing a Plotly go.Figure in JupyterLab in CPD 3.5
#     Usage:
#         1. `import plotlymanager`. This will run this code and add the custom method `_show()` to `go.Figure`
#         2. Create a go.Figure fig in the normal Plotly way. Then in the last line of the cell, instead of `fig.show()`, do a:
#         3. `fig._show()`
#     """
#     from IPython.display import display, HTML  # Need to import dynamically. Otherwise problems running locally in pure Python (i.e. without Jupyter)
#     html = plotly.io.to_html(self)
#     display(HTML(html))
# go.Figure._show = _show

DM = TypeVar('DM', bound='DataManager')

class PlotlyManager(Generic[DM]):
    """Holds method that create Plotly charts.
    Pass-in the DM as an input in the constructor.
    """
    def __init__(self, dm: DM):
        self.dm: DM = dm

        # Used by DoDashApp for scenario compare, when the Reference Scenario is selected
        # This supports scenario compare visualizations
        self.ref_dm: Optional[DM] = None  # A DataManager based on the reference scenario
        # Used by the DoDashApp for scenario compare, when multiple scenarios are selected for compare
        # These DataFrames are 'multi-scenario': they have an additional colum with the scenarioName.
        # One 'multi-scenario' df contains data for the same scenario table from multiple scenarios
        self.ms_inputs: Dict[str, pd.DataFrame] = None  # Dict[TableName, 'multi-scenario' dataframe]
        self.ms_outputs: Dict[str, pd.DataFrame] = None  # Dict[TableName, 'multi-scenario' dataframe]

    def get_plotly_fig_m(self, id):
        """DEPRECATED. Not used in dse_do_dashboard package.
        On the instance `self`, call the method named by id['index']
        For use with pattern-matching callbacks. Assumes the id['index'] is the name of a method of this class and returns a fig.
        Used in dse_do_dashboard Plotly-Dash dashboards
        """
        return getattr(self, id['index'])()

    def get_dash_tab_layout_m(self, page_id):
        """DEPRECATED. Not used in dse_do_dashboard package.
        On the instance `self`, call the method named by get_tab_layout_{page_id}.
        Used in dse_do_dashboard Plotly-Dash dashboards
        """
        return getattr(self, f"get_tab_layout_{page_id}")()

    ###################################################################
    #  For scenario-compare in dse-do-dashboard
    ###################################################################
    def plotly_kpi_compare_bar_charts(self, figs_per_row: int = 3, orientation: str = 'v') -> [[go.Figure]]:
        """
        Generalized compare of KPIs between scenarios. Creates a list-of-list of go.Figure, i.e. rows of figures,
        for the PlotlyRowsVisualizationPage.
        Each KPI gets its own bar-chart, comparing the scenarios.

        Supports 3 cases:
            1. Multi-scenario compare based on the Reference Scenarios multi-checkbox select on the Home page.
            2. Compare the current select scenario with the Reference Scenario selected on the Home page.
            3. Single scenario view based on the currently selected scenario

        Args:
            figs_per_row: int - Maximum number of figures per row
            orientation: str - `h' (horizontal) or `v` (vertical)

        Returns:
            figures in rows ([[go.Figure]]) - bar-charts in rows

        """
        figs = []
        if self.get_multi_scenario_compare_selected():
            df = self.get_multi_scenario_table('kpis')
        elif self.get_reference_scenario_compare_selected():
            ref_df = self.ref_dm.kpis.reset_index()
            ref_df['scenario_name'] = 'Reference'
            selected_df = self.dm.kpis.reset_index()
            selected_df['scenario_name'] = 'Current'
            df = pd.concat([selected_df, ref_df])
        else:
            df = self.dm.kpis.reset_index()
            df['scenario_name'] = 'Current'

        for kpi_name, group in df.groupby('NAME'):
            labels = {'scenario_name': 'Scenario', 'VALUE': kpi_name}
            title = f'{kpi_name}'
            if orientation == 'v':
                fig = px.bar(group, x='scenario_name', y='VALUE', orientation='v', color='scenario_name', labels=labels,
                             title=title)
            else:
                fig = px.bar(group, y='scenario_name', x='VALUE', orientation='h', color='scenario_name',
                             labels=labels)
            fig.update_layout(xaxis_title=None)
            fig.update_layout(yaxis_title=None)
            fig.update_layout(showlegend=False)
            figs.append(fig)

        # Split list of figures in list-of-lists with maximum size of n:
        n = figs_per_row
        figs = [figs[i:i + n] for i in range(0, len(figs), n)]
        return figs

    def get_multi_scenario_compare_selected(self) -> bool:
        """Returns True if the user has selected multi-scenario compare.
        """
        ms_enabled = (isinstance(self.ms_outputs, dict)
                      and isinstance(self.ms_inputs, dict)
                      and 'Scenario' in self.ms_inputs.keys()
                      and self.ms_inputs['Scenario'].shape[0] > 0
                      )
        return ms_enabled

    def get_reference_scenario_compare_selected(self) -> bool:
        """Returns True if the user has selected (single) reference-scenario compare
        """
        ms_selected = self.get_multi_scenario_compare_selected()
        ref_selected = isinstance(self.ref_dm, DataManager)
        return not ms_selected and ref_selected

    def get_multi_scenario_table(self, table_name: str) -> Optional[pd.DataFrame]:
        """Gets the df from the table named `table_name` in either inputs or outputs.
        If necessary (i.e. when using scenario_seq), merges the Scenario table, so it has the scenario_name as column.
        DataFrame is NOT indexed!
        """
        if table_name in self.ms_inputs.keys():
            df = self.ms_inputs[table_name]
        elif table_name in self.ms_outputs.keys():
            df = self.ms_outputs[table_name]
        else:
            df = None

        if df is not None:
            if "scenario_name" not in df.columns:
                df = df.merge(self.ms_inputs['Scenario'], on='scenario_seq')  # Requires scenario_seq. Merges-in the scenario_name.

        return df