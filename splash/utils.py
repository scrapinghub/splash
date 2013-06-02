
_REQUIRED = object()

class BadRequest(Exception):
    pass

def getarg(request, name, default=_REQUIRED, type=str):
    if name in request.args:
        return type(request.args[name][0])
    elif default is _REQUIRED:
        raise BadRequest("Missing argument: %s" % name)
    else:
        return default

