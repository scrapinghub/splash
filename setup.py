#!/usr/bin/env python
import os
import re

def get_version():
    filename = os.path.join(os.path.dirname(__file__), 'splash', '__init__.py')
    with open(filename, 'r') as fp:
        contents = fp.read().decode('utf8')
        return re.search(r"__version__ = ['\"](.+)['\"]", contents).group(1)


setup_args = {
    'name': 'splash',
    'version': get_version(),
    'packages': ['splash'],
    'url': 'https://github.com/scrapinghub/splash',
    'description': 'A javascript rendered with a HTTP API',
    'long_description': open('README.rst').read(),
    'author': 'Scrapinghub',
    'author_email': 'info@scrapinghub.com',
    'maintainer': 'Scrapinghub',
    'maintainer_email': 'info@scrapinghub.com',
    'license': 'BSD',
    'scripts': ['bin/splash'],
    'classifiers': [
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Environment :: No Input/Output (Daemon)',
        'Topic :: Internet :: WWW/HTTP',
    ],
}


try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup
else:
    setup_args['install_requires'] = [
        'Twisted', 'qt4reactor', 'psutil', 'adblockparser'
    ]

setup(**setup_args)
