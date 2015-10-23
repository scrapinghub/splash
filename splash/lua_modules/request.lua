--
-- A wrapper for Response objects returned by Splash
--
local wraputils = require("wraputils")
local treat = require("libs/treat")

local Request = wraputils.create_metatable()
local Request_private = {}

function Request._create(py_request)
  local self = {
    info=py_request.info,
    headers=treat.as_case_insensitive(py_request.headers),
    url=py_request.url,
    method=py_request.method,
  }
  setmetatable(self, Request)

  wraputils.wrap_exposed_object(py_request, self, Request, Request_private, false)
  return self
end

return Request
