--
-- Lua autocompletion utilities for IPython kernel
--
local lexer = require('vendor/lexer')
-- local inspect = require('vendor/inspect')
local completer = {}


--
-- Tokenize Lua source code
--
function completer.tokenize(src)
  local res = {}
  local filter = {space=true, comments=true}
  local options = {number=true, string=true}

  for tp, value in lexer.lua(src, filter, options) do
      res[#res+1] = {tp=tp, value=value}
  end
  return res
end


--
-- Return all string table keys for which values passes `value_ok` test.
--
function completer.get_table_keys(tbl, value_ok)
  local res = {}
  for k, v in pairs(tbl) do
    if type(k) == "string" and value_ok(k, v) then
      res[#res+1] = k
    end
  end
  return res
end


--
-- Return all string metatable.__index keys with values passing `value_ok` test.
--
function completer.get_metatable_keys(obj, value_ok)
  local mt = getmetatable(obj)
  if type(mt) ~= 'table' then return {} end
  local index = mt.__index
  if type(index) == 'table' then
    return completer.get_table_keys(index, value_ok)
  elseif type(index) == 'function' then
    -- Assume index function eventually gets values from metatable itself.
    -- This is not always correct, but that's better than nothing.
    return completer.get_table_keys(mt, value_ok)
  else
    return {}
  end
end


--
-- Return all attribute names of an object.
--
function completer.obj_attrs(obj, no_methods, only_methods)
  local tp = type(obj)

  local function value_ok(k, v)
    local is_meth = type(v) == 'function'
    if is_meth and no_methods then return false end
    if not is_meth and only_methods then return false end
    return true
  end

  if tp == "nil" then
    return {}
  end

  if tp == "string" then
    return completer.get_metatable_keys(obj, value_ok)
  end

  -- todo: strings, functions, ...?

  if tp == "table" then
    local keys = completer.get_table_keys(obj, value_ok)
    local mt_keys = completer.get_metatable_keys(obj, value_ok)
    for idx, k in ipairs(mt_keys) do
      keys[#keys+1] = k
    end
    return keys
  end

  return {}
end

--
-- Return an object given its lookup names chain.
--
function completer.resolve_obj(names_chain)
  if #names_chain == 0 then
    error("invalid attributes chain")
  end

  local obj = _G
  for idx, attr in ipairs(names_chain) do
    obj = obj[attr]
  end

  return obj
end

--
-- Return all attribute names of a global variable or its attribute,
-- resolving names lookup chain.
--
function completer.attrs(names_chain, no_methods, only_methods)
  local obj = completer.resolve_obj(names_chain)
  return completer.obj_attrs(obj, no_methods, only_methods)
end


return completer
