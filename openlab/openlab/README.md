# OpenLab python http client
This a python package for OpenLab `openlab`.
```
Name: openlab
Version: 2.5.7
Summary: A python client for openLab.
Home-page: https://live.openlab.app
Author: NORCE
Author-email: andrew.holsaeter@norceresearch.no
License: NORCE COPYRIGHT: Do not distribute without approval by NORCE
Requires: oauthlib, json, uuid, datetime, matplotlib, numpy, os, keyring
```

## Prerequisites
To use this package, you will need: 
1. An account to access the OpenLab web client (https://live.openlab.app) (can use Google or Microsoft account for a free trial)
2. An API key (which you can request in your user settings from the OpenLab web client at https://live.openlab.app) 
3. Python 3.6+ 

## Intended usage
The `openlab` python library acts as an http client for the openlab web api, which you find here http://live.openlab.app/swagger
Currently, this library supports the following workflow:
1. Create a configuration using the website application
2. Use python to programmaticaly create/run a new simuation on a pre-existing configuration or interact with already existing simulation/configuration data

### Installation and setup
1. From a command window run `pip install openlab`
2. Start a python shell/script and run the following login/authentication commands:
```
    >>> import openlab
    >>> client = openlab.http_client()
```
3. The first time you run the http_client, you will be prompted for your email/api_key and this will be stored in your confidential keychain for fourther use. YOU CAN GET AN API KEY IN YOUR USER SETTINGS FROM THE WEB APPLICATION (LIVE.OPENLAB.APP)
4. If running Ubunutu, and you receive errors pertaining to the keyring module. Try running `pip3 install --upgrade keyrings.alt`

## Recommended WorkFlow
1. import the client             ` >>> import openlab `
2. initialize the htpp_client    ` >>> client = openlab.http_client() `
3. initialize a simulation       ` >>> simulation = client.create_simulation("Existing_Config_Name", "Simulation_Name", Initial_bit_depth) `
4. Assign desired setpoints      ` >>> simulation.setpoints.ChokeOpening = 0.25 ` you can see or pass in all available setpoints by `>>> openlab.all_setpoints()`
5. Tag desired results to fetch   `>>> result_tags = ["SurfaceTorque", "FlowRateOut", "DownholePressure"] `   #you can see or pass in all available results by `>>> openlab.all_results()`
6. Run simulation                
``` 
   >>> for i in range(600):
   ...    simulation.step(i)
   ...    simulation.get_results(i, result_tags) 
```
7. Complete simulation           ` >>> simulation.stop() `

## Switching users / updating api key
If you need to switch users or update your api key, run the following in a python shell to override the stored credentials:
```
    >>> import openlab
    >>> openlab.login.switch_user(username, api_key)
```

## Jupyter Tutorial Notebook
Included in the OpenLab python package is a Jupyter notebook tutorial that goes into ways to use the client as well as:
- A very basic python tutorial that goes into some basics about the language
- Using a library to plot data
- PID controller tuning example using OpenLab
Instructions can be found in the `tutorial` folders README file

### MPD example
This example maintains constant BHP with varying flow rates by controlling choke opening. It is available at `python\examples\sweep.py`. 
Before you run this script you should do the following:
1. Prepare a configuration using the OpenLab web client
2. Entered your email and API key in the `openlab\credentials.py` file
3. Changed `conf_name` in the `sweep.py` file to the existing configuration name