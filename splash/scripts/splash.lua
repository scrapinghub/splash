--
-- Lua wrapper for Splash Python object.
--
-- It hides attributes that should not be exposed
-- and wraps async methods to `coroutine.yield`.
--
Splash = function (splash)
  local self = {args=splash.args}

  --
  -- Create Lua splash:<...> methods from Python Splash object.
  --
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

  function self._wait_restart_on_redirects(self, time, max_redirects)
    if not time then
      return true
    end

    local redirects_remaining = max_redirects
    while redirects_remaining do
      local ok, reason = self:wait{time, cancel_on_redirect=true}
      if reason ~= 'redirect' then
        return ok, reason
      end
      redirects_remaining = redirects_remaining - 1
    end
    error("Maximum number of redirects happen")
  end

  --
  -- Default rendering script which implements
  -- a common workflow: go to a page, wait for some time
  -- (similar to splash.qtrender.DefaultRenderScript).
  -- Currently it is incomplete.
  --
  function self.go_and_wait(self, args)
    -- content-type for error messages. Callers should set their
    -- own content-type before returning the result.
    self:set_result_content_type("text/plain; charset=utf-8")

    -- prepare & validate arguments
    local args = args or self.args
    local url = args.url
    if not url then
      error("'url' argument is required")
    end
    local wait = tonumber(args.wait)
    if not wait and args.viewport == "full" then
      error("non-zero 'wait' is required when viewport=='full'")
    end

    self:set_images_enabled(self.args.images)

    -- if viewport is 'full' it should be set only after waiting
    if args.viewport ~= "full" then
      self:set_viewport(args.viewport)
    end

    local ok, reason = self:go{url=url, baseurl=args.baseurl}
    if not ok then
      -- render.xxx endpoints don't return HTTP errors as errors,
      -- so here we also only raising an exception is an error is not
      -- caused by a 4xx or 5xx HTTP response.
      if reason:sub(0,4) ~= 'http' then
        error(reason)
      end
    end

    assert(self:_wait_restart_on_redirects(wait, 10))

    if args.viewport == "full" then
      self:set_viewport(args.viewport)
    end

  end

  return self
end
