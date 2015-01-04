local Splash = require("splash")

function Splash:get_document_title()
  return self:runjs("document.title")
end
