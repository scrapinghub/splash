function main(splash)
  assert(splash:go{url="http://orimi.com/pdf-test.pdf"
      , unsupported_content="download"
      , download_directory="/home/mohamed/Downloads"})
  return {png=splash:png()}
end
