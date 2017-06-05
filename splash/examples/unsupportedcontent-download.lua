function main(splash)
  splash.unsupported_content = 'download'
  splash.download_directory="/tmp"
  assert(splash:go("http://orimi.com/pdf-test.pdf"))
  return {
      png=splash:png(),
      download = splash:download(),
      download_filename = splash:download_filename(),
  }
end
