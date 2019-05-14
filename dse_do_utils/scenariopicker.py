# Copyright IBM All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

# -----------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------
# ScenarioPicker
# -----------------------------------------------------------------------------------
# -----------------------------------------------------------------------------------
# from IPython.display import Javascript, display
# from ipywidgets import widgets

from dse_do_utils import ScenarioManager


class ScenarioPicker(object):
    """Notebook widget to interactively select a scenario from the dd_scenario.Client.

    Usage

    Cell 1::

        sp = ScenarioPicker(model_name = 'My_DO_Model')
        sp.get_scenario_picker_ui()

    Cell 2::

        inputs, outputs = sp.load_selected_scenario_data()

    Create a ScenarioPicker and pass the model name.
    The API `get_scenario_picker_ui()` returns a widget with a drop-down box with the available scenarios.
    In addition, there is a Refresh button that will run all cells below this cell.
    The next cell should reload the scenario data.
    The API `load_selected_scenario_data()` is a convenience method that internally uses a ScenarioManager to load
    the data from the DO scenario.

    The selection of the scenario is maintained in the class variable ScenarioPicker.default_scenario.
    Therefore, a re-run of the cell keeps the last selected value.
    By adding::

        ScenarioPicker.default_scenario = 'my_default_scenario'

    before the creation of the scenario picker, one can force the default scenario to an initial value.
    """

    default_scenario = None  # Class variable to store the latest scenario selected

    from ipywidgets import widgets

    class ScenarioRefreshButton(widgets.Button):
        """A widget Refresh button that will refresh all cells below.
        Inner class of ScenarioPicker since it is only applicable in the context of the ScenarioPicker."""

        def __init__(self, scenario_picker):
            super(ScenarioPicker.ScenarioRefreshButton, self).__init__(description="Refresh")
            self.scenario_picker = scenario_picker
            self.on_click(ScenarioPicker.ScenarioRefreshButton._on_click_callback)

        @staticmethod
        def _on_click_callback(button):
            """Callback for Refresh button"""
            sp = button.scenario_picker
            ScenarioPicker.default_scenario = sp.get_selected_scenario()
            ScenarioPicker.ScenarioRefreshButton._refresh_cells_below()
            print("Set ScenarioPicker.default_scenario to {}".format(ScenarioPicker.default_scenario))

        @staticmethod
        def _refresh_cells_below():
            """Executes all cells below the current. Triggered by Refresh button."""
            #             display(Javascript('IPython.notebook.execute_cell_range(IPython.notebook.get_selected_index()+1, IPython.notebook.ncells())')) #Runs all cells below the cell with the refresh button
            from IPython.display import Javascript, display
            display(
                Javascript('IPython.notebook.execute_cells_below()'))  # Will also run the cell with the refresh button

    def __init__(self, model_name=None, scenario_name=None):
        self.model_name = model_name
        self.scenario_name = scenario_name
        self.selected_scenario = None

    def _get_scenario_names(self):
        '''Return a list of scenario names'''
        client = ScenarioManager._get_dd_client()
        dd_model_builder = client.get_model_builder(name=self.model_name)
        if dd_model_builder is None:
            raise ValueError('No DO model with name {}'.format(self.model_name))
        scenarios = dd_model_builder.get_containers(category='scenario')
        scenario_names = [sc['name'] for sc in scenarios]  # Get only the name property of the scenario tuple
        return scenario_names

    def get_scenario_select_drop_down(self):
        """Return the drop-down button."""
        self.drop_down = widgets.Dropdown(
            options=self._get_scenario_names(),
            value=self._get_default_scenario(),  # None, #DEFAULT_SCENARIO, #the default selected value
            description='Scenario:',
            disabled=False,
        )
        self.drop_down.observe(ScenarioPicker._drop_down_on_change)
        return self.drop_down

    @staticmethod
    def _drop_down_on_change(change):
        """Callback for the on-change event of the drop-down button.
        Sets the current value of the selection in the class variable ScenarioPicker.default_scenario,
        so that this selection is retained when re-running the notebook.
        See https://stackoverflow.com/questions/34020789/ipywidgets-dropdown-widgets-what-is-the-onchange-event
        """
        if change['type'] == 'change' and change['name'] == 'value':
            # print ("changed to {}".format(change['new']))
            ScenarioPicker.default_scenario = change['new']

    def get_selected_scenario(self):
        """Return the name of the selected scenario"""
        return self.drop_down.value

    def get_scenario_refresh_button(self):
        """Return an instance of the Refresh button."""
        self.button = ScenarioPicker.ScenarioRefreshButton(self)  # widgets.Button(description="Refresh")
        return self.button

    def get_scenario_picker_ui(self):
        """Return a combination of both the drop-down and the refresh button."""
        tab = widgets.HBox(children=[self.get_scenario_select_drop_down(), self.get_scenario_refresh_button()])
        return tab

    def _get_default_scenario(self):
        """Return the name of the scenario that should be selected by default. Return `None` if no default.
        Makes sure the default is one of the available scenarios.
        Returns:
            The name of the default scenario. Or None if no default.
        """
        scenario_names = self._get_scenario_names()
        default_scenario = ScenarioPicker.default_scenario
        if default_scenario is None or default_scenario not in scenario_names:
            if self.scenario_name is not None and self.scenario_name in scenario_names:
                default_scenario = self.scenario_name
                # print("Warning: ScenarioPicker.default_scenario named `{}` does not exist and replaced by {}".format(ScenarioPicker.default_scenario, self.scenario_name))
            else:
                default_scenario = None
                print("Warning: ScenarioPicker.default_scenario named `{}` does not exist".format(
                    ScenarioPicker.default_scenario))
        return default_scenario

    def load_selected_scenario_data(self):
        """Convenience method. Creates a ScenarioManager and loads input and output data from the scenario
        selected by the picker.
        Returns:
            A tuple with the (inputs, outputs) data
        """
        scenario_name = self.get_selected_scenario()
        if scenario_name is not None:
            print("Loading scenario {}".format(scenario_name))
            sm = ScenarioManager(model_name=self.model_name, scenario_name=scenario_name)
            inputs, outputs = sm.load_data()
        else:
            raise ValueError('No scenario selected.')
        return (inputs, outputs)