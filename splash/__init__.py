__version__ = '2.3.3'

from distutils.version import LooseVersion
version_info = tuple(LooseVersion(__version__).version)
__all__ = ['__version__', 'version_info']
