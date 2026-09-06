import logging
import os
import sys
import inspect
import time
import requests
import ssl
import urllib
import OpenSSL
import pkg_resources
from requests_oauthlib import OAuth2Session
from oauthlib.oauth2.rfc6749.clients.base import Client
from oauthlib.oauth2.rfc6749.parameters import (parse_authorization_code_response,
                          parse_token_response, prepare_grant_uri,
                          prepare_token_request)

import openlab

credentials_location = openlab.credentials.credentials_location #'keyring' or 'account'
environment = openlab.credentials.environment #'prod'

credentials = openlab.login.get_credentials(credentials_location, environment)
#email = credentials['user']
#api_key = credentials['key']
#client_id = credentials['client_id']
#url = credentials['url']
#network_proxies = credentials['proxies']

#Import logger name from OpenLab directory and initialize it
logger_name = openlab.openlab_logger.logger_name
logger = logging.getLogger(logger_name)

#default ports
default_http_port = 80
default_https_port = 443

div_msg = "----------{}----------"

current_directory = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
logger.info("Current Directory: {}".format(current_directory))

#get info about ssl 
logger.debug(div_msg.format("SSL INFO"))
print("Getting SSL Info")

logger.info("OpenSSL version Number: {}".format(ssl.OPENSSL_VERSION))
logger.info("SSL Default Verify Paths: {}".format(ssl.get_default_verify_paths()))
logger.info("Requests Certs Location: {}".format(requests.certs.where()))

try:
    openssl_context = OpenSSL.SSL.Context(OpenSSL.SSL.SSLv23_METHOD)
    logger.info("OpenSSL Context: {}".format(openssl_context))
    logger.info("OpenSSL Context get cert Store: {}".format(openssl_context.get_cert_store()))
except Exception as e:
    logger.error("Problem getting openssl context. Error {}".format(e))

try:
    context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
    logger.info("SSL Context: {}".format(context))
    logger.info("SSL Context Cert Store Stats: {}".format(context.cert_store_stats()))
except Exception as e:
    logger.error("Problem getting ssl context. Error {}".format(e))

try:
    server_certificates = ssl.get_server_certificate(('https://live.openlab.app',default_https_port))
    logger.info("SSL server certificate from live.openlab.app:443: {}".format(server_certificates))
except Exception as e:
    logger.error("Problem getting server certificate. Error: {}".format(e))
                
logger.debug(div_msg.format("SSL INFO Completed"))

def check_for_environmental_proxies():
    """Checks for environmentally set HTTP_PROXY and HTTPS_PROXY which can be set from a command window.
        Alteranatively you can pass these in as a dictionary to the openlab http_client
        Returns an empty dictionary if none were found"""
    logger.debug("Checking for environemntally set proxies")
    #execute all get proxy requests once or until proxies is not empty 
    proxies = {}
    while proxies == {}:
        proxies = urllib.request.getproxies()
        logger.debug(".getproxies returned: {}".format(proxies))
        proxies = urllib.request.getproxies_environment()
        logger.debug(".getproxies_environemnt returned: {}".format(proxies))
        proxies = urllib.request.getproxies_registry()
        logger.debug(".getproxies returned: {}".format(proxies))
        break
    logger.debug("Check for proxies returning: {}".format(proxies))
    return proxies

def check_for_proxies(**kwargs):
    logger.debug("kwargs passed in to check_for_proxies: {}".format(kwargs))
    
    passed_in_proxies = kwargs.get('proxies')
    logger.debug("kwargs.get('proxies') in check_for_proxies: {}".format(passed_in_proxies))
    
    #if proxies were passed in and not empty
    if 'proxies' in kwargs and passed_in_proxies:       
        #check type
        if type(passed_in_proxies) is not dict:
            logger.error(
                "Passed_in_proxies: {} was not a dict. Attempting to get environmental proxies instead".format(
                passed_in_proxies))
            return check_for_environmental_proxies()                 
        else:
            #use proxies that were passed in
            proxies = passed_in_proxies
            logger.debug("Using proxies that were passed in: {}".format(proxies))
            return proxies
    else:
        #check for environemntal proxies if none were passed in
        logger.debug("No proxies were passed in")
        return check_for_environmental_proxies() 

class openlab_client(object):
    def __init__(self, auth_data):
        logger.debug("....Initializing openlab client....")
        logger.debug("auth_data passed in to openlab_client(): {}".format(auth_data))
        self.email = auth_data['user']
        self.api_key = auth_data['key']
        self.client_id = auth_data['client_id']
        self.url = auth_data['url']
        self.proxies = auth_data['proxies']
        self.client = login(self.email,self.api_key,self.url,self.client_id,proxies = self.proxies)

    def whoami(self):
        logger.debug("Who am i call")
        logger.info("self.client.proxies : {}".format(self.client.proxies))
        r=self.client.get(self.url+"/users/whoami")
        return r

class OpenlabApplicationClient(Client):
    """
    Custom ApplicationClient based on oauthlib's WebApplicationClient in ormder to pass in custom grant type
    """

    def __init__(self, client_id, code=None, **kwargs):
        super(OpenlabApplicationClient, self).__init__(client_id, **kwargs)
        self.code = code

    def prepare_request_uri(self, uri, redirect_uri=None, scope=None,
                            state=None, **kwargs):
            
        return prepare_grant_uri(uri, self.client_id, 'code', 
                                 redirect_uri=redirect_uri, scope=scope, state=state, **kwargs)

    def prepare_request_body(self, client_id=None, code=None, body='', redirect_uri=None, **kwargs):
        code = code or self.code
        return prepare_token_request('openlab_api_key', code=code, body=body,
                                     client_id=self.client_id, redirect_uri=redirect_uri, **kwargs)

    def parse_request_uri_response(self, uri, state=None):
        response = parse_authorization_code_response(uri, state=state)
        self._populate_attributes(response)
        return response

def urllib_test(url, proxies = {}):
    """Simple get test using urlllib"""

    logger.debug("Get request using urllib library to {} with proxies: {}".format(url,proxies))
    try:
        proxies = check_for_proxies(proxies = proxies)
        proxy_support = urllib.request.ProxyHandler(proxies)
        opener = urllib.request.build_opener(proxy_support)
        urllib.request.install_opener(opener)
        with urllib.request.urlopen(url) as response:
            html = response.read()
        logger.info("HTML response from urrlib request to {}: {}".format(url,html))
    except Exception as e:
        logger.error("Urllib failed to read {}. Error: {}".format(url,e))
    
def simple_get(url, proxies = {}):
    """Simple get request"""
    logger.debug("Get request using requests library to {} with proxies {}".format(url, proxies))
    try:
        proxies = check_for_proxies(proxies = proxies)
        r = requests.get(url, proxies = proxies)
        logger.info("Get request to {} returned: {}".format(
            url, r.text))
        return r
    except Exception as e:
        logger.error("Error getting response from {}. Error: {}".format(url, e))
        
def login(email,api_key,url,client_id, **kwargs):
    #logger.debug("kwargs in login: {}".format(**kwargs))
    proxies = check_for_proxies(**kwargs)
    logger.info("Email: {} \n API KEY: {} \n url: {} \n client_id: {} \n proxies: {} \n kwargs: {} \n".format(
        email,api_key,url,client_id,proxies,kwargs))
             
    client = OpenlabApplicationClient(client_id=client_id)
    oauth = OAuth2Session(client = client)
    oauth.proxies = proxies
    logger.debug("Fetching Token")
    try:
        token = oauth.fetch_token(token_url = url+"/connect/token", key = api_key, username = email,
                                    client_id = client_id,proxies = proxies,include_client_id=True)
        logger.info("Token: {}".format(token))
    except Exception as e:
        logger.error("Error fetching token: {}".format(e))
        print("Problem fetching token. Error =", e)
    return oauth

logger.debug(div_msg.format("Testing urllib requests"))
print("Testing urllib request")
                
urllib_test("https://httpbin.org/ip", proxies = credentials['proxies'])
urllib_test("https://live.openlab.app", proxies = credentials['proxies'])

logger.debug(div_msg.format("Testing simple get requests with no user/keys requirements"))
print("Testing requests")
simple_get("https://httpbin.org/ip", proxies = credentials['proxies'])
simple_get("https://live.openlab.app", proxies = credentials['proxies'])

logger.debug(div_msg.format("Testing OpenLab Client and token fetch"))
print("Testing OpenLab login")
                
session = None
try:
    session = openlab_client(credentials)
except Exception as e:
    print("Failure initializing openlab http client. Error: ",e)
    logger.error("Error in openlab_client instance creation. Error {}".format(e))

if session:
    logger.info("OAuth2Session proxies: {}".format(session.client.proxies))
    logger.info("OAuth2Session auth: {}".format(session.client.auth))
    logger.info("OAuth2Session cert: {}".format(session.client.cert))

    logger.debug(div_msg.format("Testing Openlab Credentials with whoami call"))      
    try:
        whoami = session.whoami()
        logger.info("whoami status code: {}".format(whoami.status_code))
        logger.info("whoami data: {}".format(whoami.text))
        print("Who Am I: ", whoami.text)
        
    except Exception as e:
        logger.error("Problem logging into network test. Error {}".format(e))
        print("Problem calling whoami. Error: ", e)
else:
    logger.error("Could not try openlab whoami called because openlab http client was not initialized")

