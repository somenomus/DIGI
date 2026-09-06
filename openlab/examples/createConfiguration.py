import openlab

# Initialize an openlab session
session = openlab.http_client()

# Get an existing configuration
config_id = "put config id here"
data = session.configuration_data(config_id)


# Double each UCS
for fs in data["FormationStrength"]:
    fs["UCS"] *= 2

# Create a new configuraition with the edited data
session.create_configuration("New Configuration", data)
