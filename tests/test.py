# from dse_do_utils.datamanager import DataManager
# from dse_do_utils.optimizationengine import OptimizationEngine
# from dse_do_utils.scenariomanager import ScenarioManager

from dse_do_utils import DataManager
from dse_do_utils import OptimizationEngine
from dse_do_utils import ScenarioManager
# from dse_do_utils import ScenarioPicker
import pandas as pd
from datetime import datetime

df = pd.DataFrame({'param':['horizon_start_time', 'test_bool', 'test_int', 'test_float', 'test_str'], 'value':['2019-01-01 00:01', 'F', '1.1', '1.25', 'hello world']}).set_index(['param'])
test_bool = DataManager.get_parameter_value(df, 'test_bool', param_type='bool', default_value=True)
test_int = DataManager.get_parameter_value(df, 'test_int', param_type='int', default_value=0)
test_float = DataManager.get_parameter_value(df, 'test_float', param_type='float', default_value=0.123)
test_str = DataManager.get_parameter_value(df, 'test_str', param_type='str', default_value='hw')
horizon_start_time = DataManager.get_parameter_value(df, 'horizon_start_time', param_type='datetime', default_value='2019-01-01 00:00')

assert test_bool == False
assert test_int == 1
assert test_float == 1.25
assert test_str == 'hello world'
assert isinstance(test_bool, bool)
assert isinstance(test_int, int)
assert isinstance(test_str, str)
assert isinstance(horizon_start_time, datetime)
assert isinstance(horizon_start_time, datetime)