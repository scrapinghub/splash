--
-- Lua autocompletion utilities for IPython kernel
--
local lexer = require('vendor/lexer')
local completer = {}


--
-- Tokenize Lua source code
--
function completer.tokenize(src)
  local res = {}
  local filter = {space=false, comments=true}
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
    if type(k) == "string" and value_ok(v) then
      res[#res+1] = k
    end
  end
  return res
end


--
-- Return all attributes of a global variable or its attribute.
--
function completer.attrs(names_chain, no_methods, only_methods)
  if #names_chain == 0 then
    error("invalid attributes chain")
  end

  local obj = _G
  for idx, attr in ipairs(names_chain) do
    obj = obj[attr]
  end

  local tp = type(obj)

  local function value_ok(v)
    local is_meth = type(v) == 'function'
    if is_meth and no_methods then return false end
    if not is_meth and only_methods then return false end
    return true
  end

  if tp == "nil" then
    return {}
  end

  -- todo: strings, functions, ...?

  if tp == "table" then
    return completer.get_table_keys(obj, value_ok)
  end

  return {}
end


return completer
