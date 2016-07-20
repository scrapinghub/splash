--
-- A module for creating Lua 'splash' object
-- from a Python 'splash' object.
--

local wraputils = require("wraputils")
local Response = require("response")
local Request = require("request")

--
-- Lua wrapper for Splash Python object.
--
local Splash = wraputils.create_metatable()
local Splash_private = {}
wraputils.set_metamethods(Splash)

function Splash._create(py_splash)
  local splash = { args = py_splash.args }
  wraputils.wrap_exposed_object(py_splash, splash, Splash, Splash_private, true)
  return splash
end

--
-- Create jsfunc method from private_jsfunc.
-- It is required to handle errors properly.
--
function Splash:jsfunc(...)
  local func = Splash_private.jsfunc(self, ...)
  return wraputils.unwraps_python_result(func)
end

--
-- Pass wrapped `request` and `response` objects to callbacks.
--
function Splash:on_request(cb)
  if type(cb) ~= 'function' then
    error("splash:on_request callback is not a function", 2)
  end
  Splash_private.on_request(self, function(py_request)
    local req = Request._create(py_request)
    return cb(req)
  end)
end

function Splash:on_response_headers(cb)
  if type(cb) ~= 'function' then
    error("splash:on_response_headers callback is not a function", 2)
  end
  Splash_private.on_response_headers(self, function(response)
    local res = Response._create(response)
    return cb(res)
  end)
end

function Splash:on_response(cb)
  if type(cb) ~= 'function' then
    error("splash:on_response callback is not a function", 2)
  end
  Splash_private.on_response(self, function(response)
    local res = Response._create(response)
    return cb(res)
  end)
end


--
-- Timer Lua wrapper
--
local Timer = wraputils.create_metatable()
local Timer_private = {}
wraputils.set_metamethods(Timer)

function Timer._create(py_timer)
  local timer = {}
  wraputils.wrap_exposed_object(py_timer, timer, Timer, Timer_private, true)
  return timer
end

function Splash:call_later(cb, delay)
  local py_timer = Splash_private.call_later(self, cb, delay)
  return Timer._create(py_timer)
end


return Splash
