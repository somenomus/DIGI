#Following imports are for the OpenlabApplicationClient
from __future__ import absolute_import, unicode_literals
from oauthlib.oauth2.rfc6749.parameters import (parse_authorization_code_response,
                          parse_token_response, prepare_grant_uri,
                          prepare_token_request)                          
from oauthlib.oauth2.rfc6749.clients.base import Client
from requests_oauthlib import OAuth2Session, OAuth1Session
from oauthlib.oauth2 import InvalidGrantError
from openlab import credentials
from openlab import account
from openlab import logger

import importlib
import os
import validators
import json
import time
import inspect
import urllib
import keyring
from keyring.errors import NoKeyringError
import tempfile

#Get the location of the installed OpenLab Library
current_directory = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))

#exec credentials to force compile so to recognize any changes to credentials
exec(open(current_directory+"/credentials.py").read())


environments = {'prod': "https://live.openlab.app", 'dev' : "https://dev.openlab.app", 'build':"https://build.openlab.app", 'local':"http://localhost:8888"}
valid_environments = environments.keys()

reference_username = 'current_user' # For storing the active username account

logger = logger.makeLogger("openlab.login")

# Get OS specific temporary folder location
tmp_dir = tempfile.gettempdir()
tmp_openlab_dir = os.path.join(tmp_dir, "openlab")
token_file = "openlab_token.txt"
token_path = os.path.join(tmp_openlab_dir, token_file)

class OpenlabApplicationClient(Client):
    """
    Custom ApplicationClient based on oauthlib's WebApplicationClient in order to pass in custom grant type
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

def token_saver(token):
    """
    Saves the token so it can be used next time
    """
    logger.info("Saving token")
    
    # Create the temporary openlab directory if it doesn't exist
    if not os.path.isdir(tmp_openlab_dir):
        os.makedirs(tmp_openlab_dir)
    
    with open(token_path, 'w') as f:
        json.dump(token, f)

def load_token():
    """
    Returns False if there is no temporary openlab folder
    Returns False if there is no token file in that temporary openlab folder
    Otherwise, it returns the token file, converted to dictionary object
    """
    # Check if there is a temporary openlab directory
    if not os.path.isdir(tmp_openlab_dir):
        return False

    # Check if there is a token file in that temporary openlab directory
    if not os.path.isfile(token_path):
        return False

    #open the token file and read it
    token = open(token_path, 'r')
    token_text = token.read()
    #close the token file
    token.close()

    #convert the json data so that we can search key,value pairings
    j = json.loads(token_text)
    
    return j


def get_expire_time():
    """
    Returns the expire time of a token if one exists
    """
    # Load token
    has_token = load_token()
    if has_token:
        return has_token['expires_at']
    else:
        logger.warning("No token exists")
        return

def token_handler(token, auth_data):
    """
    Sets up and returns an Oauth Session that will automatically handle token refreshing
    """
    #validate the url and email
    valid_url=validators.url(auth_data['url'])
    valid_user= validators.email(auth_data['user'])
    if not valid_url:
        raise ValueError('Invalid url: ' + auth_data['url'])
    if not valid_user:
        raise ValueError('Invalid email: ' + auth_data['user'])

    extra = {'client_id' : auth_data['client_id'],
              'key' : auth_data['key'], 'proxies' : auth_data['proxies']}

    #attempt to create client session to pass back
    client = OpenlabApplicationClient(client_id=auth_data['client_id'])
    oauth = OAuth2Session(client = client, token = token, auto_refresh_url= auth_data['refresh_url'], auto_refresh_kwargs = extra, token_updater = token_saver)
    oauth.proxies = auth_data['proxies'] # probabily redundant
    
    return oauth

def check_for_proxies():
    """Checks for environmentally set HTTP_PROXY and HTTPS_PROXY which can be set from a command window.
        Alteranatively you can pass these in as a dictionary to the openlab http_client
        Returns an empty dictionary if none were found"""
    #execute all get proxy requests once or until proxies is not empty 
    proxies = {}
    while proxies == {}:
        try:
            proxies = urllib.request.getproxies()
            proxies = urllib.request.getproxies_environment()
            proxies = urllib.request.getproxies_registry() 
        except:
            pass
        
        break
    return proxies

def get_proxies(**kwargs):
    proxies = {}
    
    # give 1st priority to kwargs passed in
    if 'proxies' in kwargs:
        # use proxies that were passed in
        proxies = kwargs.get('proxies')
            
        # check type
        if type(proxies) is not dict:
            raise TypeError("proxies must be a dictionary")

    # give 2nd priority to kwargs in credentials
    elif len(credentials.network_proxies) > 0:
        proxies = credentials.network_proxies

    else:
        # check for environemntal proxies if none were passed in
        proxies = check_for_proxies()
    
    return proxies

def request_user_credentials(environment='prod'):
    """
    Asks user for email and api_key
    """
    if environment not in valid_environments:
        raise Exception("Invalid environment: {}\nValid environments: {}".format(environment, valid_environments))

    service = "_".join(["openlab",environment])

    # make a list of safe functions/variables for exec
    safe_list = ['username', 'apikey', 'licenseguid']
    safe_dict = dict([(k, locals().get(k, None)) for k in safe_list])

    input_text = input("Enter the python generated login script:\n")
    
    #format the string
    input_text.strip() #get rid of whitespace
    text = input_text.split() #split at spaces
    
    #assign each assignment
    for assignment in text:
        exec(assignment, {'__builtins__' : None} , safe_dict)

    name = safe_dict['username']
    api_key = safe_dict['apikey']
    license_id = safe_dict['licenseguid']

    # Again, we set an arbritary account's (i.e reference_username) password to the username inputted
    # This way we can keep track of the active account
    if name is not None and api_key is not None:
        try:
            keyring.set_password(service, reference_username, name)
            keyring.set_password(service, name + "_key", api_key)
            keyring.set_password(service, name +"_license", license_id)
        except:
            logger.warn("Problems setting credentials in keyring")
    else:
        return request_individual_credentials(environment)
    return {'email' : name, 'api_key' : api_key, 'licenseguid' : license_id}

def request_individual_credentials(environment='prod'):
    if environment not in valid_environments:
        raise Exception("Invalid environment: {}\nValid environments: {}".format(environment, valid_environments))

    service = "_".join(["openlab",environment])

    email = input("Username: ")
    if email is not None:
        try:
            keyring.set_password(service, reference_username, email)
        except:
            pass

    api_key = input("Api key: ")
    if api_key is not None and email is not None:
        try:
            keyring.set_password(service, email + "_key", api_key)
        except:
            pass


    license_id = input("License Guid: ")
    if license_id is not None and email is not None:
        try:
            keyring.set_password(service, email + "_license", license_id )
        except:
            pass

    return {'email' : email, 'api_key' : api_key, 'licenseguid' : license_id}

def _reload_account_module():
    return importlib.reload(account)

def _store_account_credentials(username, apikey, licenseguid):
    account_path = os.path.join(current_directory, "account.py")
    account_lines = [
        "#=========deprecated===========",
        '#User Settings - Individually change these or "Generate python Script" from live.openlab.app and paste here',
        f"username={username!r}",
        f"apikey={apikey!r}",
        f"licenseguid={licenseguid!r}",
        "#===============================",
    ]

    with open(account_path, 'w') as account_file:
        account_file.write("\n".join(account_lines) + "\n")

    return _reload_account_module()

def get_keyring_username(environment='prod'):
    """
    Gets the active openlab python account
    If one does not exist, it will prompt the user for one
    """
    if environment not in valid_environments:
        raise Exception("Invalid environment: {}\nValid environments: {}".format(environment, valid_environments))
    
    service = "_".join(["openlab",environment])

    #Treating username like a password
    email = None
    try:
        email = keyring.get_password(service, reference_username) #service ="openlab_prod" ; reference_username = "current_user"
    except:
        logger.warn("Problem getting email from keyring")
        email = None

    if email == None:
        account_module = _reload_account_module()
        if account_module.username is not None:
            try:
                keyring.set_password(service, reference_username, account_module.username)
            except NoKeyringError:
                logger.warning("No keyring backend available. Using email from account.py")
            except:
                logger.warn("Problem storing email from account.py in keyring")

            logger.info("Using email from accounts.py")
            email = account_module.username

    if email is None:
        logger.info("No OpenLab username exists yet for this environment...")
        email = request_user_credentials(environment)['email']

    return email

def get_keyring_password(username, environment = 'prod'):
    """
    Returns the openlab key associated with a username.
    If one does not exist, it will prompt the user for one
    """
    if environment not in valid_environments:
        raise Exception("Invalid environment: {}\nValid environments: {}".format(environment, valid_environments))
    
    service = "_".join(["openlab",environment])
    username += "_key"

    #get actual password
    password = None
    try:
        password = keyring.get_password(service, username)
    except:
        logger.warn("Problem getting api key from keychain")
        password = None

    if password is None:
        account_module = _reload_account_module()
        if account_module.apikey is not None:
            try:
                keyring.set_password(service, username, account_module.apikey)
            except NoKeyringError:
                logger.warning("No keyring backend available. Using api key from account.py")
            except:
                logger.warn("Problem storing api key from account.py in keyring")

            logger.info("Using password from accounts.py")
            return account_module.apikey
    if password is None:
        logger.info("No api_key associated with {}...\nInput Api Key: ".format(username))
        # FIXME
        api_key = request_user_credentials(environment)['api_key']
        try:
            keyring.set_password(service, username, api_key)
            return api_key
        except:
            password = api_key
  
    return password

def get_keyring_license(username, environment = 'prod'):
    """
    Returns the openlab license associated with a username.
    If one does not exist, it will prompt the user for one
    """
    if environment not in valid_environments:
        raise Exception("Invalid environment: {}\nValid environments: {}".format(environment, valid_environments))
    
    service = "_".join(["openlab",environment])
    
    username += "_license"

    license_id = None
    try:
        license_id = keyring.get_password(service, username)
    except:
        license_id = None
    if license_id is None:
        account_module = _reload_account_module()
        if account_module.licenseguid is not None:
            try:
                keyring.set_password(service, username, account_module.licenseguid)
            except NoKeyringError:
                logger.warning("No keyring backend available. Using license from account.py")
            except:
                logger.warn("Problem storing license from account.py in keyring")

            logger.info("Using license from accounts.py")
            return account_module.licenseguid

    if license_id is None:
        logger.info("No license exists yet for this environment. Default will be personal limits")
        answer = input(
            """
            No license exists yet for this environment.\n
            Default is personal license\n
            Would you like to add one? (y/n)
            """
            )
            
        if answer == 'y':
            return request_user_credentials(environment)['license_id']

    return license_id

def switch_license(environment ='prod'):
    if environment not in valid_environments:
        raise Exception("Invalid environment: {}\nValid environments: {}".format(environment, valid_environments))
    
    request_user_credentials(environment)
    
def switch_user(new_user, new_key, new_licenseguid=None, environment='prod'):
    """
    Deletes old openlab account/key combination and sets a new one
    """
    if environment not in valid_environments:
        raise Exception("Invalid environment: {}\nValid environments: {}".format(environment, valid_environments))
    
    service = "_".join(["openlab",environment])
    

    try:
        keyring.delete_password(service, reference_username)
    except:
        logger.info("No previous Openlab account detected")
    try:
        keyring.delete_password(service, new_user+"_key")
    except:
        logger.info("New user deteced. Creating a new username/key keychain")

    #set the username so we can find the email later without having to know it
    try:
        keyring.set_password(service, reference_username, new_user)
        keyring.set_password(service, new_user + "_key", new_key)
        if new_licenseguid:
            keyring.set_password(service, new_user + "_license", new_licenseguid)
    except NoKeyringError:
        _store_account_credentials(new_user, new_key, new_licenseguid)
        logger.warning("No keyring backend available. Stored credentials in account.py instead")

def clear_password(environment ='prod'):
    if environment not in valid_environments:
        raise Exception("Invalid environment: {}\nValid environments: {}".format(environment, valid_environments))
    
    service = "_".join(["openlab",environment])

    try:
        keyring.delete_password(service, reference_username)
    except:
        logger.warn("Problem clearing password")

def get_credentials(location = 'keyring', environment = 'prod', **kwargs):
    #get the credials/login info needed for logging in/getting token
    if environment not in valid_environments:
        raise Exception("Invalid environment: {}\nValid environments: {}".format(environment, valid_environments))
    username = None
    apikey = None
    licensguid = None
    c = dict()

    if 'url' in kwargs:
        c['url'] = kwargs['url']    
    else:
        c['url'] = environments.get(environment) #FIXME
        
    c['refresh_url'] = c['url'] + "/connect/token"

    # Give highest priority to passed-in Variables
    if 'username' in kwargs.keys():
        username = kwargs.get('username')
    if 'apikey' in kwargs.keys():
        apikey = kwargs.get('apikey')
    if 'licenseguid' in kwargs.keys():
        licensguid = kwargs.get('licenseguid')

    # Give second priority if location = "account"
    if location == 'account':
        try:
            account_module = _reload_account_module()
            c['user'] = username or account_module.username
            c['key'] = apikey or account_module.apikey
            c['license_id'] = licensguid or account_module.licenseguid
        except:
            logger.warn("Problem loading from accont")
            
    # Give last priority to default keyring
    elif location == 'keyring':
        c['user'] = username or get_keyring_username(environment)
        c['key'] = apikey or get_keyring_password(c['user'], environment)
        c['license_id'] = licensguid or get_keyring_license(c['user'], environment)

    c['client_id'] = 'OpenLab'

    c['proxies'] = get_proxies(**kwargs)

    c['verify'] = credentials.verify
    return c
    
def create_token(**kwargs):
    logger.info("Creating token")
    kwargs.setdefault('environment', "prod")
    kwargs.setdefault('location', "keyring")
    kwargs.setdefault('proxies', {})

    environment = kwargs.pop('environment')
    location = kwargs.pop('location')

    auth_data = get_credentials(location, environment, **kwargs)
    
    token = None

    client = OpenlabApplicationClient(client_id=auth_data['client_id'])
    oauth = OAuth2Session(client=client)  # this session will be be overwritten with one containing token details for refreshing, but we need it to fetch an initial token
    oauth.proxies = auth_data['proxies']
    oauth.verify = auth_data['verify']
    # create an initial token
    try:
        token = oauth.fetch_token(token_url = auth_data['url'] + "/connect/token",
            key = auth_data['key'], username = auth_data['user'], client_id=auth_data['client_id'],
            proxies = auth_data['proxies'], include_client_id=True)
    except InvalidGrantError:
        logger.error("Invalid Grant Error. Ensure the following account information is correct:\n"
              "email = {}\n"
              "key = {}\n"
              "url = {}\n".format(auth_data['user'], auth_data['key'], auth_data['url']))
        
    if token is not None:
        #save the token
        token_saver(token)
        return token_handler(token, auth_data) #overwrite the oauth so that we can refresh on the first time
    else:
        raise Exception("Problem creating a token. Check your credentials")