import logging
import openlab
import openlab.logger

#Import logger name from OpenLab directory and initialize it
logger_name = openlab.openlab_logger.logger_name
logger = logging.getLogger(logger_name)

print("Getting user information")
logger.info("{0}User Information{0}".format('-'*10))

email = openlab.credentials.email
api_key = openlab.credentials.api_key
client_id = openlab.credentials.client_id
url = openlab.credentials.OPENLAB_URL
network_proxies = openlab.credentials.network_proxies

logger.info("\n Email: {} \n API KEY: {} \n url: {} \n client_id: {} \n proxies: {}".format(
        email,api_key,url,client_id,network_proxies))