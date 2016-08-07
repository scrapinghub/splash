--
-- A wrapper for Element objects
--
local wraputils = require("wraputils")


local Element = wraputils.create_metatable()
local Element_private = {}
wraputils.set_metamethods(Element)

function Element._create(py_element)
  local element = {}
  wraputils.wrap_exposed_object(py_element, element, Element, Element_private, false)
  return element
end

function Element:node_method(...)
  local ok, func = Element_private.node_method(self, ...)

  if not ok then
    return ok, func
  end

  return ok, wraputils.unwraps_python_result(func, 2)
end


function Element:node_property(...)
  local ok, result, is_element = Splash_private.node_property(self, ...)

  if not ok then
    return ok, result
  end

  if is_element then
    return true, Element._create(result)
  end

  return true, result
end

function Element:serialize()
  return { type = 'node', id = self.inner_id }
end

function Element:style()
  return { type = 'node', id = self.inner_id }
end


local ElementStyle = wraputils.create_metatable()
local ElementStyle_private = {}

ElementStyle.__index = function(self, index)
  return ElementStyle_private.get_style(self, index)
end

ElementStyle.__newindex = function(self, index, value)
  return ElementStyle_private.set_style(self, index, value)
end

function ElementStyle._create(py_element_style)
  local element_style = {}
  wraputils.wrap_exposed_object(py_element_style, element_style, ElementStyle, ElementStyle_private, false)
  return element_style
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
  if index == 'style' then
    local py_element_style = Element_private.get_style(self)
    return ElementStyle._create(py_element_style)
  end

  if is_event_name(index) then
    local event_name = get_event_name(index)
    return Element_private.get_event_handler(self, event_name)
  end

  return element_index(self, index)
end

Element.__newindex = function(self, index, value)
  if string.sub(index, 1, 2) == 'on' then
    local event_name = get_event_name(index)
    return Element_private.set_event_handler(self, event_name, value)
  end

  return element_newindex(self, index, value)
end

return Element