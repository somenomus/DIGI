import io
import os
import sys
from shutil import rmtree

from setuptools import find_packages, setup, Command

# Package meta-data
# Pull version from source without importing
# since we can't import something we haven't built yet :)
#exec(open('version.py').read())

NAME = "openlab"

REQUIRED = [
	"oauthlib>=2.0.7", "requests>=2.20.0", "requests-oauthlib>=0.4",
	"validators", "datetime", "matplotlib", "uuid","keyring", "numpy",
	"outdated>=0.2.0"
]

here = os.path.abspath(os.path.dirname(__file__))

setup(
	name = NAME,
	version='2.5.7',
	url='https://live.openlab.app',
	description = "A python client for OpenLab Drilling.",
	author='NORCE',
	author_email='andrew.holsaeter@norceresearch.no',
	license='NORCE COPYRIGHT: Do not distribute without approval by NORCE',
	packages = find_packages(),
	#packages=['openlab'],
	install_requires = REQUIRED,
	include_package_data = True,
	classifiers = [
		  # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
		'Development Status :: 4 - Beta',
		'Programming Language :: Python :: 3.6',
		'Intended Audience :: Developers',
	]
)
