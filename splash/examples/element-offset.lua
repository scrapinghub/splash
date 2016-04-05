function main(splash)
  local url = splash.args.url
  assert(splash:go(url))
  assert(splash:wait(0.5))
	  
  local element = splash:select('.article2 h1')

  return element:offset()
end
