import openlab

#initiate http_client_session
session = openlab.http_client()

#get configuration data
configs = session.configurations()

#show all theconfigs and their simulations if they have any
for config in configs:
    has_simulations = config["HasSimulations"]
    msg = "has" if has_simulations else "does not have"
    print("Configuration '{}' {} simulations".format(config["Name"],msg))
    if has_simulations:
        simulations = session.configuration_simulations(config["ConfigurationID"])
        #sort the simulations by update date
        sortedSimulations = sorted(simulations, key=lambda k:k['LastUpdatedDate'], reverse=True)
        for simulation in sortedSimulations:
            print("\tName: {:20}\tID: {:}\tLast Updated: {}\tCurrent Step: {}".format(
                simulation["Name"], simulation["SimulationID"], 
                simulation["LastUpdatedDate"],simulation["CurrentStep"]))