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
local function unwraps_errors(func, nlevels)
  if nlevels == nil then
    -- assertx is tail-call-optimized and extra stack level is not
    -- created, hence nlevels==1.
    nlevels = 1
  end
  return function(...)
    return assertx(nlevels, func(...))
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


local PRIVATE_PREFIX = "private_"

local function is_private_name(key)
  return string.find(key, "^" .. PRIVATE_PREFIX) ~= nil
end

--
-- Create a Lua wrapper for a Python object.
--
-- * Lua methods are created for Python methods wrapped in @command.
-- * Async methods are wrapped to `coroutine.yield`.
-- * Lua <-> Python error handling is fixed.
-- * Private methods are stored in `private_self`, public methods are 
--   stored in `self`.
--
local function wrap_exposed_object(py_object, self, private_self, async)
  -- Create lua_object:<...> methods from py_object methods:
  for key, opts in pairs(py_object.commands) do
    local command = py_object[key]

    if opts.sets_callback then
      command = sets_callback(command, py_object.tmp_storage)
    end

    command = drops_self_argument(command)

    if opts.returns_error_flag then
      local nlevels = nil
      if is_private_name(key) then
        -- private functions are wrapped, so nlevels
        -- is set to 2 to show error line number in user code
        nlevels = 2
      end
      command = unwraps_errors(command, nlevels)
    end

    if async then
      if opts.is_async then
        command = yields_result(command)
      end

      if opts.can_raise_async then
        command = raises_async(command)
      end
    end
    
    if is_private_name(key) then
      local short_key = string.sub(key, PRIVATE_PREFIX:len()+1)
      private_self[short_key] = command
    else
      self[key] = command
    end
  end

end

--
-- Handle @lua_property decorators.
--
function setup_property_access(py_object, self, cls)
  local setters = {}
  local getters = {}
  for key, opts in pairs(py_object.lua_properties) do
    local setter = unwraps_errors(drops_self_argument(py_object[key]))
    local getter = unwraps_errors(drops_self_argument(py_object[opts.getter_method]))
    getters[opts.name] = getter
    setters[opts.name] = setter
  end
  
  function cls:__newindex(index, value)
    if setters[index] then
      setters[index](self, value)
    else
      rawset(cls, index, value)
    end  
  end
  
  function cls:__index(index)
    if getters[index] then
      return getters[index](self)
    else
      return rawget(cls, index)
    end
  end
end

--
-- Lua wrapper for Splash Python object.
--
local Splash = {}
local Splash_private = {}

function Splash._create(py_splash)
  local self = {args=py_splash.args}
  setmetatable(self, Splash)
  wrap_exposed_object(py_splash, self, Splash_private, true)
  setup_property_access(py_splash, self, Splash)
  return self
end

--
-- Create jsfunc method from private_jsfunc.
-- It is required to handle errors properly.
--
function Splash:jsfunc(...)
  local func = Splash_private.jsfunc(self, ...)
  return unwraps_errors(func)
end

--
-- Pass wrapped `request` object to `on_request` callback.
--
local Request = {}
local Request_private = {}

function Request._create(py_request)
  local self = {info=py_request.info}
  setmetatable(self, Request)

  -- copy informational fields to the top level
  for key, value in pairs(py_request.info) do
    self[key] = value
  end
  wrap_exposed_object(py_request, self, Request_private, false)
  setup_property_access(py_request, self, Request)
  return self
end

function Splash:on_request(cb)
  Splash_private.on_request(self, function(py_request)
    local req = Request._create(py_request)
    return cb(req)
  end)
end

local Response = {}
local Response_private = {}

function Response._create(py_reply)
  local self = {
    headers=py_reply.headers,
    info=py_reply.info,
    request=py_reply.request,
  }
  setmetatable(self, Response)

  -- convert har headers to something more convenient
  local _request_headers = {}
  for name, value in pairs(py_reply.request["headers"]) do
    _request_headers[value["name"]] = value["value"]
  end
  py_reply.request["headers"] = _request_headers

  -- take some keys from py_reply.info
  -- but not all (we don't want mess har headers with response headers)
  local keys_from_reply_info = {"status", "url", "ok"}

  for key, value in pairs(keys_from_reply_info) do
    self[value] = py_reply.info[value]
  end

  wrap_exposed_object(py_reply, self, Response_private, false)
  setup_property_access(py_reply, self, Response)
  return self
end

function Splash:on_response_headers(cb)
  Splash_private.on_response_headers(self, function (response)
    local res = Response._create(response)
    return cb(res)
  end)
end

--
-- Timer Lua wrapper
--

local Timer = {}
local Timer_private

function Timer._create(py_timer)
  local self = {}
  setmetatable(self, Timer)
  wrap_exposed_object(py_timer, self, Timer_private, false)
  setup_property_access(py_timer, self, Timer)
  return self
end

function Splash:call_later(cb, timeout)
  local py_timer = Splash_private.call_later(self, cb, timeout)
  return Timer._create(py_timer)
end

return Splash
