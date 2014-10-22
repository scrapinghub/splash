--
-- Lua wrapper for Splash Python object.
--
-- It hides attributes that should not be exposed
-- and wraps async methods to `coroutine.yield`.
--
Splash = function (splash)
  local self = {args=splash.args}

  for key, is_async in pairs(splash.commands) do
    local command = splash[key]

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
