-- Hey, this is a Splash rendering script.
-- It is written in Lua. Hope you like it.

function main(splash)

  local url = splash.args.url

  local ok, msg = splash:go(url) -- this is async!
  if not ok then
    return {status="error", msg=msg}
  end

  splash:wait(0.5)
  splash:stop()

  local prefixed_title = splash:jsfunc([[
    function(prefix){
      return prefix + " " + document.title;
    }
  ]])

  return {
    greeting = prefixed_title("Hello, "),
    html = splash:html(),
    png = splash:png{width=640},
    har = splash:har(),
  }
end
