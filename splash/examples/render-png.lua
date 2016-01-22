-- A simplistic implementation of render.png endpoint
function main(splash)
   assert(splash:go(splash.args.url))
   return splash:png{
      width=splash.args.width,
      height=splash.args.height
   }
end
