--
-- A sandbox
--
env = {
  --
  -- 6.1 Basic Functions
  -- http://www.lua.org/manual/5.2/manual.html#6.1
  assert = assert,
  error = error,
  ipairs = ipairs,
  next = next,
  pairs = pairs,
  pcall = pcall,
  print = print,        -- should we disable it?
  select = select,
  tonumber = tonumber,
  tostring = tostring,  -- Mike Pall says it is unsafe; why? See http://lua-users.org/lists/lua-l/2011-02/msg01595.html
  type = type,
  xpcall = xpcall,

  --
  -- 6.2 Coroutine Manipulation
  -- http://www.lua.org/manual/5.2/manual.html#6.2
  --
  -- Disabled: they are used internally.

  --
  -- 6.3 Modules
  -- http://www.lua.org/manual/5.2/manual.html#6.3
  --
  -- Disabled: this needs more research.

  --
  -- 6.4 String Manipulation
  -- http://www.lua.org/manual/5.2/manual.html#6.4
  string = {
    byte = string.byte,
    char = string.char,
--    find = string.find,         -- can be CPU intensive
    format = string.format,
--    gmatch = string.gmatch,     -- can be CPU intensive
--    gsub = string.gsub,         -- can be CPU intensive
    len = string.len,
    lower = string.lower,
--    match = string.match,       -- can be CPU intensive
--    rep = string.rep,           -- can eat memory
    reverse = string.reverse,
    sub = string.sub,
    upper = string.upper,
  },

  --
  -- 6.5 Table Manipulation
  -- http://www.lua.org/manual/5.2/manual.html#6.5
  table = {
    concat = table.concat,
    insert = table.insert,
    pack = table.pack,
    remove = table.remove,
    sort = table.sort,
    unpack = table.unpack,
  },

  --
  -- 6.6 Mathematical Functions
  -- http://www.lua.org/manual/5.2/manual.html#6.6
  math = {
    abs = math.abs,
    acos = math.acos,
    asin = math.asin,
    atan = math.atan,
    atan2 = math.atan2,
    ceil = math.ceil,
    cos = math.cos,
    cosh = math.cosh,
    deg = math.deg,
    exp = math.exp,
    floor = math.floor,
    fmod = math.fmod,
    frexp = math.frexp,
    huge = math.huge,
    ldexp = math.ldexp,
    log = math.log,
    max = math.max,
    min = math.min,
    modf = math.modf,
    pi = math.pi,
    pow = math.pow,
    rad = math.rad,
    random = math.random,
    randomseed = math.randomseed,
    sin = math.sin,
    sinh = math.sinh,
    sqrt = math.sqrt,
    tan = math.tan,
    tanh = math.tanh,
  },

  --
  -- 6.7 Bitwise Operations
  -- http://www.lua.org/manual/5.2/manual.html#6.7
  --
  -- Disabled: don't care.

  --
  -- 6.8 Input and Output Facilities
  -- http://www.lua.org/manual/5.2/manual.html#6.8
  --
  -- Disabled.

  --
  -- 6.9 Operating System Facilities
  -- http://www.lua.org/manual/5.2/manual.html#6.9
  os = {
    clock = os.clock,
--    date = os.date,        -- from wiki: "This can crash on some platforms (undocumented). For example, os.date'%v'. It is reported that this will be fixed in 5.2 or 5.1.3."
    difftime = os.difftime,
    time = os.time,
  },

  --
  -- 6.10 The Debug Library
  -- http://www.lua.org/manual/5.2/manual.html#6.10
  --
  -- Disabled.
}

-- Lua 5.2 sandbox
function run(untrusted_code)
  local untrusted_function, message = load(untrusted_code, nil, 't', env)
  if not untrusted_function then return nil, message end
  return pcall(untrusted_function)
end
