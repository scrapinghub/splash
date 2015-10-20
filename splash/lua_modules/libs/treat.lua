local treat = {}

local wraputils = require("wraputils")

--
-- Mark a string as binary. It means it no longer
-- can be processed from Lua, but it can be
-- returned as a main() result as-is.
--
-- Binary objects are also auto-encoded to base64 when
-- encoding to JSON.
--
function treat.as_binary(s, content_type)
  if type(s) ~= 'userdata' and type(s) ~= 'string' then
    error("as_binary argument must be a string or a binary object", 2)
  end
  return __extras:treat_as_binary(s, content_type)
end


--
-- Get original string value and a content type of
-- a binary object created by treat.as_binary or
-- returned by one of Splash methods.
--
function treat.as_string(s)
  if type(s) ~= 'userdata' then
    return tostring(s)
  end
  return __extras:treat_as_string(s)
end


--
-- Mark a Lua table as an array. Such tables
-- will be represented as arrays when encoded to JSON.
-- This function modifies its argument inplace.
--
function treat.as_array(tbl)
  -- the same function is available in
  -- Splash Python code as lua._mark_table_as_array
  if type(tbl) ~= 'table' or wraputils.is_wrapped(tbl) then
    error('as_array argument must be a table', 2)
  end
  setmetatable(tbl, {__metatable="array"})
  return tbl
end


--
-- Make keys in a Lua table case-insensitive.
--
function treat.as_case_insensitive(tbl)
  local copy = {}
  local lowercase_copy = {}
  for k, v in pairs(tbl) do
    copy[k] = v
    lowercase_copy[k:lower()] = v
  end

  local mt = {
    __index = function(table, key)
      return lowercase_copy[key:lower()]
    end,
    __newindex = function(table, key, value)
      rawset(table, key, value)
      lowercase_copy[key:lower()] = value
    end
  }
  setmetatable(copy, mt)
  return copy
end


return treat
