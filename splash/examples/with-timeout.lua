function main(splash, args)
  local ok, result = splash:with_timeout(function()
    -- try commenting out splash:wait(3)
    splash:wait(3)
    assert(splash:go(args.url))
  end, 2)

  if not ok then
    if result == "timeout_over" then
      return "Cannot navigate to the url within 2 seconds"
    else
      return result
    end
  end
  return "Navigated to the url within 2 seconds"
end