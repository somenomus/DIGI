"""Check that the OpenLab login works and see what the API gives back.

Logs in with the credentials from config.py, lists the configurations, stops
any simulation still running from an earlier crash, then runs a few steps on
the first configuration and prints every feedback tag. Run this once on a new
machine before training anything.
"""
import sys
import os
# use the vendored openlab, not whatever pip installed
_openlab_parent = os.path.join(os.path.dirname(os.path.abspath(__file__)), "openlab")
if _openlab_parent not in sys.path:
    sys.path.insert(0, _openlab_parent)

import openlab

# credentials come from config.py, which reads them from the environment
import config as cfg
username = cfg.OPENLAB_EMAIL
apikey = cfg.OPENLAB_API_KEY
licenseguid = cfg.OPENLAB_LICENSE_GUID


# put them in the keyring so later runs do not prompt
openlab.login.switch_user(
    new_user=username,
    new_key=apikey,
    new_licenseguid=licenseguid,
    environment='prod'
)

print(f"Connecting to OpenLab as {username}...")
kwargs = dict(username=username, apikey=apikey, licenseguid=licenseguid)

try:
    session = openlab.http_client(**kwargs)
    print("LOGIN SUCCESS!")
except Exception as e:
    print(f"LOGIN FAILED: {e}")
    raise SystemExit(1)

print(session.whoami())

print(session.user_limits())

print("\nAvailable Configurations")
configs = session.configurations()
for c in configs:
    print(f"  Name: {c['Name']}, ID: {c['ConfigurationID']}")

if not configs:
    print("  (No configurations found...)")

# kill anything still running from a previous crash. this stops every sim on the account
print("\n Cleaning up old simulations")
sims = session.simulations()
for s in sims:
    if s['Status'] in ('Running', 'Created'):
        print(f"  Stopping sim {s['SimulationID']} (status: {s['Status']})")
        try:
            session.end_simulation(s['SimulationID'])
        except Exception as e:
            print(f"    Failed to stop: {e}")

# short test simulation on the first config, print every tag we can get
if configs:
    config_name = configs[0]['Name']
    config_id = configs[0]['ConfigurationID']
    print(f"\n--- Testing simulation with config: {config_name} ---")

    sim = session.create_simulation(config_name, "API_Verify_Test", 2497, StepDuration=1)
    print(f"Simulation created! ID: {sim.sim_id}")
    print(f"Max timesteps: {sim.max_timeStep}")

    # setpoints go in SI
    sim.setpoints.SurfaceRPM = 120 / 60       # rpm -> Hz
    sim.setpoints.DesiredWOB = 20 * 1000       # kN -> kg
    sim.setpoints.WOBAutoDriller = True
    sim.setpoints.FlowRateIn = 1500 / 60000   # l/min -> m3/s
    sim.setpoints.DesiredROP = 0.02            # m/s
    sim.setpoints.TopOfStringVelocity = 0.02   # m/s

    sim.step(1)

    # every time-series tag the API knows about
    all_tags = [
        "SPP", "DownholeECD", "FlowRateOut", "HookLoad", "SurfaceTorque",
        "BitDepth", "TD", "ChokeOpening", "DownholePressure", "ChokePressure",
        "FluidTemperatureOut", "WOB", "InstantaneousROP", "FlowRateIn",
        "TopOfStringVelocity", "SurfaceRPM", "TotalInfluxMass",
        "CalculatedPressureBottomHole", "FluidTemperatureIn", "TotalMudLossMass",
        "Connection", "TopOfStringPosition", "ActivePitVolume", "ActivePitDensity",
        "ActivePitTemperature", "MainPitVolume", "MainPitDensity", "MainPitTemperature"
    ]

    sim.get_results(1, all_tags)

    print("\n FEEDBACK at timestep 1 ")
    for tag in all_tags:
        result_dict = getattr(sim.results, tag, {})
        val = result_dict.get(1, "N/A")
        print(f"  {tag:40s} = {val}")

    # a few more steps to watch ROP settle
    print("\n Running 5 more steps")
    for t in range(2, 7):
        sim.step(t)
        sim.get_results(t, ["InstantaneousROP", "WOB", "SPP", "SurfaceTorque", "DownholePressure", "BitDepth"])
        rop = sim.results.InstantaneousROP.get(t, 0)
        wob = sim.results.WOB.get(t, 0)
        spp = sim.results.SPP.get(t, 0)
        torque = sim.results.SurfaceTorque.get(t, 0)
        dp = sim.results.DownholePressure.get(t, 0)
        bd = sim.results.BitDepth.get(t, 0)
        print(f"  t={t}: ROP={rop:.6f} m/s, WOB={wob:.1f} kg, SPP={spp:.0f} Pa, "
              f"Torque={torque:.0f} Nm, BHP={dp:.0f} Pa, BitDepth={bd:.1f} m")

    sim.stop()
    print("\nSimulation stopped. API verification complete!")
else:
    print("\nNo configurations available...")