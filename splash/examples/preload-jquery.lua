function main(splash)
    assert(splash:autoload("https://code.jquery.com/jquery-2.1.3.min.js"))
    assert(splash:go(splash.args.url))
    local version = splash:evaljs("$.fn.jquery")
    return 'JQuery version: ' .. version
end
