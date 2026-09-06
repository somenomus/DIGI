"""
Simulation that sweeps flow rate while maintaining constant BHP by adjusting the choke opening with a PI Controller
"""
import openlab
import time
import numpy
import matplotlib.pyplot as plt


username=""
apikey=""
licenseguid=""

config_name = "test"
INITIAL_BIT_DEPTH= 2500

# results we want 
tags=["SPP", "DownholeECD", "FlowRateOut", "ChokeOpening", "DownholePressure"]

#create new client session
session = openlab.http_client(username=username, apikey=apikey, licenseguid=licenseguid, environment="prod")

PLOT = False

#Ramp settings
rampIndex = 0
rampValuesDown = numpy.arange(2500, 1400, -100)/60000
rampValuesUp = numpy.arange(1500,2600,100)/60000
rampValues = numpy.concatenate((rampValuesDown, rampValuesUp))
rampStepDuration = 30 #seconds
rampStartTime = 100 #seconds
rampTimeSteps =numpy.arange(rampStartTime, rampValues.shape[0]*rampStepDuration-1+rampStartTime,rampStepDuration)
#print("{:.4f}".format(rampValues))

#-1 gets last value
maxTimeSteps = rampTimeSteps[-1]+rampStepDuration 
#PI controller settings
#PI controller settings
referenceBHPPressure = 380 *1E5 # Pa
initialChokeOpening = 0.25 # 0 = closed , 1 = open

kp = 5e-8 # first try for tuning the pi controller
ti = 10
ts = 1
referenceMaxRateOfChange = 0.1
isReversed = 1; # true or false
minOutput = 0;
maxOutput = 1;
pi = openlab.piController.Controller(kp, ti, ts, referenceBHPPressure,referenceMaxRateOfChange,initialChokeOpening, isReversed, minOutput, maxOutput)

#units
FLOW_UNIT_CONV_FACTOR= 1.66666667 * 0.00001#float("10e-5") # l/min --> m^3/s
PRESSURE_CONV_FACTOR= 100000.0 # float("10e5") # bar-->pascal

sim_name= "Python sweep simulation"
print("Configuration ID: " + session.configuration_id(config_name))
print("Simulation name : " + sim_name)
print("Initializing Simulation...")

#initialize and run the sim
sim = session.create_simulation(config_name,sim_name,2500)

#configure plot 
plt.show()
fig, ((plot_q, plot_choke), (plot_bhp,plot_spp)) = plt.subplots(2, 2,sharex=True)

plot_q.set_xlim(0,maxTimeSteps)
plot_bhp.set_xlim(0,maxTimeSteps)
plot_q.set_ylim(0,3000) #3000 l/min
plot_choke.set_ylim(0,1)   #fraction
plot_bhp.set_ylim(0,500) #500 bar
plot_spp.set_ylim(0,500) #500 bar

plot_q.set_title('Flow Rate Out (l/min)')
plot_choke.set_title('Choke Opening')
plot_bhp.set_title('Downhole Pressure(bar)')
plot_spp.set_title('SPP (bar)')
plot_bhp.set_xlabel('Time Step (seconds)')
plot_spp.set_xlabel('Time Step (seconds)')

#empty lists for plots
steps_ = list()
spps_ = list()
qs_= list()
chokes_= list()
ps_ = list()

print("--------------------------------Simulation started-------------------------")
for timeStep in range(1,maxTimeSteps):
    
    if timeStep >= rampStartTime: # flow sweep and PI control of the choke
        if rampIndex < rampTimeSteps.shape[0]-1 and rampIndex < rampValues.shape[0]-1:
            if timeStep >= rampTimeSteps[rampIndex] and timeStep < rampTimeSteps[rampIndex+1]:
                flowRateIn = rampValues[rampIndex]
                print("FlowRateIn: {:.4f} @ timeStep:{}".format(flowRateIn,timeStep))
                if timeStep == rampTimeSteps[rampIndex]:
                    rampIndex = rampIndex+1
        elif rampIndex == rampTimeSteps.shape[0] and rampIndex == rampValues.shape[0]: 
            flowRateIn = rampValues[rampIndex]
            plot_q.set_title("Set Point : {:.4f}".format(flowRateIn))
    
        if timeStep == rampStartTime:
            #reset PI controller before usage, set reference value and initial output = initial choke opening
            pi.reset(referenceBHPPressure, sim.results.ChokeOpening[timeStep-1])
        
        chokeOpening = pi.getOutput(referenceBHPPressure,sim.results.DownholePressure[timeStep-1])

    else: #constant flow rate and choke opening
        flowRateIn = rampValues[0]
        chokeOpening = initialChokeOpening

    #set setpoints 
    sim.setpoints.FlowRateIn = flowRateIn
    sim.setpoints.ChokeOpening = chokeOpening
    
    #step simulator
    sim.step(timeStep)         

    #ask results
    sim.get_results(timeStep,tags)

    #plot  
    if PLOT:
        steps_.append(timeStep)
        spps_.append(sim.results.SPP[timeStep]/PRESSURE_CONV_FACTOR)
        ps_.append(sim.results.DownholePressure[timeStep]/PRESSURE_CONV_FACTOR)
        qs_.append(sim.results.FlowRateOut[timeStep]/FLOW_UNIT_CONV_FACTOR)
        chokes_.append(sim.results.ChokeOpening[timeStep])
        
        #check if plot is still open
        if plt.fignum_exists(fig.number):
            plot_q.plot(steps_,qs_,'b-')
            plot_choke.plot(steps_,chokes_,'b-')
            plot_bhp.plot(steps_,ps_,'b-')
            plot_spp.plot(steps_,spps_,'b-')
            plt.pause(1e-17)
    
    #advance the simulation    
    timeStep = timeStep + 1

#end the simulation
sim.stop()