function main(splash)
    splash:autoload([[
        function get_document_title(){
           return document.title;
        }
    ]])
    assert(splash:go(splash.args.url))
    return splash:evaljs("get_document_title()")
end
