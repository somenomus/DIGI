import openlab

username="INPUT CREDENTIALS FROM openlab.app"
apikey=""
licenseguid=""

config_name = "PUT CONFIGURATION NAME HERE"
initial_bit_depth = 2495

# WOB Setpoints
wob = 5 * 1000 # 5 metric tons converted to SI unit of kg
# WOB PI controller setpoints 
kp = 1.0 / 1e5 # proportional gain
ki = 1.0 / 1e6 # integral gain


# Login and authenticate to openlab
session = openlab.http_client(username=username, apikey=apikey, licenseguid=licenseguid, environment="build")

sim = session.create_simulation(config_name, "WOB Example", initial_bit_depth)

# Apply the normal setpoints mandatory for drilling (apart from ROP)
sim.setpoints.FlowRateIn = 2000 / 60000 # 2000 l/m to SI unit of m^3/s
sim.setpoints.SurfaceRPM = 100 / 60 # 100 RPM to SI unit of Hz
sim.setpoints.TopOfStringVelocity = 0.5 # 1.5 m/s to tag bottom, then it gets ignored


# Make the WOB setpoints
sim.setpoints.DesiredWOB = wob
sim.setpoints.WOBAutoDriller = True
sim.setpoints.WOBProportionalGain = kp
sim.setpoints.WOBIntegralGain = ki

# Make 300 steps
sim.step(1, duration=300)

sim.stop()
