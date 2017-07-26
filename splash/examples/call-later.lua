function main(splash, args)
  local snapshots = {}
  local timer = splash:call_later(function()
    snapshots["a"] = splash:html()
    splash:wait(1.0)
    snapshots["b"] = splash:html()
  end, 1.5)
  assert(splash:go(args.url))
  splash:wait(3.0)
  timer:reraise()

  return snapshots
end