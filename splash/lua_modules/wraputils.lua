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
    local msg = tostring(select(1, ...))
    error(msg, 1 + nlevels)
  else
    return ...
  end
end


--
-- Python Splash commands return
--
--     ok, result1, [ result2, ... ]
--
-- tuples.  If "ok" is false, this decorator raises an error using "result1" as
-- message.  Otherwise, it returns
--
--     result1, [result2, ...]
--
local function unwraps_errors(func, nlevels)
  if nlevels == nil then
    -- assertx is tail-call-optimized and extra stack level is not
    -- created, hence nlevels==1.
    nlevels = 1
  end
  return function(...)
    return assertx(nlevels, func(...))
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
-- Allows an async function to raise a Lua error by returning ok, err, raise.
--
-- If raise is true and ok is nil, then an error will be raised using res
-- as the reason.
--
local function raises_async(func)
  return function(...)
    local ok, err, raise = func(...)
    if ok == nil and raise then
      error(err, 2)
    else
      return ok, err
    end
  end
end

--
-- This decorator makes function yield the result instead of returning it
--
local function yields_result(func)
  return function(...)
    -- XXX: can Lua code access func(...) result
    -- from here? It should be prevented.

    -- The code below could be just "return coroutine.yield(func(...))";
    -- it is more complex because of error handling: errors are catched
    -- and reraised to preserve the original line number.
    local f = function (...)
      return table.pack(coroutine.yield(func(...)))
    end
    local ok, res = pcall(f, ...)
    if ok then
      return table.unpack(res)
    else
      error(res, 2)
    end
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
local function setup_commands(py_object, self, private_self, async)
  -- Create lua_object:<...> methods from py_object methods:
  for key, opts in pairs(py_object.commands) do
    local command = py_object[key]

    if opts.sets_callback then
      command = sets_callback(command, py_object.tmp_storage)
    end

    command = drops_self_argument(command)

    if opts.returns_error_flag then
      local nlevels = nil
      if is_private_name(key) then
        -- private functions are wrapped, so nlevels
        -- is set to 2 to show error line number in user code
        nlevels = 2
      end
      command = unwraps_errors(command, nlevels)
    end

    if async then
      if opts.is_async then
        command = yields_result(command)
      end

      if opts.can_raise_async then
        command = raises_async(command)
      end
    end

    if is_private_name(key) then
      local short_key = string.sub(key, PRIVATE_PREFIX:len()+1)
      private_self[short_key] = command
    else
      self[key] = command
    end
  end

end

--
-- Handle @lua_property decorators.
--
local function setup_property_access(py_object, self, cls)
  local setters = {}
  local getters = {}
  for name, opts in pairs(py_object.lua_properties) do
    getters[name] = unwraps_errors(drops_self_argument(py_object[opts.getter]))
    if opts.setter ~= nil then
      setters[name] = unwraps_errors(drops_self_argument(py_object[opts.setter]))
    else
      setters[name] = function()
        error("Attribute " .. name .. " is read-only.", 2)
      end
    end
  end

  function cls:__newindex(index, value)
    if setters[index] then
      return setters[index](self, value)
    else
      return rawset(cls, index, value)
    end
  end

  function cls:__index(index)
    if getters[index] then
      return getters[index](self)
    else
      return rawget(cls, index)
    end
  end
end


--
-- Create a Lua wrapper for a Python object.
--
local function wrap_exposed_object(py_object, self, cls, private_self, async)
  setup_commands(py_object, self, private_self, async)
  setup_property_access(py_object, self, cls)
end


--
-- Return a metatable for a wrapped Python object
--
local function create_metatable()
  return {
    __wrapped=true
  }
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
  unwraps_errors = unwraps_errors,
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
