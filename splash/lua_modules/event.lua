--
-- A wrapper for Events objects
--
local wraputils = require("wraputils")

local Event = {}

function Event._create(py_event)
  local event = {}
  return wraputils.wrap_exposed_object(py_event, event, Event)
end

local methods = { preventDefault = true, stopImmediatePropagation = true, stopPropagation = true }

local __index = Event.__index

Event.__index = function(self, index)
  if not methods[index] then
    return self:_get_property(index)
  end

  return __index(self, index)
end

return Event
