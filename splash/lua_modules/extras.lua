--
-- A wrapper for __extras object. 
-- It is used to safely expose additional functions
-- to Lua runtime.
--
local wraputils = require("wraputils")

local Extras = {}
local Extras_private = {}

function Extras._create(py_extras)
  local extras = {}
  setmetatable(extras, Extras)
  Extras.__index = Extras
  Extras.__newindex = rawset
  wraputils.wrap_exposed_object(py_extras, extras, Extras_private, false)
  return extras
end

return Extras
