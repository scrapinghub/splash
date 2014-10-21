--
-- Lua wrapper for Splash Python object.
--
-- It hides attributes that should not be exposed
-- and wraps async methods to `coroutine.yield`.
--
Splash = function (splash)
  local self = {}

  for key, value in pairs(splash.commands) do

    -- XXX: value is a Python tuple wrapped by lupa,
    -- it is indexed from 0
    local command, is_async = value[0], value[1]

    if is_async then
      self[key] = function(self, ...)
        -- XXX: can Lua code access command(...) result
        -- from here? It should be prevented.
        return coroutine.yield(command(...))
      end
    else
      self[key] = function(self, ...)
        return command(...)
      end
    end
  end
  return self
end
