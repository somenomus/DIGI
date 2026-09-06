import logging
import os
import sys
import pkg_resources

import openlab
import pip # this throws error if imported before OAuth2Session 

#Import logger name from OpenLab directory and initialize it
logger_name = openlab.openlab_logger.logger_name
logger = logging.getLogger(logger_name)

logger.info("{0}Environment Information{0}".format('-'*10))
try:
    print("Getting Python Information")
    logger.debug("{0}Python Information{0}".format('-'*10))
    logger.info("Python version: {}".format(sys.version))
    logger.info("Python version info: {}".format(sys.version_info))
except Exception as e:
    print("Error getting python info. See Logs")
    logger.error("Problem getting Python information. Error: {}".format(e))

try:
    print("Getting system information")
    logger.info("Sys path: {}".format(sys.path))
    logger.info("Sys platform: {}".format(sys.platform))
except Exception as e:
    print("Error getting system info. Error: ", e)
    logger.error("Problem getting system info. Error: {}".format(e))

try:
    print("Getting available module information")
    logger.info("Pip installed distributions: {}".format(
        sorted(["%s==%s" % (i.key, i.version) for i in pip.get_installed_distributions()])))
    logger.info("PKG Resources Working Set: {}".format(
        sorted(["%s==%s" % (i.key, i.version) for i in pkg_resources.working_set]))) #should be the same
except Exception as e:
    print("Error getting modules. Error: ", e)
    logger.error("Problem getting modules. Error: {}".format(e))