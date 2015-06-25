-- This function works very much like standard Lua assert, but:
--
-- * the first argument is the stack level to report the error at (1 being
--   current level, like for `error` function)
-- * it strips the flag if it evaluates to true
-- * it does not take a message parameter and thus will always preserve all
--   elements of the tuple
--
local function assertx(nlevels, ok, ...)
  if not ok then
    error(select(1, ...), 1 + nlevels)
  else
    return ...
  end
end


--
-- Python Splash commands return
--
--     ok, result1, [ result2, ... ]
--
-- tuples.  If "ok" is false, this decorator raises an error using "result1" as
-- message.  Otherwise, it returns
--
--     result1, [result2, ...]
--
local function unwraps_errors(func)
  return function(...)
    -- Here assertx is tail-call-optimized and extra stack level is not
    -- created, hence nlevels==1.
    return assertx(1, func(...))
  end
end


--
-- Python methods don't want explicit 'self' argument;
-- this decorator adds a dummy 'self' argument to allow Lua
-- methods syntax.
--
local function drops_self_argument(func)
  return function(self, ...)
    return func(...)
  end
end


--
-- Allows an async function to raise a Lua error by returning ok, err, raise.
--
-- If raise is true and ok is nil, then an error will be raised using res
-- as the reason.
--
local function raises_async(func)
  return function(...)
    local ok, err, raise = func(...)
    if ok == nil and raise then
      error(err, 2)
    else
      return ok, err
    end
  end
end

--
-- This decorator makes function yield the result instead of returning it
--
local function yields_result(func)
  return function(...)
    -- XXX: can Lua code access func(...) result
    -- from here? It should be prevented.

    -- The code below could be just "return coroutine.yield(func(...))";
    -- it is more complex because of error handling: errors are catched
    -- and reraised to preserve the original line number.
    local f = function (...)
      return table.pack(coroutine.yield(func(...)))
    end
    local ok, res = pcall(f, ...)
    if ok then
      return table.unpack(res)
    else
      error(res, 2)
    end
  end
end

--
-- A decorator that fixes an issue with passing callbacks from Lua to Python
-- by putting the callback to a table provided by the caller.
-- See https://github.com/scoder/lupa/pull/49 for more.
--
local function sets_callback(func, storage)
  return function(cb, ...)
    storage[1] = cb
    return func(...)
  end
end

--
-- Lua wrapper for Splash Python object.
--
-- It hides attributes that should not be exposed,
-- wraps async methods to `coroutine.yield` and fixes Lua <-> Python
-- error handling.
--
local Splash = {}

local private = {}
local PRIVATE_PREFIX = "private_"

function Splash._create(py_splash)
  local self = {
    args=py_splash.args,
    _setters={},
    _getters={}
  }
  setmetatable(self, Splash)

  -- Create Lua splash:<...> methods from Python Splash object:
  for key, opts in pairs(py_splash.commands) do
    local command = py_splash[key]

    if opts.sets_callback then
      command = sets_callback(command, py_splash.tmp_storage)
    end

    command = drops_self_argument(command)

    if opts.returns_error_flag then
      command = unwraps_errors(command)
    end

    if opts.is_async then
      command = yields_result(command)
    end

    if opts.can_raise_async then
      command = raises_async(command)
    end

    if key:find("^" .. PRIVATE_PREFIX) ~= nil then
      local short_key = key:sub(PRIVATE_PREFIX:len()+1)
      private[short_key] = command
    else
      self[key] = command
    end
  end

  -- Set attribute handler functions
  for key, opts in pairs(py_splash.lua_properties) do
    local func = drops_self_argument(py_splash[key])
    self._getters[opts.name] = drops_self_argument(
                                            py_splash[opts.getter_method])
    self._setters[opts.name] = func
  end

  return self
end

--
-- Apply attribute handlers.
--
function Splash:__newindex( index, value )
  if self._setters[index] then
    self._setters[index](self, value)
  else
    rawset(Splash, index, value)
  end
end

function Splash:__index(index)
  if self._getters[index] then
    return self._getters[index](self)
  else
    return rawget(Splash, index)
  end
end

--
-- Create jsfunc method from private_jsfunc.
-- It is required to handle errors properly.
--
function Splash:jsfunc(...)
  local func = private.jsfunc(self, ...)
  return unwraps_errors(func)
end

--
-- Pass wrapped `request` object to `on_request` callback.
--
local Request = {}
Request.__index = Request

function Request._create(py_request)
  local self = {info=py_request.info}
  setmetatable(self, Request)

  -- copy informational fields to the top level
  for key, value in pairs(py_request.info) do
    self[key] = value
  end

  for key, opts in pairs(py_request.commands) do
    local command = py_request[key]
    command = drops_self_argument(command)

    if opts.returns_error_flag then
      command = unwraps_errors(command)
    end

    self[key] = command
  end

  return self
end

function Splash:on_request(cb)
  private.on_request(self, function(py_request)
    local req = Request._create(py_request)
    return cb(req)
  end)
end

local Response = {}
Response.__index = Response

function Response._create(py_reply)
    local self = {response=py_reply.response}
    
    for key, opts in pairs(py_reply.commands) do
        local command = py_reply[key]
        command = drops_self_argument(command)

        if opts.returns_error_flag then
            command = unwraps_errors(command)
        end
        self[key] = command
    end
    
    return self
end

function Splash:on_response_headers(cb)
    private.on_response_headers(self, function (response)
        local res = Response._create(response)
        return cb(res)
    end)
end


return Splash
