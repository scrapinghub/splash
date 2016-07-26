--
-- A wrapper for Response objects returned by Splash
--
local wraputils = require("wraputils")
local treat = require("libs/treat")

local Request = wraputils.create_metatable()
wraputils.set_metamethods(Request)

function Request._create(py_request)
  local request = {
    info=py_request.info,
    headers=treat.as_case_insensitive(py_request.headers),
    url=py_request.url,
    method=py_request.method,
  }

  wraputils.wrap_exposed_object(py_request, request, Request)
  return request
end

return Request
