#!/usr/bin/env python

import os
from setuptools import setup

here = os.path.abspath(os.path.dirname(__file__))
README = open(os.path.join(here, 'Readme.md')).read()

setup(name='elog',
      version='1.3.4',
      description="Python library to access Elog.",
      long_description=README,
      author='Paul Scherrer Institute (PSI)',
      url="https://github.com/paulscherrerinstitute/py_elog",
      keywords='elog, electronic, logbook',
      packages=['elog'],
      # install_requires=[
      #     'requests', 'passlib', 'lxml'
      # ],
      )
