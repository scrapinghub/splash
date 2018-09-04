treat = require("treat")

function main(splash, args)
  local urls = {}
  splash:on_navigation_locked(function(request)
    table.insert(urls, request.url)
  end)

  assert(splash:go(splash.args.url))
  splash:lock_navigation()
  splash:select("a"):mouse_click()
  return treat.as_array(urls)
end