import openlab

sim_id = "PUT SIM ID HERE"

session = openlab.http_client()
print("")

print("All available results are {}".format(openlab.results.valid_results))
print("")

# see __init__ resultsClass for more
tags = ["SurfaceTorque", "FlowRateOut", "InstantaneousROP", "WOB", "SurfaceRPM"]

#last_setpoint = session.last_setpoint(sim_id)
#last_setpoint_time = last_setpoint['TimeStep']
#print("Last setpoint was at {} seconds and had setpoints of {}".format(last_setpoint_time,last_setpoint['Data']))

last_setpoint_time = session.last_timestep(sim_id)
print("Last timestep was:", last_setpoint_time)
print("")

from_time = last_setpoint_time -5
to_time =  last_setpoint_time

results = session.get_simulation_results(sim_id, from_time, to_time, True, tags)

#print all the results
print("Results for {} from {} to {}".format(tags,from_time,to_time))
for tag in results:
    print("\t",tag,"-",results[tag])
print("")

specific_result = "SurfaceTorque"
#print just a specific results
print("Results for just", specific_result)
for time in range(from_time, to_time+1):
    print("\t {} @ time {}: {}".format(specific_result, time, results[specific_result][time]))
print("")

#get depth_based values
time_based_value = session.get_simulation_results(sim_id, time, time, False, ['SPP'])
depth_based_value =  session.get_simulation_results(sim_id, time, time, False, ['DrillstringTension']) 
#note that if you leave filter_depth = True, you will only get depth_based_results for the last setpoint requested

#Time based results type vs depth based results types 
print("type of non depth-based value: {}".format(type(time_based_value['SPP'][time])))
print("type of depth based value    : {}".format(type(depth_based_value['DrillstringTension'][time])))
print("")

#loop through depth based results
for depth_value in depth_based_value['DrillstringTension'][time]:
    print("\t Depth: {} ; Value: {}".format(depth_value['d'],depth_value['v']))
