import openlab
import numpy
import os
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

#%% Get login data from the web client to get a valid token
username=""
apikey=""
licenseguid=""

#%% Login and setup client
session = openlab.http_client(username=username, apikey=apikey, licenseguid=licenseguid, environment="prod")

#%% Configuration and simulation name. Set initial bit depth corresponding to the total well length 
config_name = "test OWD"
sim_name = "Simulation from Python"
initial_depth = 4999

#%% PI controller settings
referenceBHPPressure = 990 *1E5 # Pa
initialLiftPumpFlowRate = 0
kp = 2e-9
ti = 7
ts = 1
referenceMaxRateOfChange =  1E5 # Reference value is rate limited
isReversed = 1 # true or false
minOutput = -7000/60000
maxOutput = 7000/60000
pi = openlab.piController.Controller(kp, ti, ts, referenceBHPPressure,referenceMaxRateOfChange,initialLiftPumpFlowRate, isReversed, minOutput, maxOutput)

#%% Results we want 
# Be sure that the correct drilling mode is chosen in the configuration: Open Water Drilling
# CalculatedLiftPumpFlowRate is not available for conventional and backpressure drilling and the simulation will then fail
tags=["SPP", "DownholeECD", "FlowRateOut", "CalculatedLiftPumpFlowRate", "DownholePressure"]

#%% Initialize simulation
sim = session.create_simulation(config_name,sim_name,initial_depth)

#%% Run flow sweep
timeStep = 1
startTime = 1
endTime = 3000
rampStartTime = 100
stepDuration = 60 # duration for each flow rate
rampValuesDown = numpy.arange(2500, 1500, -100)/60000
rampValuesUp = numpy.arange(1500,2600,100)/60000
flowrates = numpy.concatenate((rampValuesDown, rampValuesUp))


for timeStep in range(startTime,endTime):
    
    ts = time.time();
    
    sim.setpoints.UseContinuousCirculationSystem = True #To avoid stopping the pump during auto connections    
    
    if timeStep>600:
        referenceBHPPressure = 1000 * 1E5 # Change reference bhp during the simulation
    
    if timeStep >= rampStartTime:
        if timeStep == rampStartTime:
            #reset PI controller before usage, set reference value and initial output = initial choke opening
            pi.reset(referenceBHPPressure, sim.results.CalculatedLiftPumpFlowRate[timeStep-1])        
    
        index = int((timeStep - rampStartTime) / stepDuration)
        
        if index > len(flowrates) - 1:
            break   
        
        sim.setpoints.FlowRateIn = flowrates[index]
        sim.setpoints.LiftPumpFlowRate = pi.getOutput(referenceBHPPressure,sim.results.DownholePressure[timeStep-1])
        sim.setpoints.LiftPumpControlMode = 1

    else: #constant flow rate and choke opening
        sim.setpoints.FlowRateIn =  flowrates[0] 
        if timeStep > 1:
            sim.setpoints.LiftPumpFlowRate = sim.results.CalculatedLiftPumpFlowRate[timeStep-1]
        else:
            sim.setpoints.LiftPumpFlowRate = initialLiftPumpFlowRate
        sim.setpoints.LiftPumpControlMode = 0
    
    #step simulator
    sim.step(timeStep)         

    #ask results
    sim.get_results(timeStep,tags)    
    
    #advance the simulation    
    timeStep = timeStep + 1
    
    # print step duration
    print("Total step duration:", "{:.2f}".format(time.time() - ts), "s" )
    
    
#%% stop the sim once you have experimenting some with tuning the PI controller
sim.stop()