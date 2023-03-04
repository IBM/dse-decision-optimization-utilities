# Copyright IBM All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

from .version import __version__
from .datamanager import DataManager
from .optimizationengine import OptimizationEngine
from .scenariomanager import ScenarioManager
from .scenariodbmanager import ScenarioDbManager
# from .scenariopicker import ScenarioPicker
# from .deployeddomodel import DeployedDOModel
# from .mapmanager import MapManager

name = "dse_do_utils"


def module_reload():
    """DEPRECATED. Requires updates to Python 3.6
    Reloads all component modules. Use when you want to force a reload of this module with imp.reload().

    This avoids having to code somewhat complex reloading logic in the notebook that is using this module.

    Challenge with imp.reload of dse-do_utils. The following is NOT (!) sufficient::

        import imp
        import dse_do_utils
        imp.reload(dse_do_utils)

    The package dse_do_utils internally contains a number of sub modules that each contain a part of the code.
    This keeps development easier and more organized. But to make importing easier, the classes are exposed
    in the top level `init.py`, which allows for a simple import statement like from dse_do_utils import ScenarioManager.
    Unfortunately, reloading the top-level module dse_do_utils doesn't force a reload of the internal modules.

    In case of subclassing, reloading needs to be done in the right order, i.e. first the parent classes.

    Usage::

        import imp
        import dse_do_utils  # You have to do the import, otherwise not possible to do the next 2 steps
        dse_do_utils.module_reload()  #This function
        imp.reload(dse_do_utils)  # Necessary to ensure all following expressions `from dse_do_utils import class` are using the updated classes
        from dse_do_utils import DataManager, OptimizationEngine, ScenarioManager, ScenarioPicker, DeployedDOModel, MapManager  # This needs to be done AFTER the reload to refresh the definitions


    Note that this function assumes that the set of classes and component modules is not part of the update.
    If it is, you may need to add another reload::

        import imp
        import dse_do_utils  # You have to do the import, otherwise not possible to do the next 2 steps
        imp.reload(dse_do_utils)  # To reload this function
        dse_do_utils.module_reload()  #This function
        imp.reload(dse_do_utils)  # Necessary to ensure all future expressions `from dse_do_utils import class` are using the updated classes
        from dse_do_utils import DataManager, OptimizationEngine, ScenarioManager, ScenarioPicker, DeployedDOModel, MapManager  # This needs to be done AFTER the reload to refresh the definitions


    If not using this function, in the notebook you would need to do the following (or the relevant parts of it)::

        import imp
        import dse_do_utils
        imp.reload(dse_do_utils.datamanager)
        imp.reload(dse_do_utils.optimizationengine)
        imp.reload(dse_do_utils.scenariomanager)
        imp.reload(dse_do_utils.scenariopicker)
        imp.reload(dse_do_utils.deployeddomodel)
        imp.reload(dse_do_utils.mapmanager)
        imp.reload(dse_do_utils)
        from dse_do_utils import DataManager, OptimizationEngine, ScenarioManager, ScenarioPicker, DeployedDOModel, MapManager

    Returns:

    """
    import importlib
    import datamanager
    import optimizationengine
    import scenariomanager
    import scenariopicker
    import deployeddomodel
    import mapmanager
    import multiscenariomanager
    importlib.reload(datamanager)
    importlib.reload(optimizationengine)
    importlib.reload(scenariomanager)
    importlib.reload(scenariopicker)
    importlib.reload(deployeddomodel)
    importlib.reload(mapmanager)
    importlib.reload(multiscenariomanager)

    # The imports below cannot be done here.
    # You need to redo the class imports from the notebook that is calling this function

    # from .version import __version__
    # from .datamanager import DataManager
    # from .optimizationengine import OptimizationEngine
    # from .scenariomanager import ScenarioManager
    # from .scenariopicker import ScenarioPicker
    # from .deployeddomodel import DeployedDOModel
    # from .mapmanager import MapManager
