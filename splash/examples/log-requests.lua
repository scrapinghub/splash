treat = require("treat")

local urls = {}
splash:on_request(function(request)
  table.insert(urls, request.url)
end)

assert(splash:go(splash.args.url))
return treat.as_array(urls)
