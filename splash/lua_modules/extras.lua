--
-- A wrapper for __extras object. 
-- It is used to safely expose additional functions
-- to Lua runtime.
--
local wraputils = require("wraputils")

local Extras = wraputils.create_metatable()

function Extras._create(py_extras)
  local extras = {}
  return wraputils.wrap_exposed_object(py_extras, extras, Extras)
end

return Extras
