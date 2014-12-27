--
-- Lua wrapper for Splash Python object.
--
-- It hides attributes that should not be exposed,
-- wraps async methods to `coroutine.yield` and fixes Lua <-> Python
-- error handling.
--
Splash = function (py_splash)
  local self = {args=py_splash.args}

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
  -- This decorator makes function yields the result instead of returning it
  --
  local function yields_result(func)
    return function(...)
      -- XXX: can Lua code access func(...) result
      -- from here? It should be prevented.

      -- errors are catched and reraised to preserve the original line number
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
  -- Create Lua splash:<...> methods from Python Splash object.
  --
  for key, opts in pairs(py_splash.commands) do
    local command = drops_self_argument(py_splash[key])

    if opts.returns_error_flag then
      command = unwraps_errors(command)
    end

    if opts.is_async then
      command = yields_result(command)
    end

    self[key] = command
  end

  --
  -- Create jsfunc method from jsfunc_private.
  -- It is required to handle errors properly.
  --
  function self.jsfunc(...)
    local func = self.jsfunc_private(...)
    return unwraps_errors(func)
  end

  -- a helper function
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
      if string.sub(reason, 0,4) ~= 'http' then
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
