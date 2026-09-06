def all_results():
    """
    Returns a list of all available/possible results
    Subject to change in the future
    """  
    results_list = [
        "SPP","DownholeECD","FlowRateOut","HookLoad","SurfaceTorque",
        "BitDepth", "TD", "ChokeOpening", "DownholePressure", "ChokePressure",
        "FluidTemperatureOut", "WOB", "InstantaneousROP", "BopChokeOpening",
        "FlowRateIn", "TopOfStringVelocity", "SurfaceRPM", "ChokePumpFlowRateIn",
        "DrillstringTemperature", "TotalInfluxMass", "CalculatedPressureBottomHole",
        "CuttingsMassFractionTransient", "GasVolumeFraction", "DrillstringBucklingLimit",
        "FluidTemperatureIn", "AnnulusECD", "DrillstringTorqueLimit", "AnnulusTemperature",
        "DrillstringTension", "AnnulusFluidVelocity", "DrillstringFluidVelocity", "CuttingsBedHeight",
        "AnnulusDensity", "DrillstringTorque", "TotalMudLossMass", "Connection",
        "TopOfStringPosition", "ActivePitVolume", "ActivePitDensity", "ActivePitTemperature",
        "MainPitVolume", "MainPitDensity", "MainPitTemperature", "ReservePitVolume", 
        "ReservePitDensity", "ReservePitTemperature", "GasFlowRateOut", "DrillstringDensity",
        "CalculatedLiftPumpFlowRate", "RigChokeOpeningActual", "RigChokePressure", "KillPumpFlowRateInActual"
        ]
    return results_list

valid_results = [
        "SPP","DownholeECD","FlowRateOut","HookLoad","SurfaceTorque",
        "BitDepth", "TD", "ChokeOpening", "DownholePressure", "ChokePressure",
        "FluidTemperatureOut", "WOB", "InstantaneousROP", "BopChokeOpening",
        "FlowRateIn", "TopOfStringVelocity", "SurfaceRPM", "ChokePumpFlowRateIn",
        "DrillstringTemperature", "TotalInfluxMass", "CalculatedPressureBottomHole",
        "CuttingsMassFractionTransient", "GasVolumeFraction", "DrillstringBucklingLimit",
        "FluidTemperatureIn", "AnnulusECD", "DrillstringTorqueLimit", "AnnulusTemperature",
        "DrillstringTension", "AnnulusFluidVelocity", "DrillstringFluidVelocity", "CuttingsBedHeight",
        "AnnulusDensity", "DrillstringTorque", "TotalMudLossMass", "Connection",
        "TopOfStringPosition", "ActivePitVolume", "ActivePitDensity", "ActivePitTemperature",
        "MainPitVolume", "MainPitDensity", "MainPitTemperature", "DrillstringDensity",
        "ReservePitVolume", "ReservePitDensity", "ReservePitTemperature", "GasFlowRateOut",
        "CalculatedLiftPumpFlowRate", "RigChokeOpeningActual", "RigChokePressure", "KillPumpFlowRateInActual"
        ]

time_results = [
    'SPP', 'DownholeECD', 'FlowRateOut', 'HookLoad', 'SurfaceTorque', 'BitDepth', 'TD',
    'ChokeOpening', 'DownholePressure', 'ChokePressure', 'FluidTemperatureOut', 'WOB',
    'InstantaneousROP', 'FlowRateIn', 'TopOfStringVelocity', 'SurfaceRPM', "BopChokeOpening",
    'ChokePumpFlowRateIn', 'TotalInfluxMass', 'CalculatedPressureBottomHole',
    'FluidTemperatureIn', 'TotalMudLossMass', 'Connection', 'TopOfStringPosition',
    'ActivePitVolume', 'ActivePitDensity', 'ActivePitTemperature', 'MainPitVolume',
    'MainPitDensity', 'MainPitTemperature', 'ReservePitVolume', 'ReservePitDensity',
    'ReservePitTemperature', 'GasFlowRateOut',
    "CalculatedLiftPumpFlowRate", "RigChokeOpeningActual", "RigChokePressure", "KillPumpFlowRateInActual"]     

depth_results = [
    'DrillstringTemperature', 'CuttingsMassFractionTransient', 'GasVolumeFraction',
    'DrillstringBucklingLimit', 'AnnulusECD', 'DrillstringTorqueLimit', 'AnnulusTemperature',
    'DrillstringTension', 'AnnulusFluidVelocity', 'DrillstringFluidVelocity',
    'CuttingsBedHeight', 'DrillstringDensity', 'AnnulusDensity', 'DrillstringTorque'
]

class Results():
    """
    This is a class property for the results
    """
    def __init__(self):
        self.SPP = dict()
        self.DownholeECD = dict()
        self.FlowRateOut = dict()
        self.HookLoad = dict()
        self.SurfaceTorque = dict()
        self.BitDepth = dict()
        self.TD = dict()
        self.ChokeOpening = dict()
        self.BopChokeOpening = dict()
        self.DownholePressure = dict()
        self.ChokePressure = dict()
        self.FluidTemperatureOut = dict()
        self.WOB = dict()
        self.InstantaneousROP = dict()
        self.FlowRateIn = dict()
        self.TopOfStringVelocity = dict()
        self.SurfaceRPM = dict()
        self.ChokePumpFlowRateIn = dict()
        self.Connection = dict()
        self.TopOfStringPosition = dict()
        self.ActivePitVolume = dict()
        self.ActivePitDensity = dict()
        self.ActivePitTemperature = dict()
        self.MainPitVolume = dict()
        self.MainPitDensity = dict()
        self.MainPitTemperature = dict()
        self.ReservePitVolume = dict()
        self.ReservePitDensity = dict()
        self.ReservePitTemperature = dict()
        self.GasFlowRateOut = dict()

        self.DrillstringTemperature = dict()
        self.TotalInfluxMass = dict()
        self.CalculatedPressureBottomHole = dict() #BHP
        self.CuttingsMassFractionTransient = dict()
        self.GasVolumeFraction = dict()
        self.DrillstringBucklingLimit = dict()
        self.DrillstringTorqueLimit = dict()
        self.FluidTemperatureIn = dict()
        self.AnnulusECD = dict()
        self.AnnulusTemperature = dict()
        self.AnnulusDensity = dict()
        self.DrillstringFluidVelocity = dict()
        self.CuttingsBedHeight = dict()
        self.DrillstringTorque = dict()
        self.TotalMudLossMass = dict()
        self.BopChokePressure = dict()
        self.AnnulusFluidVelocity = dict()
        self.DrillstringTension = dict()
        self.DrillstringDensity = dict()
        
        self.CalculatedLiftPumpFlowRate = dict()
        self.RigChokePressure = dict()
        self.RigChokeOpeningActual = dict()
        self.KillPumpFlowRateInActual = dict()
        
    @property
    def SPP(self): return self._SPP
    @SPP.setter
    def SPP(self, value): self._SPP = value
    
            
    @property
    def CalculatedLiftPumpFlowRate(self): return self._CalculatedLiftPumpFlowRate
    @CalculatedLiftPumpFlowRate.setter
    def CalculatedLiftPumpFlowRate(self, value): self._CalculatedLiftPumpFlowRate = value    
        
    @property
    def RigChokePressure(self): return self._RigChokePressure
    @RigChokePressure.setter
    def RigChokePressure(self, value): self._RigChokePressure = value
        
    @property
    def RigChokeOpeningActual(self): return self._RigChokeOpeningActual
    @RigChokeOpeningActual.setter
    def RigChokeOpeningActual(self, value): self._RigChokeOpeningActual = value   

    @property
    def KillPumpFlowRateInActual(self): return self._KillPumpFlowRateInActual
    @KillPumpFlowRateInActual.setter
    def KillPumpFlowRateInActual(self, value): self._KillPumpFlowRateInActual = value
    
    @property
    def DownholeECD(self): return self._DownholeECD
    @DownholeECD.setter
    def DownholeECD(self, value): self._DownholeECD = value
    
    @property
    def SurfaceTorque(self): return self._SurfaceTorque
    @SurfaceTorque.setter
    def SurfaceTorque(self, value): self._SurfaceTorque = value

    @property
    def TD(self): return self._TD
    @TD.setter
    def TD(self, value): self._TD = value

    @property
    def BitDepth(self): return self._BitDepth
    @BitDepth.setter
    def BitDepth(self, value): self._BitDepth = value
        
    @property
    def DownholePressure(self): return self._DownholePressure
    @DownholePressure.setter
    def DownholePressure(self, value): self._DownholePressure = value

    @property
    def FlowRateOut(self): return self._FlowRateOut
    @FlowRateOut.setter
    def FlowRateOut(self, value): self._FlowRateOut = value

    @property
    def HookLoad(self): return self._HookLoad
    @HookLoad.setter
    def HookLoad(self, value): self._HookLoad = value

    @property
    def ChokePressure(self): return self._ChokePressure
    @ChokePressure.setter
    def ChokePressure(self, value): self._ChokePressure = value

    @property
    def FluidTemperatureOut(self): return self._FluidTemperatureOut
    @FluidTemperatureOut.setter
    def FluidTemperatureOut(self, value): self._FluidTemperatureOut = value

    @property
    def WOB(self): return self._WOB
    @WOB.setter
    def WOB(self, value): self._WOB = value

    @property
    def InstantaneousROP(self): return self._InstantaneousROP
    @InstantaneousROP.setter
    def InstantaneousROP(self, value): self._InstantaneousROP = value

    @property
    def FlowRateIn(self): return self._FlowRateIn
    @FlowRateIn.setter
    def FlowRateIn(self, value): self._FlowRateIn = value

    @property
    def TopOfStringVelocity(self): return self._TopOfStringVelocity
    @TopOfStringVelocity.setter
    def TopOfStringVelocity(self, value): self._TopOfStringVelocity = value

    @property
    def SurfaceRPM(self): return self._SurfaceRPM
    @SurfaceRPM.setter
    def SurfaceRPM(self, value): self._SurfaceRPM = value

    @property
    def ChokePumpFlowRateIn(self): return self._ChokePumpFlowRateIn
    @ChokePumpFlowRateIn.setter
    def ChokePumpFlowRateIn(self, value): self._ChokePumpFlowRateIn = value

    @property
    def ChokeOpening(self): return self._ChokeOpening
    @ChokeOpening.setter
    def ChokeOpening(self, value): self._ChokeOpening = value

    @property
    def BopChokeOpening(self): return self._BopChokeOpening
    @BopChokeOpening.setter
    def BopChokeOpening(self, value): self._BopChokeOpening = value
        
    @property
    def GasFlowRateOut(self): return self._GasFlowRateOut
    @GasFlowRateOut.setter
    def GasFlowRateOut(self, value): self._GasFlowRateOut = value

    @property
    def DrillstringTemperature(self): return self._DrillstringTemperature
    @DrillstringTemperature.setter
    def DrillstringTemperature(self, value): self._DrillstringTemperature = value

    @property
    def TotalInfluxMass(self): return self._TotalInfluxMass
    @TotalInfluxMass.setter
    def TotalInfluxMass(self, value): self._TotalInfluxMass = value

    @property
    def CalculatedPressureBottomHole(self): return self._CalculatedPressureBottomHole
    @CalculatedPressureBottomHole.setter
    def CalculatedPressureBottomHole(self, value): self._CalculatedPressureBottomHole = value
    
    @property
    def CuttingsMassFractionTransient(self): return self._CuttingsMassFractionTransient
    @CuttingsMassFractionTransient.setter
    def CuttingsMassFractionTransient(self, value): self._CuttingsMassFractionTransient = value

    @property
    def GasVolumeFraction(self): return self._GasVolumeFraction
    @GasVolumeFraction.setter
    def GasVolumeFraction(self, value): self._GasVolumeFraction = value

    @property
    def DrillstringBucklingLimit(self): return self._DrillstringBucklingLimit
    @DrillstringBucklingLimit.setter
    def DrillstringBucklingLimit(self, value): self._DrillstringBucklingLimit = value

    @property
    def FluidTemperatureIn(self): return self._FluidTemperatureIn
    @FluidTemperatureIn.setter
    def FluidTemperatureIn(self, value): self._FluidTemperatureIn = value

    @property
    def AnnulusECD(self): return self._AnnulusECD
    @AnnulusECD.setter
    def AnnulusECD(self, value): self._AnnulusECD = value

    @property
    def DrillstringTorqueLimit(self): return self._DrillstringTorqueLimit
    @DrillstringTorqueLimit.setter
    def DrillstringTorqueLimit(self, value): self._DrillstringTorqueLimit = value

    @property
    def AnnulusTemperature(self): return self._AnnulusTemperature
    @AnnulusTemperature.setter
    def AnnulusTemperature(self, value): self._AnnulusTemperature = value

    @property
    def DrillstringTension(self): return self._DrillstringTension
    @DrillstringTension.setter
    def DrillstringTension(self, value): self._DrillstringTension = value

    @property
    def DrillstringDensity(self): return self._DrillstringDensity
    @DrillstringDensity.setter
    def DrillstringDensity(self, value): self._DrillstringDensity = value

    @property
    def AnnulusFluidVelocity(self): return self._AnnulusFluidVelocity
    @AnnulusFluidVelocity.setter
    def AnnulusFluidVelocity(self, value): self._AnnulusFluidVelocity = value

    @property
    def DrillstringFluidVelocity(self): return self._DrillstringFluidVelocity
    @DrillstringFluidVelocity.setter
    def DrillstringFluidVelocity(self, value): self._DrillstringFluidVelocity = value

    @property
    def CuttingsBedHeight(self): return self._CuttingsBedHeight
    @CuttingsBedHeight.setter
    def CuttingsBedHeight(self, value): self._CuttingsBedHeight = value

    @property
    def AnnulusDensity(self): return self._AnnulusDensity
    @AnnulusDensity.setter
    def AnnulusDensity(self, value): self._AnnulusDensity = value

    @property
    def DrillstringTorque(self): return self._DrillstringTorque
    @DrillstringTorque.setter
    def DrillstringTorque(self, value): self._DrillstringTorque = value

    @property
    def TotalMudLossMass(self): return self._TotalMudLossMass
    @TotalMudLossMass.setter
    def TotalMudLossMass(self, value): self._TotalMudLossMass = value

    @property
    def Connection(self): return self._Connection
    @Connection.setter
    def Connection(self, value): self._Connection = value

    @property
    def TopOfStringPosition(self): return self._TopOfStringPosition
    @TopOfStringPosition.setter
    def TopOfStringPosition(self, value): self._TopOfStringPosition = value

    @property
    def ActivePitVolume(self): return self._ActivePitVolume
    @ActivePitVolume.setter
    def ActivePitVolume(self, value): self._ActivePitVolume = value
    
    @property
    def ActivePitDensity(self): return self._ActivePitDensity
    @ActivePitDensity.setter
    def ActivePitDensity(self, value): self._ActivePitDensity = value

    @property
    def ActivePitTemperature(self): return self._ActivePitTemperature
    @ActivePitTemperature.setter
    def ActivePitTemperature(self, value): self._ActivePitTemperature = value

    @property
    def MainPitVolume(self): return self._MainPitVolume
    @MainPitVolume.setter
    def MainPitVolume(self, value): self._MainPitVolume = value
    
    @property
    def MainPitDensity(self): return self._MainPitDensity
    @MainPitDensity.setter
    def MainPitDensity(self, value): self._MainPitDensity = value

    @property
    def MainPitTemperature(self): return self._MainPitTemperature
    @MainPitTemperature.setter
    def MainPitTemperature(self, value): self._MainPitTemperature = value

    @property
    def ReservePitVolume(self): return self._ReservePitVolume
    @ReservePitVolume.setter
    def ReservePitVolume(self, value): self._ReservePitVolume = value
    
    @property
    def ReservePitDensity(self): return self._ReservePitDensity
    @ReservePitDensity.setter
    def ReservePitDensity(self, value): self._ReservePitDensity = value

    @property
    def ReservePitTemperature(self): return self._ReservePitTemperature
    @ReservePitTemperature.setter
    def ReservePitTemperature(self, value): self._ReservePitTemperature = value
