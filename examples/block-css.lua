function main(splash)
    splash:on_response_headers(function(response)
        local content_type = response.headers["Content-Type"]
        if content_type == "text/css" then
            response.abort()
        end
    end)
    assert(splash:go(splash.args.url))
    return splash:png()
end
