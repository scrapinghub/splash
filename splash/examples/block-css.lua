function main(splash, args)
  splash:on_response_headers(function(response)
    local ct = response.headers["Content-Type"]
    if ct == "text/css" then
      response.abort()
    end
  end)

  assert(splash:go(args.url))
  return {
    png=splash:png(),
    har=splash:har()
  }
end