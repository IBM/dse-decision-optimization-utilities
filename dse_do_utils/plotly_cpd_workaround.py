# Copyright IBM All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import plotly
import plotly.graph_objs as go
from IPython.display import display, HTML


def _show(self):
    """Work-around for showing a Plotly go.Figure in JupyterLab in CPD 3.5
    Usage:
        1. `import plotly_cpd_workaround`. This will run this code and add the custom method `_show()` to `go.Figure`
        2. Create a go.Figure fig in the normal Plotly way. Then in the last line of the cell, instead of `fig.show()`, do a:
        3. `fig._show()`
    """
    html = plotly.io.to_html(self)
    display(HTML(html))


go.Figure._show = _show
