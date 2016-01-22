function main(splash)
    splash.images_enabled = false
    assert(splash:go(splash.args.url))
    return {png=splash:png()}
end
