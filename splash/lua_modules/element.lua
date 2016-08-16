--
-- A wrapper for Element objects
--
local wraputils = require("wraputils")


local Element = wraputils.create_metatable()

function Element._create(py_element)
  local element = {}
  return wraputils.wrap_exposed_object(py_element, element, Element)
end

function Element:node_method(...)
  local ok, func = self:_node_method(...)

  if not ok then
    return ok, func
  end

  return ok, wraputils.unwraps_python_result(func, 2)
end


function Element:node_property(...)
  local ok, result, is_element = self:_node_property(...)

  if not ok then
    return ok, result
  end

  if is_element then
    return true, Element._create(result)
  end

  return true, result
end

function Element:to_table()
  return { type = 'node', id = self.inner_id }
end


local ElementStyle = wraputils.create_metatable()

ElementStyle.__index = function(self, index)
  return self:_get_style(index)
end

ElementStyle.__newindex = function(self, index, value)
  return self:_set_style(index, value)
end

function ElementStyle._create(py_element_style)
  local element_style = {}
  return wraputils.wrap_exposed_object(py_element_style, element_style, ElementStyle)
end


function is_event_name(str)
  return string.sub(str, 1, 2) == 'on'
end

function get_event_name(str)
  return string.sub(str, 3, string.len(str))
end

local element_index = Element.__index
local element_newindex = Element.__newindex

Element.__index = function(self, index)
  if index == 'node' then
    return self
  end

  if index == 'style' then
    local py_element_style = self:_get_style()
    return ElementStyle._create(py_element_style)
  end

  if is_event_name(index) then
    local event_name = get_event_name(index)
    error("Cannot get " .. event_name .. " event handler")
  end

  return element_index(self, index)
end

Element.__newindex = function(self, index, value)
  if index == 'node' then
    error("Cannot set node field of the elmeent" )
  end

  if string.sub(index, 1, 2) == 'on' then
    local event_name = get_event_name(index)
    return self:_set_event_handler(event_name, value)
  end

  return element_newindex(self, index, value)
end

return Element