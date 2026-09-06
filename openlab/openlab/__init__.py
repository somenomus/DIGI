import requests
import os
import json
import uuid
import time
from enum import Enum
from oauthlib.oauth2 import LegacyApplicationClient, InvalidGrantError
from requests_oauthlib import OAuth2Session
from requests import HTTPError
import atexit
import numbers
import pkg_resources
import outdated

from openlab import credentials, login, piController, exceptions
from openlab import logger as openlabLogger # RENAME
from openlab import results, setpoints

# One logger for all http_clients
openlab_logger = openlabLogger.makeLogger("openlab.http_client")

class http_client(object):
    sim = None
    max_results_attempts = 20
    max_init_attempts=75
    """
    A utility class for using the openLab RESTfull API
    """ 
    def __init__(self, proxies = {}, **kwargs):
        # Setup root to coordinate log formats        
        openlabLogger.setUpRootLog()
        
        openlab_logger.info("Initializing Openlab http client")
        
        #create and validate the oauth client
        self.client= login.create_token(**kwargs) # returns an oauth session
        self.credentials = login.get_credentials(**kwargs) #FIXME
        self.url = self.credentials['url']

        # FIXME change to alive endpoint
        self._check_login_worked()
        self.version_check()
        
        # see if there there is another server url that the web client has decided would be better to use
        if 'EndpointUrl' in self.whoami().keys():
            self.url = self.whoami()['EndpointUrl']
        
        #TODO: Call to version endpoint

    def version_check(self):
        try:
            version = pkg_resources.get_distribution("openlab").version
            is_outdated, latest_version = outdated.check_outdated('openlab', version)
            if is_outdated:
                openlab_logger.warning(f"Your openlab version {version} is outdated. Consider upgrading to {latest_version}")
        except:
            # Don't want version check to crash/affect client
            openlab_logger.info("Could not verify openlab is current")
            
        return

    def _check_login_worked(self):
        #first, we check for invalid grant errors
        try:
            r=self.client.get(self.url+"/users/whoami") #random method to call web api, so that we can check the response code
            # Raises HttpError when status_code between 400 and 600
            r.raise_for_status()

            if r.status_code != 200:
                openlab_logger.error(f"Call to whoami failed with HTTP Code: {r.status_code}. Attempting to create new token")
                self.client = login.create_token()
            else:
                openlab_logger.info("Login Succesfull")

        except InvalidGrantError:
            openlab_logger.error("Invalid Grant Exception Thrown. Attempting to create new token")
            self.client = login.create_token()
        return 

    def labels(self):
        r=self.client.get(self.url+"/labels/")
        return self.standard_response(r, 200) 

    def labels_by_id(self, config_id):
        r=self.client.get(self.url+"/configurations/" + str(config_id) + "/labels")
        return self.standard_response(r, 200)     

    @staticmethod
    def standard_response(response, success_status_code, success_msg=None, model=None):
        """
        model = "simulation" or "configuration" so we can throw appropriate exceptions
        """
        status_code = response.status_code
        try:
            # Raises HTTPError for status_codes between 400 and 600
            response.raise_for_status()
           
            if status_code == success_status_code:
                if success_msg is not None:
                    openlab_logger.info(success_msg)
                
                method = response.request.method
                # no content will throw jsonDecodeError
                content = response.content

                if method == 'GET' and content:
                    return response.json()
                if method == 'POST' and content:
                    return response.json()
                if method == 'PUT' and content:
                    return response.json()          
                if method == 'DELETE':
                    return True
                
            else:
                raise Exception("Error getting response from web_client:\n {} \n {}".format(response, response.text))

        except HTTPError as err:
            msg = response.text
            # Catch some custome openlab errors
            if status_code == 404:
                if model and model == "simulation":
                    raise exceptions.SimulationNotFound(msg)
                if model and model == "configuration":
                    raise exceptions.ConfigurationNotFound(msg)
            elif status_code == 422:
                raise exceptions.ValidationError(msg)
            else:
                # Raise the original HTTPError
                raise err

    def whoami(self):
        """
        Returns information about the current user
        """
        r=self.client.get(self.url+"/users/whoami")
        return self.standard_response(r, 200)

    def alive(self):
        """
        Pings the API and returns True if alive
        """
        r=self.client.get(self.url+"/alive")
        return True if r.status_code == 204 else False

    def version(self):
        """
        The API version
        """
        r=self.client.get(self.url+"/version")
        return self.standard_response(r, 200)

    def user_limits(self, **kwargs):
        """Returns the user limits"""
        query = dict()
        if 'licenseId' in kwargs.keys():
            query['licenseId'] = kwargs.get("licenseId")
            r = self.client.get(self.url + "/users/limits?", params = query)
        elif 'license_id' in self.credentials.keys():
            query['licenseId'] = self.credentials['license_id']
            r = self.client.get(self.url + "/users/limits?", params = query)
        else:
            openlab_logger.info("No license given. Defaulting to personal license")
            r = self.client.get(self.url + "/users/limits")
        return self.standard_response(r,200)

    def simulations(self):
        """
        Returns a list all simulations of the current user
        Each entry being a dictionary with some simulation information
        """        
        r=self.client.get(self.url+"/simulations")
        return self.standard_response(r, 200)

    def check_if_simulation_exists(self,sim_id):
        """
        Deprecated: Use _check_if_simulation_exists() instead
        """
        openlab_logger.warning("check_if_simulation_exists is Deprected. Use _check_if_simulation_exists instead")
        return self._check_if_simulation_exists(sim_id)

    def _check_if_simulation_exists(self,sim_id):
        simulations = self.simulations()
        sim_exists = False
        for simulation in simulations:
            if simulation['SimulationID'] == sim_id:
                sim_exists = True
        return sim_exists            

    def set_setpoints(self, sim_id, step, setpoints, shouldComplete=False):
        """
        Sends manually formatted setpoints to a given simulation outside of Simulation class (i.e. steps a simulation forward)
        Setpoints must be a single dictionary, and formatted as: {'tag':value}
        For a list of openlab setpoint tags, see openlab.setpoints.valid_tags. Tags are string sensitive
        Passing in True to shouldComplete, will complete the simulation
        """
        data= self.format_set_point_data(step, setpoints, shouldComplete)
        r=self.client.post(self.url+"/simulations/"+sim_id+"/setpoints", json= data)

        return self.standard_response(r, 200, model="simulation")
    
    def all_setpoints(self,sim_id):
        """
        Returns all the set points of a simulation
        """
        #timestep = self.last_timestep(sim_id)
        r=self.client.get(self.url+"/simulations/"+ sim_id+ "/setpoints")
 
        return self.standard_response(r, 200, model="simulation")

    def last_setpoint(self, sim_id):
        """
        Returns the last set points of a simulation
        """
        #timestep = self.last_timestep(sim_id)
        r=self.client.get(self.url+"/simulations/"+ sim_id+ "/setpoints/last")

        return self.standard_response(r, 200, model="simulation")

    def last_timestep(self, sim_id):
        """
        Returns the last timestep of a simulation
        """
        r=self.client.get(self.url+"/simulations/"+ sim_id+ "/timestep")
        
        return self.standard_response(r, 200, model="simulation")
    
    def get_simulation_status(self,sim_id):
        r = self.client.get(self.url+"/simulations/"+sim_id+"/status")

        return self.standard_response(r, 200, model="simulation")

    def get_simulation_results(self, sim_id, from_step, to_step, filter_depth, tags: list, validate_tags= True):
        """
        Gets the simuation results of a given simulation for a given time interval.
        Setting filter_depth = True filers out the depth based results profiles for all but the last setpoints
        Returns a dictonary of dictonaries e.g. results[timeStep]["tag"]
        """
        query=dict()
        query["timestepfrom"]= str(from_step)        
        query["timestepto"]=str(to_step)
        for tag in tags:
            if validate_tags and tag not in results.valid_results:
                raise Exception("""
                '{}' is not a valid OpenLab result tag. Check spelling and capitilization.
                If you think this is a mistake, pass in validate=False to the get_simulation_results method""".format(tag))
            query[tag]="true"
        query["filterDepth"]=str(filter_depth)
        
    
        r=self.client.get(self.url+"/simulations/"+ str(sim_id)+ "/results?", params= query)
        # Pass to standard response
        r_json = self.standard_response(r, 200, model="simulation")

        #convert the json to a dictionary of the requested results tags
        result=dict()
        result = self.collect_timebased_results(None, r_json, tags) # Timestep is deprecated and not used
        
        return result

    def configurations(self):
        """
        Returns all configurations of the current user
        """
        r=self.client.get(self.url+"/configurations") #r is of class response
        return self.standard_response(r, 200)

    def create_configuration(self, name, data):
        """
        Creates a configuration with the given data and name
        To see example of data structure format, see the configuration_data() method
        """
        config_id= str(uuid.uuid4())
        body = {'ConfigurationID':config_id, 'Data':data, 'Name':name}
        r=self.client.post(self.url+"/configurations", json = body)
        return self.standard_response(r, 200)

    def update_configuration(self, name, data):
        """
        Updates a configuration with the given data and name
        To see example of data structure format, see the configuration_data() method
        """
        config_id=self.configuration_id(name)
        body={'Data':data, 'Name':name}
        r=self.client.put(self.url+"/configurations/"+config_id, json=body)
        return self.standard_response(r, 200, model="configuration")
    
    def _check_if_configuration_belongs_to_user(self, config_id):
        """
        Takes a config guid string. 
        Returns false if configuration doesn't exist or if it exists but isn't found in user configurations
        """
        try:    
            info = self.configuration_info(config_id)
        except exceptions.ConfigurationNotFound:
            return False

        if info is None:
            # Raise ConfigurationNotFound here instead??
            return False

        user_configurations = self.configurations()
        config_owned_by_user = False
        for configuration in user_configurations:
            if configuration['ConfigurationID'] == config_id:
                config_owned_by_user = True
        
        return config_owned_by_user

    def check_if_configuration_id_exists(self,config_id):
        """
        Deprecated: Use _check_if_configuration_id_exists() instead
        """
        openlab_logger.warning("check_if_configuration_id_exists is Deprected. Use _check_if_configuration_id_exists instead")
        return self._check_if_configuration_id_exists(config_id)

    def _check_if_configuration_id_exists(self,config_id):
        """
        Not necessarily owned by the user
        """
        configurations = self.configurations()
        config_exists = False
        for configuration in configurations:
            if configuration['ConfigurationID'] == config_id:
                config_exists = True
        return config_exists    

    def check_if_configuration_name_exists(self,config_name):
        """
        Deprecated: Use _check_if_configuration_name_exists() instead
        """
        openlab_logger.warning("check_if_configuration_name_exists is Deprected. Use _check_if_configuration_name_exists instead")
        return self._check_if_configuration_name_exists(config_name)

    def _check_if_configuration_name_exists(self,config_name):
        """
        Takes a configuration name string (case sensitive), and
        Returns True/False depending on 

        """
        configurations = self.configurations()
        config_exists = False
        for configuration in configurations:
            if configuration['Name'] == config_name:
                config_exists = True
        
        return config_exists

    def configuration_info(self, config_id):
        """
        Returns all configuration info and data of the given configuration
        """
        r=self.client.get(self.url+"/configurations/"+ config_id)

        return self.standard_response(r, 200, model="configuration")

    def configuration_id(self, name):
        """
        Returns configuration id with a given name
        """
        r=self.client.get(self.url+"/configurations/"+ name)

        return self.standard_response(r, 200, model="configuration")

    def configuration_data(self, config_id):
        """Returns a dictionary of configuration data such as Trajectory, Architecture, Fluids etc..."""
        config = self.configuration_info(config_id)
        return config['Data']

    def configuration_simulations(self, config_id):
        """
        Returns a list of all the simulations for a given configuration
        With each entry of said list, being a dictionary of simulation info
        """
        r = self.client.get(self.url+"/configurations/"+str(config_id)+"/simulations")

        return self.standard_response(r, 200, model="configuration")

    def delete_simulation(self, simulationID):
        """
        Deletes a given simulation.
        Takes a simulation id
        Returns True when HTTP code 204 is returned indicating succesful deletion
        Raises SimulationNotFound when HTTP code 404 is returned
        Else returns False with error log
        """
        r = self.client.delete(self.url+"/simulations/"+simulationID)
        # call standard response, so HTTP exceptions can be raised
        self.standard_response(r, 204, model="simulation")

        if r.status_code == 204:
            openlab_logger.info(f"Simulation {simulationID} was deleted")
            return True
        else:            
            openlab_logger.error(f"Unable to delete simulation {simulationID}")
            return False

    def delete_configuration(self, configurationID: str):
        """
        Deletes a given configuration and all it's simulations
        Takes a configuration id
        Returns True when HTTP code 204 is returned indicating succesful deletion, 
        Raises ConfigurationNotFound exception when HTTP code 404 is returned
        Else returns False with error log
        """
        r = self.client.delete(self.url+"/configurations/"+configurationID)
        # call standard response, so HTTP exceptions can be raised
        self.standard_response(r, 204, model="configuration")

        if r.status_code == 204:
            openlab_logger.info(f"Configuration {configurationID} and all its simulations were deleted")
            return True
        else:
            openlab_logger.error(f"Unable to delete configuration {configurationID}")
            return False

    def simulation_by_id(self, sim_id):
        """
        Takes the simulation id of a simulation that has already been created
        Returns an openlab.Simulation instance
        **Note you must use the id, not the name, as multiple simulations can have the same name
        Simulation ID can be found in the url when viewing a simulation in live.openlab.app
        """
        if type(sim_id) is not str:
            raise TypeError("Sim-id must be a string")        

        r=self.client.get(self.url+"/simulations/"+ sim_id)
        r_json = self.standard_response(r, 200, model="simulation")
        
        config_id = r_json['ConfigurationID']
        
        sim = Simulation(config_id, sim_id, self)
       
        return sim
    
    def create_simulation(self, config_name, sim_name, initial_bit_depth, **kwargs):
        """
        Creates a simulation and returns an openlab.Simulation class instance
        Takes
        Initialization parameters can be passed in as kwargs and are
        **kwargs: 
            * influx_type
                - influx_types must be a dictionary
                - Examples for the three types (direct influx/direct loss/based on geopressure) can be found 
            * StepDuration: Duration interval in seconds of steps. Valid durations are [0.1, 0.2, 0.3, ... , 0.9, 1.0]
            * UseTemperature, # bool. Default = True
            * UseTransientCuttingsModel", # bool. Default = True
            * UseGelModel # bool. Default = False
            * UseReservoirModel, # bool. Default = False
            * UseTransientMechanicalModel, # Default = False            
            * UseDrillstringLeakage, # bool. Default = False
            * ManualReservoirMode, # bool. Default = False
        """
        if 'TimeStep' in kwargs.keys():
            openlab_logger.warning('TimeStep has been deprecated in favor of more appropriate key name StepDuration')
            kwargs['StepDuration'] = kwargs.get('TimeStep')
        
        # We set default influx_type here so we can derefence it and combine it with other kwargs
        kwargs.setdefault('influx_type', {})
        # Pop it here so we can seperate it from  That might throw off format method validations though
        influx_type = kwargs.pop('influx_type')

        #create a sim_id
        sim_id= str(uuid.uuid4())
        config_id = self.configuration_id(config_name)
        
        #check initial bit depth is valid
        max_depth = self.max_configuration_depth(config_id)
        if initial_bit_depth > max_depth:
            raise Exception("Initial bit depth of {} can not be greater than configurations maximum openhole depth of {}".format(
                initial_bit_depth,max_depth))

        #check if max simulation capacity already reached
        user_limits = self.user_limits(**kwargs)

        license_id = self.credentials['license_id']
        if license_id is not None:
            kwargs['license_id'] = license_id

        openlab_logger.info(f"User limits: {user_limits}")
        # TODO: Do this in a better way (only on error) or remove it
        if type(user_limits) is dict and "MaxConcurrentSimulations" in user_limits.keys():
            simulation_capacity = user_limits['MaxConcurrentSimulations']
            active_simulations = set()
            simulations = self.simulations()
            for sim in simulations:
                status = sim['Status']
                if status == "Running" or status == "Created":
                    active_simulations.add(sim['SimulationID'])
            if len(active_simulations) >= simulation_capacity:
                raise Exception(
                    """Max conccurent simulation capacity of {} reached.\n
                    Please stop/complete one of the running simulations to continue: \n
                    {} \n
                    Or visit https://openlab.app to upgrade your account and get more conccurent simulation capacity.
                    """.format(simulation_capacity, active_simulations))

        # format the data to send web_client
        simulation= self.format_simulation_meta_data(self, sim_id, config_id, sim_name,initial_bit_depth, influx_type=influx_type, **kwargs)
        
        r=self.client.post(self.url+"/simulations", json = simulation)
        # Since post, no need to put model="simulation"
        r_json = self.standard_response(r, 200)

        # get the simulation id that the web_client created
        simulation_id = r_json["SimulationID"]
        
        # Give openlab a head start
        time.sleep(15)
        for x in range(self.max_init_attempts):
            r=self.client.get(self.url+"/simulations/"+str(simulation_id)+"/status")
            r_json = self.standard_response(r, 200, model="simulation")

            status = r_json.get("Status")
            if status and status == "Running":
                openlab_logger.info("Simulation Initialized")
                #create a simulation class and return it to the caller
                return Simulation(config_id, simulation_id, self)
            else: 
                time.sleep(0.2)
                x += 1
        # TODO: Make this openlab timeout error or create a new http_client Timeout
        raise exceptions.OpenlabTimeoutError("Failed to start simulation " + sim_name + "\nMax attempts reached") 

    def simulation_timestep(self, sim_id):
        r = self.client.get(self.url+"/simulations/"+sim_id+"/timestep")
        
        return self.standard_response(r, 200, model="simulation")
        
    def max_configuration_depth(self,config_id):
        """
        Returns the maximum openhole depth of a configuration in meters
        """
        depth = self.configuration_info(config_id)['Data']['Architecture']['OpenHole']['DepthInterval']['MaxX']
        return depth
          
    def end_simulation(self, sim_id, timeStep = None):
        body = [] # json must be list?
        setpoints = {}
        # Don't break old scripts that don't pass in step
        if timeStep is not None:
            setpoints['TimeStep'] = timeStep

        setpoints['Data'] = {} # blank setpoints
        setpoints['ShouldComplete'] = True

        body.append(setpoints)

        success_msg = "{} was completed".format(sim_id)

        r=self.client.post(self.url+"/simulations/"+sim_id+"/setpoints", json= body)
        return self.standard_response(r, 200, success_msg, model="simulation")

    @staticmethod
    def format_configuration_meta_data(id,name,description,data):
        return { 'ConfigurationID': id, 'Data': data, 'Description': description, 'Name': name}

    @staticmethod
    def format_and_validate_simulation_model_configuration(**kwargs):
        ## TODO Add check for key in kwargs.keys(): check if valid kwarg
        model_configuration = {}

        # Set defaults
        kwargs.setdefault('StepDuration', 1)
        kwargs.setdefault('Id', 'NoInfluxLoss')
        kwargs.setdefault('UseReservoirModel', False)
        kwargs.setdefault('ManualReservoirMode', False)
        kwargs.setdefault('UseTransientCuttingsModel', True)
        kwargs.setdefault('UseTemperature', True)
        kwargs.setdefault('UseTransientMechanicalModel', False)
        kwargs.setdefault('UseDrillstringLeakage', False)
        kwargs.setdefault('UseGelModel', False)
        kwargs.setdefault('UseDetournayROPModel', False)


        step_duration = kwargs.get('StepDuration')

        #print("==============Format_and_validate_kwargs after setdefault===========")
        #print(kwargs,"\n================================")

        # Influx
        kwargs.setdefault('influx_type', {})
        influx_type = kwargs.get('influx_type')
        if not isinstance(influx_type, dict):
            raise TypeError("influx_type must be a dictionary")

        #print(f"influx_type: {influx_type}")
        # do some influx type validations if it was passed in/not default
        if influx_type != {}:
            if "Id" not in influx_type.keys():
                raise exceptions.ValidationError(f"Influx Id key was not entered. Valid influx Ids are {influx_ids}")

            #check if influx id is one of the valid influx types
            if influx_type['Id'] in influx_ids:
                openlab_logger.info(f"{influx_type['Id']} mode selected")
                for k in influx_type.keys():
                    #append model configuration with influx dict
                    model_configuration[k] = influx_type[k]
            else:
                raise exceptions.ValidationError(f"Invalid influx id '{influx_type['Id']}' entered. Valid influx/loss Ids are {influx_ids}")                    
        elif kwargs.get('Id') == "ManualInflux" or kwargs.get('Id') == 'ManualLoss':
            openlab_logger.info(f"{kwargs.get('Id')} selected")
            keys = [
                'ComplexReservoirKickOffTime', 'ManualInfluxLossMD',
                'ManualInfluxLossMassRate','ManualInfluxLossTotalMass',
                'ManualReservoirMode', 'UseReservoirModel'
            ]
            for k in keys:
                # TODO: wrap in try/catch to caatch if kwargs doesn't have key
                model_configuration[k] = kwargs[k]
            # TODO: Check ManualReservoirMode & UseReservoirModel to either throw exception or warn of atleast override if False
        else:
            openlab_logger.info("No influx mode selected. Defaulting to 'NoInfluxLoss'")
            model_configuration['Id'] = "NoInfluxLoss"
            model_configuration['ManualReservoirMode'] = False
            model_configuration['UseReservoirModel'] = False

        # Validate StepDuration
        if step_duration > 1 or step_duration < 0.1:
            raise exceptions.ValidationError("StepDuration must be between and including 0.1 and 1.0")
        elif step_duration not in [0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1.0,1]: # 1 & 1.0 will evaluate true, but put both just to be sure
            raise exceptions.ValidationError("StepDuration must be an increment of 0.1")
        
        if kwargs.get('UseTransientMechanicalModel') is True:
            if step_duration != 0.1:
                raise exceptions.ValidationError("When using Transient Mechanical Model. StepDuration must be 0.1")            
            openlab_logger.info(f"Using Transient Mechanical Model with time step: {step_duration}")


        model_configuration['StepDuration'] = step_duration
        #model_configuration['StepDuration'] = kwargs.get('StepDuration')
        model_configuration['Id'] = kwargs.get('Id')
        model_configuration['UseReservoirModel'] = kwargs.get('UseReservoirModel')
        model_configuration['ManualReservoirMode'] = kwargs.get('ManualReservoirMode')
        model_configuration['UseTransientCuttingsModel'] = kwargs.get('UseTransientCuttingsModel')
        model_configuration['UseTemperature'] = kwargs.get('UseTemperature')
        model_configuration['UseTransientMechanicalModel'] = kwargs.get('UseTransientMechanicalModel')
        model_configuration['UseDrillstringLeakage'] = kwargs.get('UseDrillstringLeakage')
        model_configuration['UseGelModel'] = kwargs.get('UseGelModel')
        model_configuration['UseDetournayROPModel'] = kwargs.get('UseDetournayROPModel')

        return model_configuration

    @staticmethod
    def format_simulation_meta_data(self, sim_id, config_id, name, initial_bit_depth, **kwargs):        
        
        simulation_model = {}
        #print(f"============Kwargs in format_simulation_meta_data==========\n",kwargs,"\n===============================")

        model_configuration = self.format_and_validate_simulation_model_configuration(**kwargs)

        if 'licenseId' in kwargs.keys():
            simulation_model['licenseId'] = kwargs.get("licenseId")
        elif 'license_id' in self.credentials.keys():
            simulation_model['licenseId'] = self.credentials['license_id']
        
        simulation_model['Name'] = name
        simulation_model['SimulationID'] = sim_id
        simulation_model['ConfigurationID'] = config_id
        simulation_model['InitialValues'] = {"BitDepth":initial_bit_depth}
        simulation_model['ModelConfiguration'] = model_configuration

        #print(simulation_model)

        return  simulation_model

    @staticmethod
    def collect_timebased_results(timestep, data, tags: list):
        """
        Collects the given tags from the result set
        Timestep is deprecated and not used
        """
        result= { tag: dict() for tag in tags }
        for v in data:
            tag, step, value = v['t'], v['s'], v['v']
            
            if isinstance(value[0]['d'], numbers.Number):
                # Depth based
                result[tag][step] = value #dump all the depths/value pairs into the result
            else:
                # Time based
                result[tag][step] = value[0]['v'] #drop the NaN depth
        return result

    @staticmethod
    def format_set_point_data(timestep, setpoints: dict, shouldComplete = False, shouldPause = False):
        return [{"TimeStep":timestep, "Data": setpoints, "ShouldComplete":shouldComplete, "ShouldPause":shouldPause}]

influx_types = ["ManualInflux", "ManualLoss", "GeoPressureGradient"]
influx_ids = ["NoInfluxLoss", "ManualInflux", "ManualLoss", "GeoPressureGradient"]

default_manual_influx = {"ComplexReservoirKickOffTime": 30,
            "Id" : "ManualInflux",
            "ManualInfluxLossMD": 2500,
            "ManualInfluxLossMassRate" : 0.083333333, 
            "ManualInfluxLossTotalMass": 50,
            "ManualReservoirMode" : True,
            "UseReservoirModel" : True}

default_manual_loss = {"ComplexReservoirKickOffTime": 30,
            "Id" : "ManualLoss",
            "ManualInfluxLossMD": 2500,
            "ManualInfluxLossMassRate" : -1.66666667,
            "ManualInfluxLossTotalMass": 1000,
            "ManualReservoirMode" : True,
            "UseReservoirModel" : True}
            
# technically not default because there are no variable inputs, but want to keep it consistent with the other names
default_geopressure_gradient = {"Id": "GeoPressureGradient", 
            "ManualReservoirMode" : False,
            "UseReservoirModel": True}

#simulation iterable class
class IterSimulation(type):
    def __iter__(cls):
        return iter(cls._registry)

class Simulation(metaclass=IterSimulation):
    """
    A Simulation class for the OpenLab http_client
    """
    #Things needed to make the simulations iterable
    __metaclass__ = IterSimulation
    _registry = []

    def  __init__(self, config_id, sim_id, client):
        self.logger = openlabLogger.makeLogger("sim-"+sim_id)
        openlabLogger.setUpRootLog()
            
        self.config_id = config_id
        self.http_client = client
        self.sim_id = sim_id
        self.timeout = 60 # seconds
        self.setpoints = setpoints.Setpoints()
        self.results = results.Results()
        try:
            self.max_timeStep = client.user_limits()['MaxTimeStep']
        except: self.max_timeStep = None

        self.end_simulation_on_exiting = False
        self.has_been_stopped = False
        self.filter_depth_based_results = True #setting true will only get the depth based results for the most recent setpoint
        self.ModelConfiguration = {}
        self._registry.append(self) #add the simulation to the iterable registry 
        self.connecting_previously = False
        self.currently_connecting = False
        # Make none so we can print out stepping first step in step 
        self.timeStep = client.last_timestep(sim_id)

        status = self.get_status()
        if status == "Created" or status == "Initialized" or status == "Running":
            self.is_running = True
        else:
            self.is_running = False
    
    def __iter__(self):
        return iter(self)

    def get_conf_id(self):
        """
        Returns the configuration id of the simulation instance
        """
        return self.config_id

    def get_sim_id(self):
        """
        Returns the simulation id for the simulation instance
        """
        return self.sim_id

    def whoamiFromSimulation(self):
        return self
    
    def get_status(self):
        """
        Returns the status of the simulation instance 
        """
        return self.http_client.get_simulation_status(self.sim_id)['Status']

    def last_setpoints(self):
        """
        Returns the last setpoints for the simulation instance
        """
        return self.http_client.last_setpoint(self.sim_id)

    def current_step(self):
        """
        Returns the current step for the simulation instance
        """
        return self.http_client.simulation_timestep(self.sim_id)
    
    def current_setpoints(self):
        """
        Returns the simulations instances current setpoints that will be sent to web client when the step method is called
        """
        #empty dictionary for setpoints
        toSet = {}
        for attr, value in self.setpoints.__dict__.items():
            # This is all done because I have None default values which fails backend validation
            if value is not None:
                toSet[attr] = value

        return toSet

    def auto_step(self,steps: int, tags = None):
        start_step = self.current_step() + 1
        end_step = start_step + steps
        for i in range(start_step, end_step):
            self.step(i)
            if tags is not None:
                self.get_results(i, tags)

    def step(self,timeStep, duration=1, wait=True):
        """
        Steps the simulation for steps of range(timeStep, timeStep + duration)
        Verifies steps have been completed when wait == True, by polling the OpenLab API after some expected_calulcated time
        Optional default arguments:
        * duration:int - How many steps you want the simulator to take with the currently assigned sim.setpoints
        * wait:bool - Whether or not you want this method to block and wait until new results have finished being
                      calculated for all steps in range(timestep, timestep+duration).
                      !Note: If you plan on using results based on the timesteps passed in immediately after calling this method,
                      you will need to keep this as True
        Exceptions:
        * openlab.ValidationError when:
                * Trying to set a setpoint at a timestep that has already been set
                * Trying to set a setpoint that has a current value outside the limits defined in Openlab backend (units must be SI)  
        * openlab.TimeoutError when result calculations take longer than specified under Simulation.timeout (default == 60s)
        * openlab.SimulationCompleted/openlab.SimulationAborted when a simulation is unexpectly completed/aborted
        """
        # verify the time step is correct
        #if timeStep != self.timeStep + 1:
        #    raise Exception(f"Trying to set a set a setpoint ({timeStep}) not at the immediate next timestep ({self.timeStep+1}).")
        
        # TODO: Add user license exception to throw
        if timeStep >= self.max_timeStep:
            self.logger.error(f"Max simulation time of {self.max_timeStep} steps will be exceeded. Vist https://openlab.app to upgrade your account and get more time")
            return
        # Using > here rather than >= because when duration == 1, you 
        elif timeStep + duration > self.max_timeStep:
            self.logger.error(f"Max simulation time of {self.max_timeStep} steps will be exceeded. Vist https://openlab.app to upgrade your account and get more time")
            return

        if self.is_running is False:
            raise exceptions.SimulationCompleted(f"Simulation cannot be stepped as it as already been {self.get_status()}")

        # Get the client to post the setpoints to the web_client
        r = self.http_client.set_setpoints(self.sim_id, timeStep, self.current_setpoints(), False)
        # r is a list of setpoints returned

        # If duration is more than one, we need to call step again with timestep endpoint
        if duration > 1:
            # Always use duration 1, or we will get infinite recursion 
            self.step(timeStep + duration, 1, wait)

        # Bool for if we should wait for results to catch up to setpoint timestep
        if wait is True:
            # Calculate a dynamic expected wait time based on difference b/w self.timestep & timeStep passed in
            current_step = self.current_step()
            avg_setpoint_calculation_time = 25 # ms/step ; Just an arbitrary time found empiracly
            expected_wait_time = (timeStep - current_step) * avg_setpoint_calculation_time # ms
            
            if expected_wait_time < 0:
                # time.sleep requires a non-negative number
                expected_wait_time = 0
            
            # Sleep in seconds
            time.sleep(expected_wait_time/1000)
            
            # Get results to ensure it was taken (Connection gets automatically requested)
            res = self.get_results(timeStep, [])

# Removing this block because when duration > 1, recursion means the initial timeStep gets called last
#            try:
#                actual_ts = list(res['Connection'].keys())[-1] # A result looks like => {'tag': {ts : value}}
#
#                if timeStep != actual_ts:
#                    raise Exception(f"Timesteps don't match. Requested => {timeStep} | Returned => {actual_ts}")
#
#            except TypeError:
#                self.logger.warning(f"Failed getting results at {timeStep}. Timesteps may not match anymore")

            # Must call API because recursion when duration > 1 means initial timeStep gets called last
            self.timeStep = self.current_step()
        
        # Should we assign timeStep optimistaclly??

        return
        
                
    def get_results(self,timeStep,tags: list):
        """
        Gets the results for the given timestep(s) and assigns them to Simulation.results.tag[timeStep(s)]. 
        Timestep can be a single timestep or a list of length 2 signifying timeStepFrom and timeStepTo
        Pass in openlab.results.all_results() to retrive all available results
        Uses class instance property Simulation.filter_depth_based_results:
        * When True: Only timeStep[1] depth values will be returned
        * When False: retrieve all depth based values for timesteps in list
        Returns the results also
        """
        
        if isinstance(timeStep, list):
            if len(timeStep) != 2:
                raise ValueError(f"timeStep must be of length 2 when passed in as a list")
            timeStepFrom = timeStep[0]
            timeStepTo = timeStep[1]
        else:
            timeStepFrom = timeStep
            timeStepTo = timeStep
            
        res = None
        if timeStepFrom >= 1:
            if "Connection" not in tags:
                tags.append("Connection")
        
            attempts = 0
            #loop until we get data, surpass timeout time, or unexpectly complete/abort a simulation
            start = time.time()
            while(True):
                #get the http_client to request simulation results
                res = self.http_client.get_simulation_results(self.sim_id,timeStepFrom, timeStepTo, self.filter_depth_based_results, tags)

                if res.get("Connection"):
                    #break out of while loop once there are results
                    break

                elif attempts >= self.http_client.max_results_attempts:
                    # Check timeout
                    if (time.time()-start > self.timeout):
                        raise exceptions.OpenlabTimeoutError(f"Getting results took longer than {self.timeout} seconds. To adjust this value, change the Simulation instance's timeout value.")

                    # Check status
                    status = self.get_status()     
                    if self.is_running is True:
                        if status ==  "Completed":
                            raise exceptions.SimulationCompleted(f"Sim {self.sim_id} was unexpectedly completed")
                        if status == "Aborted":
                            raise exceptions.SimulationAborted(f"Sim {self.sim_id} was unexpectedly aborted")
                    # Increase wait time. Something is taking a long time
                    time.sleep(1)
                
                else:
                    attempts = attempts + 1
                    if attempts == self.http_client.max_results_attempts:                        
                        if self.timeStep is not  None and self.timeStep > 1:
                            # First step always takes some time probably because initializing
                            self.logger.warning(f"Something is taking a long time at timestep {timeStep}")

                    time.sleep(0.02)
            
            try:
                for timeStep in range(timeStepFrom, timeStepTo+1):
                    connection = res.get("Connection")
                    if connection:
                        if connection.get(timeStep) == 1:
                            #check if it just started connecting
                            if self.connecting_previously == False:
                                self.logger.info("Connecting new pipe")
                            
                            self.connecting_previously = True
                            self.currently_connecting = True

                        elif self.currently_connecting == True:
                            #this will only trigger when res[timeStep]['Connection'] == 0 and flag hasn't been reset
                            self.logger.info("Done Connecting Pipe")
                            self.currently_connecting = False

                    ##assign each result from the client to its respected result dictionary in simulation class
                    for tag in tags:
                        if tag in res.keys():
                            try:
                                getattr(self.results, tag)[timeStep] = res[tag][timeStep]
                            except TypeError:
                                self.logger.error("Type Error. Time step: {}; Tag: {}".format(timeStep, tag))
                            except AttributeError:
                                self.logger.error("Tag '{}' is not a recognized OpenLab result tag".format(tag))

            except AttributeError:
                self.logger.warning(f"Attribute Error. Results were not properly assigned for timestep {timeStep}")

        return res
    
    def stop(self, timeStep=None):
        """
        Complete the simulation instance
        """
        self.logger.info("Ending simulation {}".format(self.sim_id))
        self.http_client.end_simulation(self.sim_id, timeStep)
        self.has_been_stopped = True

    @property
    def end_simulation_on_exiting(self):
        return self._end_simulation_on_exiting
    @end_simulation_on_exiting.setter
    def end_simulation_on_exiting(self, value):
        self._end_simulation_on_exiting = value

def stop_running_simulations():
    """
    Exit code that ends all running simulations
    """
    number_of_sims = len(Simulation._registry)
    if number_of_sims > 0:
        openlab_logger.info("Exiting Code...")
        try:
            #loop through all the client simulations
            for simulation in Simulation:
                status = simulation.get_status()
                sim_id = simulation.sim_id

                #stop the simulation if it is running, initializing, or created
                active = status == "Running" or status == "Initializing" or status == "Created"
                already_ended = simulation.has_been_stopped
                
                if active and not already_ended:
                    openlab_logger.info("Simulation {} is still {}".format(sim_id, status))
                    if simulation.end_simulation_on_exiting == True:
                        simulation.stop()
                    else:
                        openlab_logger.info("Sim {} was not ended because end_simulation_on_exiting was set to false".format(sim_id))
        except exceptions.SimulationNotFound:
            pass

#register the functions to run at exit
atexit.register(stop_running_simulations)
