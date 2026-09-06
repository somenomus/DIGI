"""
A simple drilling simulation that increases the RPM by 20 every 30 steps 
"""
import openlab
import numpy 

config_name = "PUT CONFIGURATION NAME HERE"
sim_name = "Simple Python Simulation"
initial_bit_depth = 2500

session = openlab.http_client()
sim = session.create_simulation(config_name, sim_name,initial_bit_depth)

#this is how setpoints set. the sim.step() method handles getting the setpoints at every step
sim.setpoints.RPM = 0 #Hz
sim.setpoints.DesiredROP = 0.02 #m/s
sim.setpoints.TopOfStringVelocity = 0.02
sim.setpoints.FlowRateIn = 2500 / 60000 #60000 is to convert m^3/s

#number of steps to take
maxSimulationSteps = 1000

#sweep Values
rpmValues = numpy.arange(20,160,20) #won't include the endpoint i.e. this will be 0 : 120
rpmStepDuration = 30 #seconds

#"jsonify" the np.array
rpmValuesList = rpmValues.tolist()

rpmIndex = 0

#calculate the times to change RPMs
stepTimes = list()
for i in range(rpmValues.shape[0]):
    if i == 0:
        stepTimes.append(rpmStepDuration)
    else:
        stepTimes.append(stepTimes[i-1]+rpmStepDuration)  

#results we want
tags = ["SPP", "DownholePressure", "InstantaneousROP", "BitDepth", "WOB", "SurfaceTorque"]

#calculate the necessary simulation duration
simulationDuration = stepTimes[-1]+rpmStepDuration

if simulationDuration > maxSimulationSteps:
    simulationDuration = maxSimulationSteps

numerator = 0
old_timeStep = 1

print("--------------------------------Simulation started-------------------------")
for timeStep in range(1, simulationDuration+1):
    if timeStep == stepTimes[rpmIndex] or timeStep == simulationDuration:
        if rpmIndex > 0: #ignore first interval
            time_interval = timeStep - old_timeStep
            if time_interval > 0: #don't divide by 0
                average_torque = numerator/time_interval
                print("Average Torque for time interval {} - {} and {} RPM was {} N*m".format(
                    old_timeStep, timeStep, round(sim.setpoints.SurfaceRPM*60), round(average_torque)))
                numerator = 0 # reset numerator
            else:
                numerator = 0 #reset
        
        if rpmIndex < len(stepTimes):
            sim.setpoints.SurfaceRPM = rpmValuesList[rpmIndex]/60 #Set new rpm setpoint
            if rpmIndex < len(stepTimes) - 1:
                rpmIndex = rpmIndex + 1

        old_timeStep = timeStep # reset old timestep 
        
    #step
    sim.step(timeStep)

    #get results
    sim.get_results(timeStep,tags)

    numerator += sim.results.SurfaceTorque[timeStep]

#stop simulation
sim.stop()
print("Simulation Complete")

