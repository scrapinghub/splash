-------------------
----- sandbox -----
-------------------
local sandbox = {}

sandbox.allowed_require_names = {}

-- 6.4 String Manipulation
-- http://www.lua.org/manual/5.2/manual.html#6.4
local _string = {
  byte = string.byte,
  char = string.char,
  find = string.find,
  format = string.format,
--  gmatch = string.gmatch,     -- can be CPU intensive
--  gsub = string.gsub,         -- can be CPU intensive; can result in arbitrary native code execution (in 5.1)?
  len = string.len,
  lower = string.lower,
--  match = string.match,       -- can be CPU intensive
--  rep = string.rep,           -- can eat memory
  reverse = string.reverse,
  sub = string.sub,
  upper = string.upper,
}


sandbox.env = {
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
  require = function(name)
    if sandbox.allowed_require_names[name] then
      local ok, res = pcall(function() return require(name) end)
      if ok then
        return res
      end
    end
    error("module '" .. name .. "' not found", 2)
  end,

  --
  -- 6.4 String Manipulation
  -- http://www.lua.org/manual/5.2/manual.html#6.4
  string = _string,

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
  -- Disabled: if anyone cares we may add them.

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
-- Fix metatables. Some of the functions are available
-- via metatables of primitive types; disable them all.
--
sandbox.fix_metatables = function()
  -- Fix string metatable: provide common functions
  -- from string module.
  local mt = {__index={}}
  for k, v in pairs(_string) do
    mt['__index'][k] = v
  end
  debug.setmetatable('', mt)

  -- 2. Make sure there are no other metatables:
  debug.setmetatable(1, nil)
  debug.setmetatable(function() end, nil)
  debug.setmetatable(true, nil)
end


-------------------------------------------------------------
--
-- Basic memory and CPU limits.
-- Based on code by Roberto Ierusalimschy.
-- http://lua-users.org/lists/lua-l/2013-12/msg00406.html
--

-- maximum memory (in KB) that can be used by Lua script
sandbox.mem_limit = 50000
sandbox.mem_limit_reached = false

function sandbox.enable_memory_limit()
  if sandbox._memory_tracking_enabled then
    return
  end
  local mt = {__gc = function (u)
    if sandbox.mem_limit_reached then
      error("script uses too much memory")
    end
    if collectgarbage("count") > sandbox.mem_limit then
      sandbox.mem_limit_reached = true
      error("script uses too much memory")
    else
      -- create a new object for the next GC cycle
      setmetatable({}, getmetatable(u))
    end
  end }
  -- create an empty object which will be collected at next GC cycle
  setmetatable({}, mt)
  sandbox._memory_tracking_enabled = true
end


-- Maximum number of instructions that can be executed.
-- XXX: the slowdown only becomes percievable at ~5m instructions.
sandbox.instruction_limit = 1e6
sandbox.instruction_count = 0

function sandbox.enable_per_instruction_limits()
  local function _debug_step(event, line)
    sandbox.instruction_count = sandbox.instruction_count + 1
    if sandbox.instruction_count > sandbox.instruction_limit then
      error("script uses too much CPU", 2)
    end
    if sandbox.mem_limit_reached then
      error("script uses too much memory")
    end
  end
  debug.sethook(_debug_step, '', 1)
end


-- In Lua (but not in LuaJIT) debug hooks are per-coroutine.
-- Use this function as a replacement for `coroutine.create` to ensure
-- instruction limit is enforced in coroutines.
function sandbox.create_coroutine(f, ...)
  return coroutine.create(function(...)
    sandbox.enable_per_instruction_limits()
    return f(...)
  end, ...)
end


-------------------------------------------------------------
--
-- Lua 5.2 sandbox.
--
-- Note that it changes the global state: after the first `sandbox.run`
-- call the runtime becomes restricted in CPU and memory, and
-- "string":methods() like "foo":upper() stop working.
--
function sandbox.run(untrusted_code)
  sandbox.fix_metatables()
  sandbox.enable_memory_limit()
  sandbox.enable_per_instruction_limits()
  local untrusted_function, message = load(untrusted_code, nil, 't', sandbox.env)
  if not untrusted_function then return nil, message end
  return pcall(untrusted_function)
end

return sandbox
