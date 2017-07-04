function main(splash, args)
    splash:on_response_headers(function(response)
        local content_type = response.headers["Content-Type"]
        if content_type == "text/css" then
            response.abort()
        end
    end)
    assert(splash:go(args.url))
    return splash:png()
end
