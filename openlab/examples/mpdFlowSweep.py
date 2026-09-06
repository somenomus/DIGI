import openlab
import numpy
import os
import time
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

#%% Get login data from the web client to get a valid token
username=""
apikey=""
licenseguid=""

#%% Login and setup client
session = openlab.http_client(username=username, apikey=apikey, licenseguid=licenseguid, environment="prod")

#%% Configuration and simulation name. Set initial bit depth corresponding to the total well length 
config_name = "test"
sim_name = "Simulation from Python"
initial_depth = 2500

#%% PI controller settings
referenceBHPPressure = 380 *1E5 # Pa
initialOutput = 0.25 # 0 = closed , 1 = open

kp = 5e-8 # first try for tuning the pi controller
ti = 10
ts = 1
referenceMaxRateOfChange = 1E5 # Reference value is rate limited
isReversed = 1; # true or false
minOutput = 0;
maxOutput = 1;
pi = openlab.piController.Controller(kp, ti, ts, referenceBHPPressure,referenceMaxRateOfChange,initialOutput, isReversed, minOutput, maxOutput)

#%% Results we want 
tags=["SPP", "DownholeECD", "FlowRateOut", "ChokeOpening", "DownholePressure"]

#%% initialize simulation
sim = session.create_simulation(config_name,sim_name,2500)
timeStep = 1

#%% Run simulation
timeStep = 1
startTime = 1
endTime = 3000
stepDuration = 60 # Duration of each flow rate
rampStartTime = 100
rampValuesDown = numpy.arange(2500, 1500, -100)/60000
rampValuesUp = numpy.arange(1500,2600,100)/60000
flowrates = numpy.concatenate((rampValuesDown, rampValuesUp))

for timeStep in range(startTime,endTime):
    
    ts = time.time();
    
    sim.setpoints.UseContinuousCirculationSystem = True #To avoid stopping the pump during auto connections
    
    if timeStep>1000:
        referenceBHPPressure = 390 * 1E5 # Change reference bhp during the simulation
    
    if timeStep >= rampStartTime:
        if timeStep == rampStartTime:
            #reset PI controller before usage, set reference value and initial output = initial choke opening
            pi.reset(referenceBHPPressure, sim.results.ChokeOpening[timeStep-1])        
    
        index = int((timeStep - rampStartTime) / stepDuration)
        if index > len(flowrates) - 1:
            break
        flowRateIn = flowrates[index]
        chokeOpening = pi.getOutput(referenceBHPPressure,sim.results.DownholePressure[timeStep-1])

    else: #constant flow rate and choke opening
        flowRateIn =  flowrates[0] 
        chokeOpening = initialOutput

    #set setpoints 
    sim.setpoints.FlowRateIn = flowRateIn
    sim.setpoints.ChokeOpening = chokeOpening
    
    #step simulator
    sim.step(timeStep)         

    #ask results
    sim.get_results(timeStep,tags)    
    
    #advance the simulation    
    timeStep = timeStep + 1
    
    # print step duration
    print("Total step duration:", "{:.2f}".format(time.time() - ts), "s" )
    
    
#%%
#stop the sim once you have experimenting some with tuning the PI controller
sim.stop()