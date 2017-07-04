-- A simplistic implementation of render.png
-- endpoint.
assert(splash:go(args.url))

return splash:png{
  width=args.width,
  height=args.height
}
