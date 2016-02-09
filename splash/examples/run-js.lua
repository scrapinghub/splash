function main(splash)
  assert(splash:go("https://news.ycombinator.com/"))
  splash:runjs([[
    document.querySelector('table')
            .style.backgroundColor = "#fff";
  ]])
  return {png=splash:png()}
end
