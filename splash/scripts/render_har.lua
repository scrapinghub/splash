--
-- Lua render script that emulates render.har endpoint.
-- Behaviour is not 100% the same as in render.har.
-- This script is used in tests.
--

function main(splash)
  splash:go_and_wait(splash.args)
  return splash:har()
end
