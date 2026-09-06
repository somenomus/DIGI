import logging
import os
import inspect
import time
import subprocess
import openlab

current_directory = os.path.dirname(
    os.path.abspath(inspect.getfile(inspect.currentframe())))
print(current_directory)

logger_name = openlab.openlab_logger.logger_name
log_path = openlab.openlab_logger.log_path
print("Running test scripts. Output will be output to ", log_path)
logger = logging.getLogger(logger_name)

def run_test(test):
    test_name = test.partition(".")[0]
    print("Running {} test".format(test_name))
    start = time.time()
    try:
        subprocess.check_call(["python", os.path.join(current_directory,test)])
        
    except Exception as e:
        print("Error opening {} test".format(test_name))
        logger.error("Failed to open {} test. Error: {}".format(test_name,e))
    elapsed = time.time()-start
    print("Completed {} test in {} s".format(test_name, elapsed))
    
start_time = time.time()
logger.debug("{0}Starting tests{0}".format('-'*15))
start_test_time = time.time()
run_test("environment.py")
run_test("user.py")
run_test("network.py")

time_elapsed = time.time()-start_time
logger.debug("Done with tests. It took {} seconds.".format(time_elapsed))
print("Test Scripts Completed in {} seconds".format(time_elapsed))
