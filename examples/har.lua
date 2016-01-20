function main(splash)
  local url = splash.args.url
  assert(splash:go(url))
  assert(splash:wait(0.5))
  return splash:har()
end
