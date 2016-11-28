--
-- This module provides render_har, render_html and render_png methods
-- which emulate render.har, render.html and render.png endpoints.
-- They are used in tests; behaviour is not 100% the same.
--

local Splash = require("splash")

--
-- A method with a common workflow: go to a page, wait for some time.
-- splash.qtrender.DefaultRenderScript implements a similar logic in Python.
--
function Splash:go_and_wait(args)
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
  if not wait and (self.args.render_all or self.args.viewport == "full") then
    error("non-zero 'wait' is required when rendering whole page")
  end

  self.images_enabled = self.args.images

  -- if viewport is 'full' it should be set only after waiting
  if args.viewport ~= nil and args.viewport ~= "full" then
    local w, h = string.match(args.viewport, '^(%d+)x(%d+)')
    if w == nil or h == nil then
      error('Invalid viewport size format: ' .. args.viewport)
    end
    self:set_viewport_size(tonumber(w), tonumber(h))
  end

  -- set a resource timeout
  self.resource_timeout = args.resource_timeout
  self.response_body_enabled = args.response_body

  local ok, reason = self:go{url=url, baseurl=args.baseurl}
  if not ok then
    -- render.xxx endpoints don't return HTTP errors as errors,
    -- so here we also only raising an exception is an error is not
    -- caused by a 4xx or 5xx HTTP response.
    if reason == 'render_error' or reason == 'error' then
      self:set_result_status_code(502)
    elseif string.sub(reason, 0,4) ~= 'http' then
      error(reason)
    end
  end

  assert(self:wait_restart_on_redirects(wait, 10))
end


function Splash:wait_restart_on_redirects(time, max_redirects)
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
-- "Endpoints"
--

local emulation = {}


function emulation.render_har(splash)
  splash:go_and_wait(splash.args)
  return splash:har()
end


function emulation.render_html(splash)
  splash:go_and_wait(splash.args)
  splash:set_result_content_type("text/html; charset=utf-8")
  return splash:html()
end


function emulation.render_png(splash)
  splash:go_and_wait(splash.args)
  splash:set_result_content_type("image/png")
  local render_all = (splash.args.render_all or
                      splash.args.viewport == "full")
  return splash:png{
    width=splash.args.width,
    height=splash.args.height,
    render_all=render_all,
    scale_method=splash.args.scale_method,
  }
end


function emulation.render_jpeg(splash)
    splash:go_and_wait(splash.args)
    splash:set_result_content_type("image/jpeg")
    local render_all = (splash.args.render_all or
            splash.args.viewport == "full")
    return splash:jpeg{
        width=splash.args.width,
        height=splash.args.height,
        render_all=render_all,
        scale_method=splash.args.scale_method,
        quality=splash.args.quality,
    }
end


return emulation
