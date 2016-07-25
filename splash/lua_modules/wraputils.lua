--
-- This modules provides utilities to access Python
-- objects from Lua. It should be used together with
-- utilities in qtrender_lua.
--

-- This function works very much like standard Lua assert, but:
--
-- * the first argument is the stack level to report the error at (1 being
--   current level, like for `error` function)
-- * it strips the flag if it evaluates to true
-- * it does not take a message parameter and thus will always preserve all
--   elements of the tuple
--
local function assertx(nlevels, ok, ...)
  if not ok then
    -- print("Assertx nlevels=", nlevels, "tb: ", debug.traceback())
    local msg = tostring(select(1, ...))
    error(msg, 1 + nlevels)
  else
    return ...
  end
end


-- Python Splash commands return
--
--   operation, [ result1, result2, ... ]
--
-- tuples.  Operation can be one of the following:
--
--   * "return": return the rest of the tuple
--
--   * "yield": yield the rest of the tuple with coroutine.yield
--
--   * "raise": raise an error using the rest of the tuple
--
local function unwrap_python_result(error_nlevels, op, ...)
  if op == 'return' then
    return ...
  elseif op == 'raise' then
    assertx(error_nlevels, nil, ...)
  elseif op == 'yield' then
    return unwrap_python_result(error_nlevels, coroutine.yield(...))
  else
    error('Invalid operation: ' .. tostring(op))
  end
end


local function unwraps_python_result(func, nlevels)
  if nlevels == nil then
    -- nlevels is passed straight to the corresponding assertx func.
    nlevels = 1
  end
  return function(...)
    return unwrap_python_result(1 + nlevels, func(...))
  end
end


--
-- Python methods don't want explicit 'self' argument;
-- this decorator adds a dummy 'self' argument to allow Lua
-- methods syntax.
--
local function drops_self_argument(func)
  return function(self, ...)
    return func(...)
  end
end


--
-- A decorator that fixes an issue with passing callbacks from Lua to Python
-- by putting the callback to a table provided by the caller.
-- See https://github.com/scoder/lupa/pull/49 for more.
--
local function sets_callback(func, storage)
  return function(cb, ...)
    storage[1] = cb
    return func(...)
  end
end


local PRIVATE_PREFIX = "private_"

local function is_private_name(key)
  return string.find(key, "^" .. PRIVATE_PREFIX) ~= nil
end


--
-- Create a Lua wrapper for a Python object.
--
-- * Lua methods are created for Python methods wrapped in @command.
-- * Async methods are wrapped with `coroutine.yield`.
-- * Lua <-> Python error handling is fixed.
-- * Private methods are stored in `private_self`, public methods are
--   stored in `self`.
--
local function setup_commands(py_object, self, private_self)
  -- Create lua_object:<...> methods from py_object methods:
  for key, opts in pairs(py_object.commands) do
    local command = py_object[key]

    if opts.sets_callback then
      command = sets_callback(command, py_object.tmp_storage)
    end

    command = drops_self_argument(command)

    local nlevels = 1
    if is_private_name(key) then
      -- private functions are wrapped, so nlevels is set to 2 to show error
      -- line number in user code
      nlevels = 2
    end
    command = unwraps_python_result(command, nlevels)

    if is_private_name(key) then
      local short_key = string.sub(key, PRIVATE_PREFIX:len() + 1)
      private_self[short_key] = command
    else
      -- avoid custom setter
      rawset(self, key, command)
    end
  end
end


--
-- Handle @lua_property decorators.
--
local function setup_property_access(py_object, self, cls)
  rawset(self, '__getters', {})
  rawset(self, '__setters', {})

  for name, opts in pairs(py_object.lua_properties) do
    self.__getters[name] = unwraps_python_result(drops_self_argument(py_object[opts.getter]))
    if opts.setter ~= nil then
      self.__setters[name] = unwraps_python_result(drops_self_argument(py_object[opts.setter]))
    else
      self.__setters[name] = function()
        error("Attribute " .. name .. " is read-only.", 2)
      end
    end
  end
end


--
-- Create a Lua wrapper for a Python object.
--
local function wrap_exposed_object(py_object, self, cls, private_self)
  setmetatable(self, cls)
  setup_commands(py_object, self, private_self)
  setup_property_access(py_object, self, cls)
end


--
-- Return a metatable for a wrapped Python object
--
-- WARNING: setting this metatable on an empty table might cause infinite
-- recursion during the lookup of __getters & __setters.  To minimize the risk,
-- the calling code should add these fields to the table ASAP, preferably with
-- rawset.
local function create_metatable()
  local cls = {
    __wrapped = true
  }

  cls.__index = function(self, index)
    if self.__getters[index] then
      return self.__getters[index](self)
    else
      return rawget(cls, index)
    end
  end

  cls.__newindex = function(self, index, value)
    if self.__setters[index] then
      return self.__setters[index](self, value)
    else
      return rawset(self, index, value)
    end
  end

  return cls
end


--
-- Return true if an object is a wrapped Python object
--
local function is_wrapped(obj)
  local mt = getmetatable(obj)
  if type(mt) ~= 'table' then
    return false
  end
  return mt.__wrapped == true
end

-- Exposed API
return {
  assertx = assertx,
  unwraps_python_result = unwraps_python_result,
  drops_self_argument = drops_self_argument,
  raises_async = raises_async,
  yields_result = yields_result,
  sets_callback = sets_callback,
  is_private_name = is_private_name,
  setup_commands = setup_commands,
  setup_property_access = setup_property_access,
  wrap_exposed_object = wrap_exposed_object,
  create_metatable = create_metatable,
  is_wrapped = is_wrapped,
}
