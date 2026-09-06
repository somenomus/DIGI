import openlab

username = ""
apikey = ""
licenseguid = ""

session = openlab.http_client(username=username, apikey=apikey, licenseguid=licenseguid)


configuration = ""
sim_name = "Simulation Based on Geothermal"
initial_bit_depth = 2499

########## Simulation Based On GeoPressure ##############
influx_mode = {
    "Id": "GeoPressureGradient",
    "ManualReservoirMode": False,
    "UseReservoirModel": True
    }
# Alternatively, can fetch same dict from openlab.default_geopressure_gradient

sim = session.create_simulation(
    configuration,
    sim_name,
    initial_bit_depth,
    influx_type=influx_mode
)

sim.setpoints.SurfaceRPM = 1
sim.auto_step(60)


# Need to make sure you have added Choke Line 
# in Riser and flow lines section of the Well Architecture Configuration Editor
# Open Chokeline Valve
sim.setpoints.ChokelineValve = 1
sim.auto_step(10)
# Close Chokeline Valve
sim.setpoints.ChokelineValve = 0
sim.auto_step(10)


# Need to make sure you have added Kill Line 
# in Riser and flow lines section of the Well Architecture Configuration Editor
# Change Rig Choke Opening
sim.setpoints.RigChokeOpening = 0.75
sim.auto_step(10)


# Change Pump to Reserve
sim.setpoints.MainPitMainPump = False
sim.auto_step(10)


# Control Main Pit Density
# First, set ControlMainPit to True
sim.setpoints.ControlMainPit = True
# Then we can set density
sim.setpoints.ControlMainPitDensity = 1450
sim.auto_step(10)



input("Press to Stop")
sim.stop()

input("Press to Delete")
session.delete_simulation(sim.sim_id)