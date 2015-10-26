local base64 = {}

function base64.encode(data)
  if type(data) ~= 'string' and type(data) ~= 'userdata' then
    error("base64.encode argument must be a string", 2)
  end
  
  return __extras:base64_encode(data)
end


function base64.decode(data)
  if type(data) ~= 'string' then
    error("base64.decode argument must be a string", 2)
  end
  
  return __extras:base64_decode(data)
end

return base64