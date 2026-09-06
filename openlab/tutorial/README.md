## 3 Steps before you start
### Create a virtual environment

## Before Use
- Check to make sure you have python 3.6 or greater installed by opening a cmd terminal and running
    `python -V`(python/python3 command dependent on your computer's environmental vraiables)

## Creating vvirtual Environment
- Open a terminal window at the same location as this README file (located under python/tutorial). 
- Run `python -m venv openlab-env`
- Run `openlab-env\Scripts\activate.bat` (windows)

Now your virtual environment is activated, but you still need to populate it with the necessary packages. Before that, you have to setup your OpenLab credentials

### Set your credentials
- Open credentials.py with any text editor
- Input our e-mail address exactly how it appears in live.openlab.app (case sensitive)
- Input the generated API key from live.openlab.app. (Login, click on your user settings and then OpenLab Server.)
- Save the file

### Install the required packages
- Make sure you are in the directory that contains `requirements.txt`. 
- From your terminal window run `pip install -r requirements.txt` This will install all the necessary packages for this tutorial and could take several minutes.
                            or `pip install -r requirements.txt --user` if machine does not have admin rights.
- Finally run `jupyter notebook` and a web browser window will appear (for development: `jupyter notebook --port 9999`)