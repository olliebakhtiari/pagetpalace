#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Note: To use the 'upload' functionality of this file, you must:
#   $ pipenv install twine --dev
import io
import os
import sys
from shutil import rmtree
from setuptools import find_packages, setup, Command

if sys.version_info[:2] < (3, 6):
    raise RuntimeError('Python Version 3.6+ Required.')

NAME = 'pagetpalace'
DESCRIPTION = 'Used to build live implementations of strategies.'
URL = 'https://github.com/olliebakhtiari/pagetpalace'
EMAIL = 'olliebakhtiari@gmail.com'
AUTHOR = 'Ollie Bakhtiari'
REQUIRES_PYTHON = '>=3.6.0'
VERSION = '0.1.0'
REQUIRED = [
    'boto3',
    'botocore',
    'certifi',
    'chardet',
    'docutils',
    'idna',
    'jmespath',
    'numpy',
    'pandas',
    'plotly',
    'pysimplemodel',
    'python-dateutil',
    'python-status',
    'pytz',
    'requests',
    'retrying',
    's3transfer',
    'six',
    'tenacity',
    'urllib3',
]
here = os.path.abspath(os.path.dirname(__file__))
try:
    with io.open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
        long_description = '\n' + f.read()
except FileNotFoundError:
    long_description = DESCRIPTION

# Load the package's __version__.py module as a dictionary.
about = {}
if not VERSION:
    project_slug = NAME.lower().replace("-", "_").replace(" ", "_")
    with open(os.path.join(here, project_slug, '__version__.py')) as f:
        exec(f.read(), about)
else:
    about['__version__'] = VERSION


class UploadCommand(Command):
    """ Support setup.py upload. """

    description = 'Build and publish the package.'
    user_options = []

    @staticmethod
    def status(s):
        """ Prints things in bold. """
        print('\033[1m{0}\033[0m'.format(s))

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        try:
            self.status('Removing previous builds…')
            rmtree(os.path.join(here, 'dist'))
        except OSError:
            pass

        self.status('Building Source and Wheel (universal) distribution…')
        os.system('{0} setup.py sdist bdist_wheel --universal'.format(sys.executable))

        self.status('Uploading the package to PyPI via Twine…')
        os.system('twine upload dist/*')

        self.status('Pushing git tags…')
        os.system('git tag v{0}'.format(about['__version__']))
        os.system('git push --tags')

        sys.exit()


setup(
    name=NAME,
    version=about['__version__'],
    description=DESCRIPTION,
    long_description=long_description,
    long_description_content_type='text/markdown',
    author=AUTHOR,
    author_email=EMAIL,
    python_requires=REQUIRES_PYTHON,
    url=URL,
    packages=find_packages(
        include=['pagetpalace', 'pagetpalace.*'],
        exclude=["tests", "*.tests", "*.tests.*", "tests.*"],
    ),
    install_requires=REQUIRED,
    include_package_data=True,
    classifiers=[
        # Trove classifiers
        # Full list: https://pypi.python.org/pypi?%3Aaction=list_classifiers
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy'
    ],

    # $ setup.py publish support.
    cmdclass={
        'upload': UploadCommand,
    },
)
