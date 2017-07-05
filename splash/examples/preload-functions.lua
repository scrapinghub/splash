function main(splash, args)
  splash:autoload([[
    function get_document_title(){
      return document.title;
    }
  ]])
  assert(splash:go(args.url))

  return splash:evaljs("get_document_title()")
end