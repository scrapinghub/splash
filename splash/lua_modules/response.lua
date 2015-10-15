--
-- A wrapper for Response objects returned by Splash
-- 
local wraputils = require("wraputils")
local treat = require("libs/treat")

local Response = {}
local Response_private = {}

function Response._create(py_response)
  local self = {
    headers=treat.as_case_insensitive(py_response.headers),
    request=py_response.request,
  }
  setmetatable(self, Response)

  -- convert har request headers to something more convenient
  -- FIXME: remove this, unify Request objects
  local _request_headers = {}
  for name, value in pairs(py_response.request["headers"]) do
    _request_headers[value["name"]] = value["value"]
  end
  self.request["headers"] = _request_headers
  
  wraputils.wrap_exposed_object(py_response, self, Response, Response_private, false)
  return self
end


return Response