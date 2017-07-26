-- This in an example of how to use lower-level
-- Splash functions to get element screenshot.
--
-- In practice use splash:select("a"):png{pad=32}.


-- this function adds padding around region
function pad(r, pad)
  return {r[1]-pad, r[2]-pad, r[3]+pad, r[4]+pad}
end

function main(splash, args)
  -- this function returns element bounding box
  local get_bbox = splash:jsfunc([[
    function(css) {
      var el = document.querySelector(css);
      var r = el.getBoundingClientRect();
      return [r.left, r.top, r.right, r.bottom];
    }
  ]])

  -- main script
  assert(splash:go(splash.args.url))
  assert(splash:wait(0.5))

  -- don't crop image by a viewport
  splash:set_viewport_full()

  -- let's get a screenshot of a first <a>
  -- element on a page, with extra 32px around it
  local region = pad(get_bbox("a"), 32)
  return splash:png{region=region}
end