function main(splash)
  splash.unsupported_content = 'drop'
  assert(splash:go("http://orimi.com/pdf-test.pdf"))
  return {png=splash:png()}
end
