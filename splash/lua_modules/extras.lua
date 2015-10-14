--
-- A wrapper for __extras object. 
-- It is used to safely expose additional functions
-- to Lua runtime.
--
local wraputils = require("wraputils")

local Extras = {}
local Extras_private = {}

function Extras._create(py_extras)
  local self = {}
  setmetatable(self, Extras)
  wraputils.wrap_exposed_object(py_extras, self, Extras_private, false)
  wraputils.setup_property_access(py_extras, self, Extras)
  return self
end

return Extras
