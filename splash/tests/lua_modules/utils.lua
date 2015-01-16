local utils = {}

function utils.get_document_title(splash)
  return splash:evaljs("document.title")
end

local secret = require("secret")
utils.hello = secret.hello

return utils
