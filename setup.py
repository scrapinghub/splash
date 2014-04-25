setup_args = {
    'name': 'splash',
    'version': '1.0',
    'packages': ['splash'],
    'url': 'https://github.com/scrapinghub/splash',
    'description': 'A javascript rendered with a HTTP API',
    'long_description': open('docs/index.rst').read(),
    'author': 'Scrapinghub',
    'maintainer': 'Scrapinghub',
    'maintainer_email': 'info@scrapinghub.com',
    'license': 'BSD',
    'scripts': ['bin/splash'],
    'classifiers': [
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.6',
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
    setup_args['install_requires'] = ['Twisted', 'qt4reactor', 'psutil']

setup(**setup_args)
