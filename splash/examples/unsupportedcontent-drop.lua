function main(splash)
  assert(splash:go{url="http://orimi.com/pdf-test.pdf"
      , unsupported_content="drop"})
  return {png=splash:png()}
end
