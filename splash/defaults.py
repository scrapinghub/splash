
# timeouts
TIMEOUT = 30
WAIT_TIME = 0.0
RESOURCE_TIMEOUT = 0.0

MAX_TIMEOUT = 60.0
MAX_WAIT_TIME = 10.0

# Default size of browser window.  As there're no decorations, this affects
# both "window.inner*" and "window.outer*" values.
VIEWPORT_SIZE = '1024x768'

# Window size limitations.
VIEWPORT_MAX_WIDTH = 20000
VIEWPORT_MAX_HEIGTH = 20000
VIEWPORT_MAX_AREA = 4000*4000

MAX_WIDTH = 1920
MAX_HEIGTH = 1080

AUTOLOAD_IMAGES = 1

# If 'raster', PNG images will be rescaled after rendering as regular images.
# If 'vector', PNG image will be rescaled during rendering which is faster and
# crisper, but may cause rendering artifacts.
IMAGE_SCALE_METHOD = 'raster'

# This value has the same meaning as "level" kwarg of :func:`zlib.compress`:
# - 0 means no compression at all
# - 1 means best speed, lowest compression ratio
# - 9 means best compression, lowest speed
#
# The default is 1, because it is twice as fast as 9 and produces only 15%
# larger files.
PNG_COMPRESSION_LEVEL = 1

# 75 is Pillow default. Values above 95 should be avoided;
# 100 disables portions of the JPEG compression algorithm,
# and results in large files with hardly any gain in image quality.
JPEG_QUALITY = 75

# There's a bug in Qt that manifests itself when width or height of rendering
# surface (aka the png image) is more than 32768.  Usually, this is solved by
# rendering the image in tiled manner and obviously, TILE_MAXSIZE must not
# exceed that value.
#
# Other than that, the setting is a tradeoff between performance and memory
# usage, because QImage that acts as a rendering surface is quite a resource
# hog.  So, if you increase tile size you may end up using a lot more memory,
# but there is less image pasting and the rendering is faster.  As of now, 2048
# size is chosen to fit commonly used 1080p resolution in one tile.
TILE_MAXSIZE = 2048

# defaults for render.json endpoint
DO_HTML = 0
DO_IFRAMES = 0
DO_PNG = 0
DO_JPEG = 0
SHOW_SCRIPT = 0
SHOW_CONSOLE = 0
SHOW_HISTORY = 0
SHOW_HAR = 0

# servers
SPLASH_PORT = 8050
PROXY_PORT = 8051
MANHOLE_PORT = 5023
MANHOLE_USERNAME = 'admin'
MANHOLE_PASSWORD = 'admin'

# pool options
SLOTS = 50

# argument cache option
ARGUMENT_CACHE_MAX_ENTRIES = 500

# security options
ALLOWED_SCHEMES = ['http', 'https', 'data', 'ftp', 'sftp', 'ws', 'wss']
JS_CROSS_DOMAIN_ENABLED = False
PRIVATE_MODE = True

# logging
VERBOSITY = 1

# plugins (e.g. flash)
PLUGINS_ENABLED = False

# response content
RESPONSE_BODY_ENABLED = False
