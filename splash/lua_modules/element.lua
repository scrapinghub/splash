--
-- A wrapper for element object. 
-- It is used to safely expose additional functions
-- to Lua runtime.
--
local wraputils = require("wraputils")

local Element = {}
local Element_private = {}

function Element._create(py_element)
  local self = {}
  setmetatable(self, Element)
  wraputils.wrap_exposed_object(py_element, self, Element_private, false)
  wraputils.setup_property_access(py_element, self, Element)
  return self
end

return Element
