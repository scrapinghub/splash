--
-- A wrapper for Response objects returned by Splash
--
local wraputils = require("wraputils")
local treat = require("libs/treat")
local Request = require("request")

local Response = wraputils.create_metatable()
local Response_private = {}

function Response._create(py_response)
  local self = {
    headers=treat.as_case_insensitive(py_response.headers),
    request=Request._create(py_response.request),
  }
  setmetatable(self, Response)

  wraputils.wrap_exposed_object(py_response, self, Response, Response_private, false)
  return self
end


return Response
