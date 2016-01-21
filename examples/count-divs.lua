function main(splash)
  local get_div_count = splash:jsfunc([[
    function () {
      var body = document.body;
      var divs = body.getElementsByTagName('div');
      return divs.length;
    }
  ]])

  local url = splash.args.url
  splash:go(url)
  return string.format("There are %s DIVs in %s",
      get_div_count(), url)
end
