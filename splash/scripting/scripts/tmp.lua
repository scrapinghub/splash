function main(splash)
    local ok, msg = coroutine.yield(splash:go("http://scrapinghub.com"))
    if not ok then
        return {status="error", message=msg}
    end
    coroutine.yield(splash:wait(0.1))
    return splash:png{width=300}
end


