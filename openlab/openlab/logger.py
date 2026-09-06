import logging
import logging.config
import os
import inspect
import time
import tempfile

import openlab.credentials as credentials

#import user settings
log = credentials.log
log_level = credentials.log_level

def setUpRootLog():
    """
    Sets up root log when none are present:
    Retrives log and log_level from openlab.credentials.py
    If log == true, console uses log_level, and file logger uses DEBUG
    If log == false, log_level for both handlers are overriden to critical
    File log path uses <openlab directory>.openlab.log and it gets overwridden everytime
    """
    level = log_level
    if log is False:
        level = logging.CRITICAL
    
    rootLogger = logging.getLogger('')
    
    # Check if there are already root handlers. Otherwise we duplicate logs
    if len(rootLogger.handlers) == 0:
        # Create Console Handler
        ch = logging.StreamHandler()

        ch_fmt = '%(asctime)s [%(levelname)s] %(message)s'
        ch_datefmt = '%H:%M:%S'
        ch_formatter = logging.Formatter(ch_fmt, ch_datefmt)
        
        ch.setLevel(level)
        ch.setFormatter(ch_formatter)
        
        rootLogger.addHandler(ch)

        if credentials.save_logs:
            # Get the location of the installed OpenLab Library
            tmp_dir = tempfile.gettempdir()

            log_dir = os.path.join(tmp_dir, "openlab","logs")

            if not os.path.isdir(log_dir):
                os.makedirs(log_dir)

            tp = tempfile.NamedTemporaryFile(
                dir=log_dir,
                prefix="openlab-log-",
                delete=False)

            log_path = tp.name
            # Create File Handler
            fh = logging.FileHandler(log_path)
            # Formatter for file(f) and console(c) handlers
            fh_fmt = '%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s'
            fh_datefmt = '%Y-%m-%d %H:%M:%S'
            fh_formatter = logging.Formatter(fh_fmt, fh_datefmt)

            
            # Finish setup                
            fh.setLevel(level)
            fh.setFormatter(fh_formatter)
            rootLogger.addHandler(fh)
        
    return


def makeLogger(name):
    """
    Returns a logger with settings from openlab.credentials.py.
    No handlers are attached so setUpRootLog() must be called locally
    """
    # Create a logger
    logger = logging.getLogger(name)
    
    # Override log_level if log is set to False
    level = log_level
    if log is False:
        level = logging.CRITICAL
    
    logger.setLevel(level)
    
    return logger