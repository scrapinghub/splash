--
-- Lua render script that emulates render.png endpoint.
-- Behaviour is not 100% the same as in render.png.
-- This script is used in tests.
--

function main(splash)
  splash:go_and_wait(splash.args)
  splash:set_result_content_type("image/png")
  return splash:png{
    width=splash.args.width,
    height=splash.args.height
  }
end
