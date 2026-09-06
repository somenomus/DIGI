def all_setpoints():
    """
    DEPRECATED
    Returns a list of all available/possible setpoints
    Subject to change in the future
    """
    empty_setpoints = [
        "ChokeOpening", "FlowRateIn", "TopOfStringVelocity",
        "DesiredROP", "SurfaceRPM", "ChokePumpFlowRateIn", "BopChokeOpening",
        "MainPitActive", "MainPitReturn", "ControlActivePit",
        "ControlActivePitDensity", "ControlActivePitTemperature",
        "WOBAutoDriller", "DesiredWOB", "WOBProportionalGain",
        "WOBIntegralGain", "LiftPumpControlMode", "RigChokeOpening",
        "KillPumpFlowRateIn", "ChokelineValve", "KillineValve",
        "LiftPumpFlowRate", "SubsurfaceValve", "UseContinuousCirculationSystem"
    ]
    return empty_setpoints


valid_tags = [
    "BopChokeOpening", "ChokeOpening", "ChokePumpFlowRateIn", "ChokelineValve",
    "ControlMainPit", "ControlMainPitDensity", "ControlMainPitTemperature",
    "DesiredROP", "FlowRateIn", "HeaveAmplitude", "HeaveCompensation",
    "HeavePeriod", "KillPumpFlowRateIn", "KillineValve",
    "LiftPumpBHECDReference", "LiftPumpBHPReference", "LiftPumpControlMode",
    "LiftPumpDeltaPressure", "LiftPumpFlowRate", "LiftPumpIntegralTime",
    "LiftPumpPWDECDReference", "LiftPumpPWDReference", "LiftPumpPressure",
    "LiftPumpProportionalGain", "LiftPumpProportionalGainECD",
    "MPDControlMode", "MPDIntegralTime", "MPDProportionalGain",
    "MPDReferencePressure", "MWLiftPumpDeltaPressure", "MWLiftPumpFlowRate",
    "MWLiftPumpPressure", "MainPitMainPump", "MainPitReturn", "MudReturnValve",
    "RigChokeOpening", "RiserBoosterFlowRateIn", "RiserBoosterValve",
    "SurfaceRPM", "TopOfStringVelocity", "UseContinuousCirculationSystem",
    "WOBAutoDriller", "WOBIntegralTime", "WOBProportionalGain"
    ]


class Setpoints():
    """
    A class property for the setpoints
    """
    def __init__(self):
        self.ChokeOpening = 1  # 0=closed 1=Open
        self.FlowRateIn = 0
        self.TopOfStringVelocity = 0
        self.DesiredROP = 0
        self.SurfaceRPM = 0
        self.ChokePumpFlowRateIn = 0
        self.RiserBoosterFlowRateIn = 0
        self.RiserBoosterValve = 1
        self.BopChokeOpening = 1  # 0=closed 1=Open
        self.MainPitMainPump = True
        self.MainPitReturn = True  # bool
        self.ControlMainPit = False  # bool
        self.ControlMainPitDensity = 1500.0  # float
        self.ControlMainPitTemperature = 323.15  # float
        self.DensityIn = None
        self.WOBAutoDriller = False  # bool
        self.DesiredWOB = None  # float
        self.WOBProportionalGain = 0.00001  # float
        self.WOBIntegralTime = 10
        self.MPDReferencePressure = 1e5
        self.MPDProportionalGain = 5e-8
        self.MPDIntegralTime = 10
        self.MPDControlMode = 1       
        self.LiftPumpControlMode = 0  # float
        self.RigChokeOpening = 1.0  # float
        self.KillPumpFlowRateIn = 0  # float
        self.ChokelineValve = 0  # float
        self.KillineValve = 0  # float
        self.LiftPumpFlowRate = 0  # float
        self.UseContinuousCirculationSystem = False  # bool
        self.LiftPumpPressure = 1e5
        self.LiftPumpDeltaPressure = 0
        self.LiftPumpBHPReference = 100e5
        self.LiftPumpPWDReference = 100e5
        self.LiftPumpPWDECDReference = 1500
        self.LiftPumpBHECDReference = 1500
        self.LiftPumpProportionalGain = 0.5e-8
        self.LiftPumpProportionalGainECD = 0.75e-4
        self.LiftPumpIntegralTime = 7
        self.MWLiftPumpFlowRate = 0
        self.MWLiftPumpPressure = 1e5
        self.MWLiftPumpDeltaPressure = 0
        self.HeaveAmplitude = 0
        self.HeavePeriod = 30
        self.HeaveCompensation = 0.9
        self.MudReturnValve = 1

    def to_string(self):
        s = ""
        for t in valid_tags:
            s += f"\"{t}\":{getattr(self, t)}, "
        # Remove last comma and space
        return s[:-2]

    # SubsurfaceValve was renamed to MudReturnValve
    @property
    def SubsurfaceValve(self): return self.MudReturnValve
    @SubsurfaceValve.setter
    def SubsurfaceValve(self, value): self.MudReturnValve = value
