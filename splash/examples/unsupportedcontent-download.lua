function main(splash)
  splash.unsupported_content = 'download'
  splash.download_directory="/tmp"
  assert(splash:go("http://orimi.com/pdf-test.pdf"))
  assert(splash:wait(0.5))
  return {
      png = splash:png(),
      html = splash:html(),
      har = splash:har(),
      download = splash:download(),
      download_filename = splash:download_filename(),
  }
end
