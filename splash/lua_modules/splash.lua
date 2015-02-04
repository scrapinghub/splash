--
-- Python Splash commands return `ok, result` pairs; this decorator
-- raises an error if "ok" is false and returns "result" otherwise.
--
local function unwraps_errors(func)
  return function(...)
    local ok, result = func(...)
    if not ok then
      error(result, 2)
    else
      return result
    end
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
    print("raises_async","calling func(...)")
    ok, err, raise = func(...)
    print("raises_async",ok,err,raise)
    if ok == nil and raise then
      print("raising error")
      error(err, 2)
    else
      print("sending ok,err")
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
-- This decorator expects function return value to be a Python list
-- and unpacks it to Lua multiple return values.
--
local function unpacks_multiple_return_values(func)
  return function(...)
    -- Max allowed list size is 10; it is more than enough for
    -- functions which return multiple values. This trick is needed
    -- to handle `nil` as a first value correctly.
    return table.unpack(func(...), 1, 10)
  end
end

--
-- Lua wrapper for Splash Python object.
--
-- It hides attributes that should not be exposed,
-- wraps async methods to `coroutine.yield` and fixes Lua <-> Python
-- error handling.
--
local Splash = {}
Splash.__index = Splash

function Splash.create(py_splash)
  local self = {args=py_splash.args}
  setmetatable(self, Splash)

  -- Create Lua splash:<...> methods from Python Splash object:
  for key, opts in pairs(py_splash.commands) do
    local command = drops_self_argument(py_splash[key])

    if opts.returns_error_flag then
      command = unwraps_errors(command)
    end

    if opts.is_async then
      command = yields_result(command)
    end

    if opts.can_raise_async then
      command = raises_async(command)
    end

    if opts.multiple_return_values then
      command = unpacks_multiple_return_values(command)
    end

    self[key] = command
  end

  return self
end

--
-- Create jsfunc method from jsfunc_private.
-- It is required to handle errors properly.
--
function Splash:jsfunc(...)
  local func = self:jsfunc_private(...)
  return unwraps_errors(func)
end


return Splash
