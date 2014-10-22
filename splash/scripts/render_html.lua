--
-- Lua render script that emulates render.html endpoint.
-- Behaviour is not 100% the same as in render.html.
-- This script is used in tests.
--

function main(splash)
  splash:set_result_content_type("text/html; charset=utf-8")

  local url = splash.args.url
  if not url then
    error("'url' argument is required")
  end

  local wait
  if splash.args.wait then
    wait = tonumber(splash.args.wait)
  end

  splash:set_viewport(splash.args.viewport)

  local baseurl = splash.args.baseurl
  assert(splash:go{url=url, baseurl=baseurl})

  if wait then
    splash:wait(wait)
  end

  return splash:html()
end
