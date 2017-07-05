-- A simplistic implementation of render.png
-- endpoint.
function main(splash, args)
  assert(splash:go(args.url))

  return splash:png{
    width=args.width,
    height=args.height
  }
end