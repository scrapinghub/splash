function main(splash)
  splash.unsupported_content = 'download'
  splash.download_directory="/tmp"
  assert(splash:go("http://orimi.com/pdf-test.pdf"))
  return {png=splash:png()}
end
