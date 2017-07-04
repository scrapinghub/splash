assert(splash:go(args.url))
assert(splash:wait(0.5))
return splash:har()
