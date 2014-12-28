#!/usr/bin/env python3

from setuptools import setup
import re

version_file = 'pybrscan/_version.py'
line = open(version_file, 'r').readline()
match = re.compile(r'^__version__\s*=\s*\'(\d+\.\d+\.\d+)\'$').match(line)
if match:
    version = match.group(1)
else:
    raise RuntimeError('Could not find version in: %s' % line)

setup(
    name='Locker',
    version=version,
    author='BB',
    author_email='run2fail@users.noreply.github.com',
    packages=['pybrscan'],
    scripts=['bin/pybrscan'],
    url='https://github.com/run2fail/pybrscan',
    license='LICENSE',
    description='Register computer for scan/email/... to pc service on Brother devices',
    long_description=open('README.rst').read(),
    install_requires=[
        'pysnmp',
        'Pillow',
        'netifaces',
        'Click',
        'daemonocle',
    ],
)
