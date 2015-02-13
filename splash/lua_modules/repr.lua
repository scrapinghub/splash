--
-- A wrapper for inspect.lua. It discards metatables and supports multiple
-- arguments.
--
local inspect = require("vendor/inspect")

local remove_all_metatables = function(item, path)
  if path[#path] ~= inspect.METATABLE then return item end
end

function repr(...)
  local args = table.pack(...)

  -- Don't touch single userdata results in order to support
  -- inline images in IPython notebook.
  if args.n == 1 and type(args[1]) == 'userdata' then
    return ...
  end

  -- run 'inspect' on all parts in case of multiple arguments
  for i=1,args.n do
    args[i] = inspect(args[i], {process = remove_all_metatables})
  end
  return table.concat(args, ', ')
end

return repr
