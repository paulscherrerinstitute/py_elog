#!/usr/bin/env python

import os
from setuptools import setup

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'Readme.md')).read()

setup(name='elog',
      version='0.9.1',
      description="Python library to access Elog.",
      long_description=README,
      author='Rok Vintar',
      classifiers=[
          'Programming Language :: Python:: 3.5',
          ],
      url = "http://packages.python.org/an_example_pypi_project",
      keywords='elog, electronic, logbook',
      packages=['elog'],
)