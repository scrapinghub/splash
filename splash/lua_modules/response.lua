--
-- A wrapper for Response objects returned by Splash
--
local wraputils = require("wraputils")
local treat = require("libs/treat")
local Request = require("request")

local Response = wraputils.create_metatable()

function Response._create(py_response)
  local response = {
    headers=treat.as_case_insensitive(py_response.headers),
    request=Request._create(py_response.request),
  }

  return wraputils.wrap_exposed_object(py_response, response, Response)
end


return Response
