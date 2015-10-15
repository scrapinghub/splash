--
-- A wrapper for Response objects returned by Splash
--
local wraputils = require("wraputils")

local Request = {}
local Request_private = {}

function Request._create(py_request)
  local self = {info=py_request.info}
  setmetatable(self, Request)

  -- copy informational fields to the top level
  for key, value in pairs(py_request.info) do
    self[key] = value
  end
  wraputils.wrap_exposed_object(py_request, self, Request, Request_private, false)
  return self
end

return Request