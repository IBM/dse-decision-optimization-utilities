#####################################################################
## Dummy dd_scenario module to fool Sphinx
#####################################################################

def Client(object):
    """Dummy class so that a `from dd_scenario import Client` will not cause a Python exception when
    generating Sphinx auto-documentation
    """

    def __init__(self):
        return