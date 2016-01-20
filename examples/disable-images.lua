 function main(splash)
     splash.images_enabled = false
     assert(splash:go("http://flickr.com"))
     return {png=splash:png()}
 end
