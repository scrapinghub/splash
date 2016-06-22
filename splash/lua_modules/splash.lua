--
-- A module for creating Lua 'splash' object
-- from a Python 'splash' object.
--

local wraputils = require("wraputils")
local Response = require("response")
local Request = require("request")
local repr = require("repr")

--
-- Lua wrapper for Splash Python object.
--
local Splash = wraputils.create_metatable()


function Splash._create(py_splash)
  local splash = { args = py_splash.args }
  return wraputils.wrap_exposed_object(py_splash, splash, Splash)
end

--
-- Create jsfunc method from private_jsfunc.
-- It is required to handle errors properly.
--
function Splash:jsfunc(...)
  local func = self:_jsfunc(...)
  return wraputils.unwraps_python_result(func)
end

--
-- Pass wrapped `request` and `response` objects to callbacks.
--
function Splash:on_request(cb)
  if type(cb) ~= 'function' then
    error("splash:on_request callback is not a function", 2)
  end
  self:_on_request(function(py_request)
    local req = Request._create(py_request)
    return cb(req)
  end)
end

function Splash:on_response_headers(cb)
  if type(cb) ~= 'function' then
    error("splash:on_response_headers callback is not a function", 2)
  end
  self:_on_response_headers(function(response)
    local res = Response._create(response)
    return cb(res)
  end)
end

function Splash:on_response(cb)
  if type(cb) ~= 'function' then
    error("splash:on_response callback is not a function", 2)
  end
  self:_on_response(function(response)
    local res = Response._create(response)
    return cb(res)
  end)
end


--
-- Timer Lua wrapper
--
local Timer = wraputils.create_metatable()

function Timer._create(py_timer)
  local timer = {}
  return wraputils.wrap_exposed_object(py_timer, timer, Timer)
end

function Splash:call_later(cb, delay)
  local py_timer = self:_call_later(cb, delay)
  return Timer._create(py_timer)
end


--
-- Element Lua wrapper
--
local Element = wraputils.create_metatable()
local Element_private = {}
wraputils.set_metamethods(Element)

function Element._create(py_element)
  local element = {}
  wraputils.wrap_exposed_object(py_element, element, Element, Element_private, false)
  return element
end

function Element:node_method(...)
  local ok, func = Element_private.node_method(self, ...)

  if not ok then
    return ok, func
  end

  return ok, wraputils.unwraps_python_result(func, 2)
end


function Element:node_property(...)
  local ok, result, is_element = Splash_private.node_property(self, ...)

  if not ok then
    return ok, result
  end

  if is_element then
    return true, Element._create(result)
  end

  return true, result
end


function Splash:select(selector)
  local py_element = Splash_private.select(self, selector)
  return Element._create(py_element)
end


return Splash
