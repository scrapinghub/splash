function main(splash)
    local ok, msg = coroutine.yield(splash:go("http://google.com"))
    if not ok then
        return {status="error", message=msg}
    end
    coroutine.yield(splash:wait(0.05))

    return {
        html = splash:html(),
        png = splash:png{base64=true},
        har = splash:har(),
    }
end
