--
-- A wrapper for Events objects
--
local wraputils = require("wraputils")

local Event = {}
local Event_private = {}

function Event._create(py_event)
  local event = {}
  wraputils.wrap_exposed_object(py_event, event, Event, Event_private)
  return event
end

local methods = { preventDefault = true, stopImmediatePropagation = true, stopPropagation = true }

local __index = Event.__index

Event.__index = function(self, index)
  if not methods[index] then
    return Event_private.get_property(self, index)
  end

  return __index(self, index)
end

return Event
