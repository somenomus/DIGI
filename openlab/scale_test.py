#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#

import openlab
import math
from datetime import datetime

import urllib.request
url = "http://client.openlab.iris.no/run.txt"
request = urllib.request.Request(url)
response = urllib.request.urlopen(request)
RunNow = response.read().decode('utf-8')
print('Waiting for value "run"')
while True:
    if "run" in RunNow:
        break
    url = "http://client.openlab.iris.no/run.txt"
    request = urllib.request.Request(url)
    response = urllib.request.urlopen(request)
    RunNow = response.read().decode('utf-8')


tags=["SPP","DownholeECD","FlowRateOut","HookLoad","SurfaceTorque", "BitDepth", "TD", "ChokeOpening", "DownholePressure", "ChokePressure", "FluidTemperatureOut", "WOB", "InstantaneousROP", "BopChokeOpening", "FlowRateIn",
"TopOfStringVelocity", "SurfaceRPM", "ChokePumpFlowRateIn", "DrillstringTemperature", "TotalInfluxMass", "CalculatedPressureBottomHole", "CuttingsMassFractionTransient", "GasVolumeFraction", "DrillstringBucklingLimit",
"FluidTemperatureIn", "AnnulusECD", "DrillstringTorqueLimit", "AnnulusTemperature", "DrillstringTension", "AnnulusFluidVelocity", "DrillstringFluidVelocity", "CuttingsBedHeight", "AnnulusDensity", "DrillstringTorque",
"TotalMudLossMass", "Connection", "TopOfStringPosition", "ActivePitVolume", "ActivePitDensity", "ActivePitTemperature", "MainPitVolume", "MainPitDensity", "MainPitTemperature", "ReservePitVolume", "ReservePitDensity", "ReservePitTemperature"]

num_sims = 8

class Histogram():

    def __init__(self):
        self.bins      = [ 0, 25, 50, 75, 100, 125, 150,  175, 200, 250, 300, 500, 1000]
        self.histogram = [ 0, 0,   0,  0,   0,   0,   0,    0,   0,   0,   0,   0,    0]

    def add_value(self, value):
        index = 0
        for lower, upper in zip(self.bins[0::1], self.bins[1::1]):
            if lower <= value < upper:
                self.histogram[index] = self.histogram[index]+1
            index = index + 1

    def print(self):
        max_length = max([len(self.histogram)])
        max_length = min(max_length, 50)
        value_characters = 80 - max_length
        max_value = max(self.histogram)
        scale = int(math.ceil(float(max_value) / value_characters))
        scale = max(1, scale)
        str_format = "%" + str(max_length) + "s [%6d] %s"
        for index,value in enumerate(self.histogram):
            print(str_format % (self.bins[index], value, (int(value/scale)) * '|'))
        print(self.histogram)
def do_sim():
    client = openlab.http_client()

    config_name = 'Python sweep simulation'
    sims = []
    for i in range(0,num_sims):
        sim_name = "Load-Test-Sim-{}".format(i+1)
        sims.append(client.create_simulation(config_name, sim_name, 2500))

    hist = Histogram()
    for timestep in range(1, 899):
        for sim in sims:
            start = datetime.now()
            sim.step(timestep)
            sim.get_results(timestep, tags)
            end = datetime.now()
            deltaT = end - start

            deltaT_ms = deltaT.total_seconds() * 1000

            hist.add_value(deltaT_ms)
        hist.print()


if __name__ == "__main__":
    do_sim()