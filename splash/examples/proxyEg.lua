function main(splash)
  splash:on_request(function(request)
    request:set_proxy{
        host = "10.3.100.207",
        port = 8080,
        username = splash.args.username,
        password = splash.args.password,
    }
end)
  local url = splash.args.url
  assert(splash:go(url))
  assert(splash:wait(0.5))
  return {
    html = splash:html(),
    png = splash:png(),
    har = splash:har(),
  }
end

