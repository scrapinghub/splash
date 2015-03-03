__version__ = '1.5'

from distutils.version import LooseVersion
version_info = tuple(LooseVersion(__version__).version)
__all__ = ['__version__', 'version_info']
