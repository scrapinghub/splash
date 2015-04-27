--
-- Lua wrapper for 'request' object passed to on_request callback.
--

local Request = {}
Request.__index = Request

function Request._create(py_request)
  local self = {info=py_request.info}
  setmetatable(self, Request)
  
  -- copy informational fields
  for key, value in pairs(py_request.info) do
    self[key] = value
  end
  
  return self
end

return Request