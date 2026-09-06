class ValidationError(Exception):
    """
    Raised when OpenLab Simulator returns 422 error code
    This happens when:
    * config/sim setpoints are out of simulator boundaries
    * Creating a configuration with name that already exists
    """
    def __init__(self, message):
        # Call the base class constructor with the parameters it needs
        super().__init__(message)
        self.message = message

class ConfigurationNotFound(Exception):
    """
    Raise when configuration is not found in OpenLab
    """
    def __init__(self, message):
        # Call the base class constructor with the parameters it needs
        super().__init__(message)
        self.message = message

class SimulationNotFound(Exception):
    """
    Raise when simulation is not found in OpenLab
    """
    def __init__(self, message):
        # Call the base class constructor with the parameters it needs
        super().__init__(message)
        self.message = message

class SimulationCompleted(Exception):
    """
    Raised when a running simulation is unexpectedly completed
    """
    def __init__(self, message):
        # Call the base class constructor with the parameters it needs
        super().__init__(message)
        self.message = message

class SimulationAborted(Exception):
    """
    Raised when a running simulation is unexpectedly aborted
    """
    def __init__(self, message):
        # Call the base class constructor with the parameters it needs
        super().__init__(message)
        self.message = message

class OpenlabTimeoutError(Exception):
    """
    Raised when:
    1) A created simulation hasn't switched to running after 30 seconds
    2) stepping or getting results takes more than the timeout specificed in Simulation. Default is 60 seconds
    """
    def __init__(self, message):
        # Call the base class constructor with the parameters it needs
        super().__init__(message)
        self.message = message

class UserLimitException(Exception):
    """
    Raised when attempting to do something that exceeds a user's limits set in a user's license
    To upgrade your limits, visit https://openlab.app
    """
    def __init__(self, message):
        # Call the base class constructor with the parameters it needs
        super().__init__(message)
        self.message = message