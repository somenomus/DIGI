import logging

#=========Advanced Settings=========#
#Crendtials
credentials_location = 'keyring' #'keyring' or 'account' ; Default is 'keyring'. 
environment = 'prod' #'prod' , 'dev', 'build' , 'local'

#Logging
log = True #whether or not to log respective to below level
log_level = logging.INFO # Critical, Error, Warning, Info, Debug, Notset
save_logs = False

#Network
network_proxies = {}
verify = True #True/False (Strongly advice against setting this to False) or path to CA_BUNDLE file or directory.
#Note from requests library: If directory, it must be processed using the c_rehas utility supplied with OpenSSL

#===================================#


#Don't need to change these
client_id = 'OpenLab'
OPENLAB_URL= 'https://live.openlab.app'
#OPENLAB_URL= 'https://dev.openlab.app'
#OPENLAB_URL= 'http://localhost:8888'

#NOTE when changing any of the above after installation, an uninstall/reinstall might be necessary
