function main(splash, args)
  splash.set_viewport_size(800, 600)
  splash.set_user_agent('Splash bot')
  local example_urls = {"www.google.com", "www.bbc.co.uk", "scrapinghub.com"}
  local urls = args.urls or example_urls
  local results = {}
  for _, url in ipairs(urls) do
    local ok, reason = splash:go("http://" .. url)
    if ok then
      splash:wait(0.2)
      results[url] = splash:png()
    end
  end
  return results
end
