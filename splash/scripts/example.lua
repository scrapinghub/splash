-- Hey, this is a Splash rendering script.
-- It is written in Lua. Hope you like it.

function main(splash)

  local url = "http://google.com"

  local ok, msg = splash:go(url) -- this is async!
  if not ok then
    return {status="error", msg=msg}
  end

  splash:wait(0.5)
  splash:stop()

  local div_count = splash:runjs([[
    var body = document.body;
    var divs = body.getElementsByTagName('div');

    // value of the last expression is returned
    divs.length
  ]])

  return {
    div_count = div_count,
    html = splash:html(),
    png = splash:png{width=640},
    har = splash:har(),
  }
end
