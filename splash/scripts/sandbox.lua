-------------------
----- Sandbox -----
-------------------

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
  -- Disabled because:
  -- 1. coroutines are used internally - users shouldn't yield to Splash themselves;
  -- 2. debug hooks are per-coroutine in 'standard' Lua (not LuaJIT) - this requires a workaround.

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
    find = string.find,
    format = string.format,
--    gmatch = string.gmatch,     -- can be CPU intensive
--    gsub = string.gsub,         -- can be CPU intensive; can result in arbitrary native code execution (in 5.1)?
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
--    sort = table.sort,          -- can result in arbitrary native code execution (in 5.1)?
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

-------------------------------------------------------------
--
-- Fix metatables.
--

-- 1. TODO: change string metatable to the sandboxed version
--    (it is now just disabled)
debug.setmetatable('', nil)

-- 2. Make sure there are no other metatables:
debug.setmetatable(1, nil)
debug.setmetatable(function() end, nil)
debug.setmetatable(true, nil)


-------------------------------------------------------------
--
-- Basic memory and CPU limits.
-- Based on code by Roberto Ierusalimschy.
-- http://lua-users.org/lists/lua-l/2013-12/msg00406.html
--

-- maximum memory (in KB) that can be used by Lua script
local memlimit = 10000

-- maximum "steps" that can be performed; each step is 1000 instructions
-- XXX: the slowdown only becomes percievable at ~100m instructions
-- (100k steps).
local steplimit = 1000 -- allow 1m instructions (1k steps)

do
  -- track memory use
  local mt = {__gc = function (u)
    if collectgarbage("count") > memlimit then
      error("script uses too much memory")
    else
      setmetatable({}, getmetatable(u))
    end
  end}
  setmetatable({}, mt)
end

local count = 0
local function step ()
  count = count + 1
  if count > steplimit then
    error("script uses too much CPU")
  end
end

-- enable sandbox hooks
local enable_debug_hooks = function()
  debug.sethook(step, 'c', 1000)
end


-- debug hooks are per-coroutine; use this function
-- as a replacement for `coroutine.create`
function create_sandboxed_coroutine(f, ...)
  return coroutine.create(function(...)
    enable_debug_hooks()
    return f(...)
  end, ...)
end


-------------------------------------------------------------
--
-- Lua 5.2 sandbox
--
function run(untrusted_code)
  enable_debug_hooks()
  local untrusted_function, message = load(untrusted_code, nil, 't', env)
  if not untrusted_function then return nil, message end
  return pcall(untrusted_function)
end
