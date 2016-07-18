--
-- A wrapper for __extras object. 
-- It is used to safely expose additional functions
-- to Lua runtime.
--
local wraputils = require("wraputils")

local Extras = {}
local Extras_private = {}

Extras.__index = Extras

function Extras._create(py_extras)
  local extras = {}
  wraputils.wrap_exposed_object(py_extras, extras, Extras, Extras_private, false)
  return extras
end

return Extras
