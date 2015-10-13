--
-- A module for creating Lua 'splash' object 
-- from a Python 'splash' object.
-- 

local wraputils = require("wraputils")

--
-- Lua wrapper for Splash Python object.
--
local Splash = {}
local Splash_private = {}

function Splash._create(py_splash)
  local self = {args=py_splash.args}
  setmetatable(self, Splash)
  wraputils.wrap_exposed_object(py_splash, self, Splash_private, true)
  wraputils.setup_property_access(py_splash, self, Splash)
  return self
end

--
-- Create jsfunc method from private_jsfunc.
-- It is required to handle errors properly.
--
function Splash:jsfunc(...)
  local func = Splash_private.jsfunc(self, ...)
  return wraputils.unwraps_errors(func)
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
  wraputils.wrap_exposed_object(py_request, self, Request_private, false)
  wraputils.setup_property_access(py_request, self, Request)
  return self
end

function Splash:on_request(cb)
  if type(cb) ~= 'function' then
    error("splash:on_request callback is not a function", 2)
  end
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

  wraputils.wrap_exposed_object(py_reply, self, Response_private, false)
  wraputils.setup_property_access(py_reply, self, Response)
  return self
end

function Splash:on_response_headers(cb)
  if type(cb) ~= 'function' then
    error("splash:on_response_headers callback is not a function", 2)
  end
  Splash_private.on_response_headers(self, function (response)
    local res = Response._create(response)
    return cb(res)
  end)
end

function Splash:on_response(cb)
  if type(cb) ~= 'function' then
    error("splash:on_response callback is not a function", 2)
  end
  Splash_private.on_response(self, function (response)
    local res = Response._create(response)
    return cb(res)
  end)
end


--
-- Timer Lua wrapper
--
local Timer = {}
local Timer_private = {}

function Timer._create(py_timer)
  local self = {}
  setmetatable(self, Timer)
  wraputils.wrap_exposed_object(py_timer, self, Timer_private, true)
  wraputils.setup_property_access(py_timer, self, Timer)
  return self
end

function Splash:call_later(cb, delay)
  local py_timer = Splash_private.call_later(self, cb, delay)
  return Timer._create(py_timer)
end


return Splash
