treat = require("treat")

-- Given an url, this function returns a table
-- with the page screenshoot, it's HTML contents
-- and it's title.
function page_info(splash, url)
    local ok, msg = splash:go(url)
    if not ok then
        return {ok=false, reason=msg}
    end
    local res = {
        html=splash:html(),
        title=splash:evaljs('document.title'),
        image=splash:png(),
        ok=true,
    }
    return res
end

-- visit first 3 pages of hacker news
local base = "https://news.ycombinator.com/news?p="
function main(splash)
    local result = treat.as_array({})
    for i=1,3 do
        local url =  base .. i
        result[i] = page_info(splash, url)
    end
    return result
end
