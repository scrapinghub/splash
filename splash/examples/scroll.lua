function main(splash, args)
  splash:go(args.url)
  local scroll_to = splash:jsfunc("window.scrollTo")
  scroll_to(0, 300)
  return {png=splash:png()}
end