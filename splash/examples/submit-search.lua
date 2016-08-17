function find_search_input(inputs)
  if #inputs == 1 then
    return inputs[1]
  else
    for _, input in ipairs(inputs) do
      if input.node.attributes.type == "search" then
        return input
      end
    end
  end
end

function find_input(forms)
  local potential = {}

  for _, form in ipairs(forms) do
    local inputs = form.node:querySelectorAll('input:not([type="hidden"])')
    if #inputs ~= 0 then
      local input = find_search_input(inputs)
      if input then
        return form, input
      end

      potential[#potential + 1] = {input=inputs[1], form=form}
    end
  end

  return potential[1].form, potential[1].input
end

function main(splash)
  splash.images_enabled = false
  assert(splash:go(splash.args.url))
  assert(splash:wait(1))

  local forms = splash:select_all('form')

  if #forms == 0 then
    error('no search form is found')
  end

  local form, input = find_input(forms)

  if not input then
    error('no search form is found')
  end

  assert(input:send_keys('splash'))
  assert(splash:wait(0))

  assert(form:submit())
  assert(splash:wait(1))

  return splash:png()
end