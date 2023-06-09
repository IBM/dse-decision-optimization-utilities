# Copyright IBM All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
from typing import Generic, TypeVar

# from typing import List, Dict, Tuple, Optional
from dse_do_utils.datamanager import DataManager

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