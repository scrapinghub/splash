--
-- Lua render script that emulates render.html endpoint.
-- Behaviour is not 100% the same as in render.html.
-- This script is used in tests.
--

function main(splash)
  splash:go_and_wait(splash.args)
  splash:set_result_content_type("text/html; charset=utf-8")
  return splash:html()
end
