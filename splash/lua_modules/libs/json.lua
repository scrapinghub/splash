local json = {}

function json.encode(data)
  return __extras:json_encode(data)
end


function json.decode(data)
  if type(data) ~= 'string' then
    error("json.decode argument must be a string")
  end
  
  return __extras:json_decode(data)
end

return json