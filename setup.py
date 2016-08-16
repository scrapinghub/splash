#!/usr/bin/env python
import os
import re
from setuptools import setup


def _path(*args):
    return os.path.join(os.path.dirname(__file__), *args)


def get_version():
    filename = _path('splash', '__init__.py')
    with open(filename, 'rb') as fp:
        contents = fp.read().decode('utf8')
        return re.search(r"__version__ = ['\"](.+)['\"]", contents).group(1)


setup_args = {
    'name': 'splash',
    'version': get_version(),
    'url': 'https://github.com/scrapinghub/splash',
    'description': 'A javascript rendered with a HTTP API',
    'long_description': open('README.rst').read(),
    'author': 'Scrapinghub',
    'author_email': 'info@scrapinghub.com',
    'maintainer': 'Scrapinghub',
    'maintainer_email': 'info@scrapinghub.com',
    'license': 'BSD',
    'scripts': ['bin/splash'],
    'packages': ['splash', 'splash.har', 'splash.kernel'],
    'package_data': {'splash': [
        'vendor/harviewer/webapp/css/*.css',
        'vendor/harviewer/webapp/css/images/*.*',
        'vendor/harviewer/webapp/css/images/menu/*.*',
        'vendor/harviewer/webapp/scripts/*.*',
        'vendor/harviewer/webapp/scripts/core/*.*',
        'vendor/harviewer/webapp/scripts/domplate/*.*',
        'vendor/harviewer/webapp/scripts/downloadify/js/*.*',
        'vendor/harviewer/webapp/scripts/downloadify/src/*.*',
        'vendor/harviewer/webapp/scripts/downloadify/media/*.*',
        'vendor/harviewer/webapp/scripts/excanvas/*.*',
        'vendor/harviewer/webapp/scripts/jquery-plugins/*.*',
        'vendor/harviewer/webapp/scripts/json-query/*.*',
        'vendor/harviewer/webapp/scripts/nls/*.*',
        'vendor/harviewer/webapp/scripts/preview/*.*',
        'vendor/harviewer/webapp/scripts/syntax-highlighter/*.js',
        'vendor/harviewer/webapp/scripts/tabs/*.*',
        'vendor/harviewer/webapp/har.js',
        'ui/*.*',

        'examples/*.lua',
        'lua_modules/*.lua',
        'lua_modules/libs/*.lua',
        'lua_modules/vendor/*.lua',
        'kernel/inspections/*.json',
        'kernel/kernels/splash-py2/*.*',
        'kernel/kernels/splash-py3/*.*',
    ]},
    'zip_safe': False,
    'install_requires': [
        'Twisted < 16.3.0',
        'qt5reactor',
        'psutil',
        'adblockparser',
        'xvfbwrapper',
        'funcparserlib',
        'Pillow',
    ],
    'classifiers': [
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Environment :: No Input/Output (Daemon)',
        'Topic :: Internet :: WWW/HTTP',
    ],
}


setup(**setup_args)
