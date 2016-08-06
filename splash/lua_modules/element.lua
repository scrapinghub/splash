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

return Element