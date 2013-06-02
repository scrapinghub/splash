
_REQUIRED = object()

class BadRequest(Exception):
    pass

def getarg(request, name, default=_REQUIRED, type=str, range=None):
    if name in request.args:
        value = type(request.args[name][0])
        if range is not None and not (range[0] < value < range[1]):
            raise BadRequest("Argument %r out of range (%d-%d)" % (name, range[0], range[1]))
        return value
    elif default is _REQUIRED:
        raise BadRequest("Missing argument: %s" % name)
    else:
        return default

