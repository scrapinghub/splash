__version__ = '3.5'

from distutils.version import LooseVersion
version_info = tuple(LooseVersion(__version__).version)
__all__ = ['__version__', 'version_info']
