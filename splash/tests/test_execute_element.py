# -*- coding: utf-8 -*-
from __future__ import absolute_import

import base64
from io import BytesIO
from PIL import Image
import pytest

lupa = pytest.importorskip("lupa")

from splash.exceptions import ScriptError
from .test_execute import BaseLuaRenderTest


class HTMLElementTest(BaseLuaRenderTest):
    def test_select(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:go(splash.args.url))
            assert(splash:wait(0.1))

            local p = splash:select('p')
            local form = splash:select('form#login')
            local username = splash:select('input[name="username"]')
            local password = splash:select('input[name="password"]')
            local title = splash:select('.title')

            return {
                p=p.node.nodeName:lower(),
                form=form.node.nodeName:lower(),
                username=username.node.nodeName:lower(),
                password=password.node.nodeName:lower(),
                title=title.node.nodeName:lower(),
            }
        end
        """, {"url": self.mockurl("various-elements")})

        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {
            "p": "p",
            "form": "form",
            "username": "input",
            "password": "input",
            "title": "h1"
        })

    def test_bad_selector(self):
        resp = self.request_lua("""
         function main(splash)
            assert(splash:go(splash.args.url))
            assert(splash:wait(0.1))

            local element = splash:select('!notaselector')

            return element:exists()
        end
        """, {"url": self.mockurl("various-elements")})

        self.assertStatusCode(resp, 400)
        err = self.assertScriptError(resp, ScriptError.SPLASH_LUA_ERROR)
        self.assertEqual(err["info"]["splash_method"], "select")

    def test_bad_selector_select_all(self):
        resp = self.request_lua("""
         function main(splash)
            assert(splash:go(splash.args.url))
            assert(splash:wait(0.1))

            local elements = splash:select_all('!notaselector')

            return elements:exists()
        end
        """, {"url": self.mockurl("various-elements")})

        self.assertStatusCode(resp, 400)
        err = self.assertScriptError(resp, ScriptError.SPLASH_LUA_ERROR)
        self.assertEqual(err["info"]["splash_method"], "select_all")

    def test_exists(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:go(splash.args.url))
            assert(splash:wait(0.1))

            local block = splash:select('#block')

            local existsBefore = block:exists()
            assert(splash:runjs('document.write("<body></body>")'))
            assert(splash:wait(0.1))
            local existsAfter = block:exists()

            return { before = existsBefore, after = existsAfter }
        end
        """, {"url": self.mockurl("various-elements")})

        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {"before": True, "after": False})

    def test_mouse_click(self):
        resp = self.request_lua("""
        local treat = require('treat')
        function main(splash)
            assert(splash:go(splash.args.url))
            assert(splash:wait(0.1))

            local body = splash:select('body')
            local clicked_points = {}

            body.node.onclick = function(event)
             table.insert(clicked_points, {x=event.clientX, y=event.clientY})
            end

            assert(body:mouse_click(0, 0))
            assert(body:mouse_click(5, 10))
            assert(body:mouse_click(20, 40))

            assert(splash:wait(0))

            return treat.as_array(clicked_points)
        end
        """, {"url": self.mockurl("various-elements")})

        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), [
            {'x': 0, 'y': 0}, {'x': 5, 'y': 10}, {'x': 20, 'y': 40}
        ])

    def test_mouse_click_bad_x_argument(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:go(splash.args.url))
            assert(splash:wait(0.1))

            local body = splash:select('body')

            assert(body:mouse_click('not a number', 0))
        end
        """, {"url": self.mockurl("various-elements")})

        err = self.assertScriptError(resp, ScriptError.SPLASH_LUA_ERROR,
                                     message='x coordinate must be a number')
        self.assertEqual(err['info']['splash_method'], 'mouse_click')

    def test_mouse_click_bad_y_argument(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:go(splash.args.url))
            assert(splash:wait(0.1))

            local body = splash:select('body')

            assert(body:mouse_click(12, 'not a number'))
        end
        """, {"url": self.mockurl("various-elements")})

        err = self.assertScriptError(resp, ScriptError.SPLASH_LUA_ERROR,
                                     message='y coordinate must be a number')
        self.assertEqual(err['info']['splash_method'], 'mouse_click')

    def test_mouse_click_non_existing_element(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:go(splash.args.url))
            assert(splash:wait(0.1))

            local body = splash:select('div')
            body.node:remove()

            assert(body:mouse_click())
        end
        """, {"url": self.mockurl("various-elements")})

        self.assertStatusCode(resp, 400)
        self.assertScriptError(resp, ScriptError.LUA_ERROR,
                               message="Element no longer exists in DOM")

    def test_mouse_hover(self):
        resp = self.request_lua("""
        local treat = require('treat')
        function main(splash)
            assert(splash:go(splash.args.url))
            assert(splash:wait(0.1))

            local body = splash:select('body')
            local hovered_points = {}

            body.node.onmousemove = function(event)
             table.insert(hovered_points, {x=event.clientX, y=event.clientY})
            end

            assert(body:mouse_hover(0, 0))
            assert(body:mouse_hover(5, 10))
            assert(body:mouse_hover(20, 40))

            assert(splash:wait(0))

            return treat.as_array(hovered_points)
        end
        """, {"url": self.mockurl("various-elements")})

        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), [
            {'x': 0, 'y': 0}, {'x': 5, 'y': 10}, {'x': 20, 'y': 40}
        ])

    def test_mouse_hover_bad_x_argument(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:go(splash.args.url))
            assert(splash:wait(0.1))

            local body = splash:select('body')

            assert(body:mouse_hover('not a number', 0))
        end
        """, {"url": self.mockurl("various-elements")})

        err = self.assertScriptError(resp, ScriptError.SPLASH_LUA_ERROR,
                                     message='x coordinate must be a number')
        self.assertEqual(err['info']['splash_method'], 'mouse_hover')

    def test_mouse_hover_bad_y_argument(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:go(splash.args.url))
            assert(splash:wait(0.1))

            local body = splash:select('body')

            assert(body:mouse_hover(12, 'not a number'))
        end
        """, {"url": self.mockurl("various-elements")})

        err = self.assertScriptError(resp, ScriptError.SPLASH_LUA_ERROR,
                                     message='y coordinate must be a number')
        self.assertEqual(err['info']['splash_method'], 'mouse_hover')

    def test_styles(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:go(splash.args.url))
            assert(splash:wait(0.1))

            local title = splash:select('.title')

            return title:styles()
        end
        """, {"url": self.mockurl("various-elements")})

        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json()["display"], "none")

    def test_bounds(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:go(splash.args.url))
            assert(splash:wait(0.1))

            local block = splash:select('#block')
            local nestedBlock = splash:select('#nestedBlock')

            local blockBounds = block:bounds()
            local nestedBlockBounds = nestedBlock:bounds()

            return {
                top = nestedBlockBounds.top - blockBounds.top,
                left = nestedBlockBounds.left - blockBounds.left
            }
        end
            """, {"url": self.mockurl("various-elements")})

        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {"top": 10, "left": 10})

    def test_visible(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:go(splash.args.url))
            assert(splash:wait(0.1))

            local title = splash:select('.title')

            local visibleBefore = title:visible()

            assert(splash:runjs('document.querySelector(".title").style.display = "block"'))
            assert(splash:wait(0))

            local visibleAfter = title:visible()

            return { before = visibleBefore, after = visibleAfter }
        end
            """, {"url": self.mockurl("various-elements")})

        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {"before": False, "after": True})

    def test_focused(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:go(splash.args.url))
            assert(splash:wait(0.1))

            local input = splash:select('input')
            assert(not input:focused())
            input:focus()
            assert(input:focused())
            return "ok"
        end
        """, {"url": self.mockurl("various-elements")})
        self.assertStatusCode(resp, 200)

    def test_text(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:go(splash.args.url))
            assert(splash:wait(0.1))

            local input = splash:select('input[name="username"]')
            local block = splash:select('#block')
            local h1 = splash:select('h1')

            local inputText = input:text()
            local blockText = block:text()
            local h1Text = h1:text()

            return { input = inputText, block = blockText, h1 = h1Text }
        end
        """, {"url": self.mockurl("various-elements")})

        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {"input": "admin", "block": "nested", "h1": "Title"})

    def test_info(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:go(splash.args.url))
            assert(splash:wait(0.1))

            local h1 = splash:select('h1')

            return h1:info()
        end
        """, {"url": self.mockurl("various-elements")})

        expected = {
            'tag': '<h1 id="title" class="title" style="display: none ">Title</h1>',
            'width': 0,
            'nodeName': 'h1',
            'text': 'Title',
            'attributes': {
                'id': 'title',
                'class': 'title',
                'style': 'display: none '
            },
            'html': 'Title',
            'height': 0,
            'y': 0,
            'visible': False,
            'x': 0
        }

        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), expected)

    def test_form_values(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:go(splash.args.url))
            assert(splash:wait(0.1))

            local form = splash:select('#login')
            return assert(form:form_values())
        end
        """, {"url": self.mockurl("various-elements")})

        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {
            "username": "admin",
            "password": "pass123"
        })

    def test_form_values_empty(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:go(splash.args.url))
            assert(splash:wait(0.1))

            local form = splash:select('#login')
            form.node.innerHTML = ''

            return assert(form:form_values())
        end
        """, {"url": self.mockurl("various-elements")})

        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {})

    def test_form_values_values_auto(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:go(splash.args.url))
            assert(splash:wait(0.1))
            return assert(splash:select('#form'):form_values())
        end
        """, {"url": self.mockurl("various-elements")})

        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {
            'choice': 'no',
            'check': True,
            'foo[]': ['coffee', 'milk', 'eggs'],
            'baz': 'foo',
            'selection': ['1', '3']
        })

    def test_form_values_values_list(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:go(splash.args.url))
            assert(splash:wait(0.1))
            return assert(splash:select('#form'):form_values('list'))
        end
        """, {"url": self.mockurl("various-elements")})

        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {
            'choice': ['no'],
            'check': ['checked'],
            'foo[]': ['coffee', 'milk', 'eggs'],
            'baz': ['foo'],
            'selection': ['1', '3']
        })

    def test_form_values_values_first(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:go(splash.args.url))
            assert(splash:wait(0.1))
            return assert(splash:select('#form'):form_values('first'))
        end
        """, {"url": self.mockurl("various-elements")})

        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {
            'choice': 'no',
            'check': True,
            'foo[]': 'coffee',
            'baz': 'foo',
            'selection': '1',
        })

    def test_form_values_bad_values(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:go(splash.args.url))
            assert(splash:wait(0.1))
            return assert(splash:select('#form'):form_values(1))
        end
        """, {"url": self.mockurl("various-elements")})

        err = self.assertScriptError(resp, ScriptError.SPLASH_LUA_ERROR,
                                     message="element:form_values values can only be 'auto', 'first' or 'list'")
        self.assertEqual(err['info']['splash_method'], 'form_values')

    def test_form_values_of_not_form(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:go(splash.args.url))
            assert(splash:wait(0.1))

            local input = splash:select('input')
            return assert(input:form_values())
        end
        """, {"url": self.mockurl("various-elements")})

        self.assertStatusCode(resp, 400)
        self.assertScriptError(resp, ScriptError.LUA_ERROR, message="DOMError")

    def test_field_value(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:go(splash.args.url))
            assert(splash:wait(0.1))

            local username = splash:select('input[name="username"]')
            local ok, value = assert(username:field_value())

            return value
        end
        """, {"url": self.mockurl("various-elements")})

        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.text, "admin")

    def test_field_value_empty_value(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:go(splash.args.url))
            assert(splash:wait(0.1))

            local remember = splash:select('input[name="remember"]')
            local ok, value = assert(remember:field_value())

            return {value=value}
        end
        """, {"url": self.mockurl("various-elements")})

        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {'value': False})

    def test_fill(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:go(splash.args.url))
            assert(splash:wait(0.1))

            local form = splash:select('#login')
            local values = { username="user1", password="mypass" }

            assert(form:fill(values))
            return assert(form:form_values())
        end
        """, {"url": self.mockurl("various-elements")})

        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {'username': 'user1', 'password': 'mypass'})

    def test_fill_complex(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:go(splash.args.url))
            assert(splash:wait(0.1))

            local form = splash:select('#form')
            local values = {
              ['foo[]'] = 'foo',
              baz = 'abc',
              choice = 'yes',
              check = false,
              selection = {'2', '3'}
            }

            assert(form:fill(values))
            return assert(form:form_values())
        end
        """, {"url": self.mockurl("various-elements")})

        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {
            'selection': ['2', '3'],
            'choice': 'yes',
            'baz': 'abc',
            # 'check': False, lua -> py conversation removes negative values
            'foo[]': ['foo', 'foo', 'foo']
        })

    def test_fill_multi(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:go(splash.args.url))
            assert(splash:wait(0.1))

            local form = splash:select('#form')
            local values = {
              ['foo[]'] = {'a', 'b', 'c'}
            }

            assert(form:fill(values))
            return assert(form:form_values())
        end
        """, {"url": self.mockurl("various-elements")})

        self.assertStatusCode(resp, 200)
        res = resp.json()
        self.assertEqual(res['foo[]'], ['a', 'b', 'c'])

    def test_fill_bad_values(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:go(splash.args.url))
            assert(splash:wait(0.1))

            local form = splash:select('#form')
            assert(form:fill(1123))
            return assert(form:form_values())
        end
        """, {"url": self.mockurl("various-elements")})

        err = self.assertScriptError(resp, ScriptError.SPLASH_LUA_ERROR,
                                     message='values is not a table')
        self.assertEqual(err['info']['splash_method'], 'fill')

    def test_send_keys(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:go(splash.args.url))
            assert(splash:wait(0.1))

            local username = splash:select('input[name="username"]')
            assert(username:send_keys('super <Space>'))
            assert(splash:wait(0))
            local ok, value = assert(username.field_value())

            return value
        end
        """, {"url": self.mockurl("various-elements")})

        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.text, "super admin")

    def test_send_text(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:go(splash.args.url))
            assert(splash:wait(0.1))

            local username = splash:select('input[name="username"]')
            assert(username:send_text('super '))
            assert(splash:wait(1))
            local ok, value = assert(username.field_value())

            return value
        end
        """, {"url": self.mockurl("various-elements")})

        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.text, "super admin")

    def test_send_text_keys_multiple(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:go(splash.args.url))
            assert(splash:wait(0.1))

            local username = splash:select('input[name="username"]')
            username:mouse_click()   -- fixme
            splash:wait(0)

            assert(username:send_text('super '))
            assert(username:focused())
            assert(username:send_text('duper'))
            assert(username:send_keys('<Left> <Left> <Delete>'))
            assert(splash:wait(1))
            local ok, value = assert(username.field_value())

            return value
        end
        """, {"url": self.mockurl("various-elements")})

        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.text, "super dupradmin")

    def test_png(self):
        resp = self.request_lua("""
        function main(splash)
            local args = splash.args

            splash:set_viewport_size(1024, 768)
            splash:go(args.url)
            splash:wait(0.1)

            local full = splash:png()
            local left = splash:select('#left')
            local left_shot = left:png()
            local bounds = left:bounds()

            return {full = full, shot = left_shot, bounds = bounds}
        end
        """, {"url": self.mockurl("red-green")})

        region_size = 1024 / 2, 768

        self.assertStatusCode(resp, 200)
        out = resp.json()
        full_img = Image.open(BytesIO(base64.b64decode(out["full"])))

        element_img = Image.open(BytesIO(base64.b64decode(out["shot"])))
        bounds = out["bounds"]
        region = (bounds["left"], bounds["top"], bounds["right"], bounds["bottom"])

        self.assertEqual(element_img.size, region_size)
        self.assertImagesEqual(full_img.crop(region), element_img)

    def test_png_invisible_element(self):
        resp = self.request_lua("""
        function main(splash)
            local args = splash.args

            splash:set_viewport_size(1024, 768)
            splash:go(args.url)
            splash:wait(0.1)

            local left = splash:select('#left')
            assert(splash:runjs('document.querySelector("#left").style.visibility = "hidden"'))
            assert(splash:wait(0))
            local left_shot = left:png()

            return left_shot
        end
        """, {"url": self.mockurl("red-green")})

        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.text, 'None')

    def test_png_non_existing_element(self):
        resp = self.request_lua("""
        function main(splash)
            local args = splash.args

            splash:set_viewport_size(1024, 768)
            splash:go(args.url)
            splash:wait(0.1)

            local left = splash:select('#left')
            assert(splash:runjs('document.write("")'))
            assert(splash:wait(0))
            local left_shot = left:png()

            return left_shot
        end
        """, {"url": self.mockurl("red-green")})

        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.text, 'None')

    def test_png_with_pad(self):
        resp = self.request_lua("""
        function main(splash)
            local args = splash.args

            splash:set_viewport_size(1024, 768)
            splash:go(args.url)
            splash:wait(0.1)

            local full = splash:png()
            local left = splash:select('#left')
            local left_shot = left:png{pad=10}
            local bounds = left:bounds()

            return {full = full, shot = left_shot, bounds = bounds}
        end
        """, {"url": self.mockurl("red-green")})

        pad = 10
        region_size = 1024 // 2 + pad * 2, 768 + pad * 2

        self.assertStatusCode(resp, 200)
        out = resp.json()
        full_img = Image.open(BytesIO(base64.b64decode(out["full"])))

        element_img = Image.open(BytesIO(base64.b64decode(out["shot"])))
        bounds = out["bounds"]
        region = (bounds["left"] - pad, bounds["top"] - pad, bounds["right"] + pad, bounds["bottom"] + pad)

        self.assertEqual(element_img.size, region_size)
        self.assertImagesEqual(full_img.crop(region), element_img)

    def test_png_with_complex_pad(self):
        resp = self.request_lua("""
        function main(splash)
            local args = splash.args

            splash:set_viewport_size(1024, 768)
            splash:go(args.url)
            splash:wait(0.1)

            local full = splash:png()
            local left = splash:select('#left')
            local left_shot = left:png{pad={-5, 10, -20, -30}}
            local bounds = left:bounds()

            return {full = full, shot = left_shot, bounds = bounds}
        end
        """, {"url": self.mockurl("red-green")})

        pad = (-5, 10, -20, -30)
        region_size = 1024 // 2 + (pad[0] + pad[2]), 768 + (pad[1] + pad[3])

        self.assertStatusCode(resp, 200)
        out = resp.json()
        full_img = Image.open(BytesIO(base64.b64decode(out["full"])))

        element_img = Image.open(BytesIO(base64.b64decode(out["shot"])))
        bounds = out["bounds"]
        region = (bounds["left"] - pad[0], bounds["top"] - pad[1], bounds["right"] + pad[2], bounds["bottom"] + pad[3])

        self.assertEqual(element_img.size, region_size)
        self.assertImagesEqual(full_img.crop(region), element_img)

    def test_png_with_width(self):
        resp = self.request_lua("""
        function main(splash)
            local args = splash.args

            splash:set_viewport_size(1024, 768)
            splash:go(args.url)
            splash:wait(0.1)

            local full = splash:png()
            local left = splash:select('#left')
            local left_shot = left:png{width=100}
            local bounds = left:bounds()

            return {full = full, shot = left_shot, bounds = bounds}
        end
        """, {"url": self.mockurl("red-green")})

        region_size = 100, 150

        self.assertStatusCode(resp, 200)
        out = resp.json()
        full_img = Image.open(BytesIO(base64.b64decode(out["full"])))

        element_img = Image.open(BytesIO(base64.b64decode(out["shot"])))
        bounds = out["bounds"]
        region = (bounds["left"], bounds["top"], bounds["right"], bounds["bottom"])

        self.assertEqual(element_img.size, region_size)
        self.assertImagesEqual(full_img.crop(region), element_img)

    def test_jpeg(self):
        resp = self.request_lua("""
        function main(splash)
            local args = splash.args

            splash:set_viewport_size(1024, 768)
            splash:go(args.url)
            splash:wait(0.1)

            local left = splash:select('#left')
            local left_shot = left:jpeg()
            return left_shot
        end
        """, {"url": self.mockurl("red-green")})

        self.assertStatusCode(resp, 200)
        self.assertJpeg(resp, 1024 // 2, 768)

    def test_jpeg_non_existing_element(self):
        resp = self.request_lua("""
        function main(splash)
            local args = splash.args

            splash:set_viewport_size(1024, 768)
            splash:go(args.url)
            splash:wait(0.1)

            local left = splash:select('#left')
            assert(splash:runjs('document.write("")'))
            assert(splash:wait(0))
            local left_shot = left:jpeg()

            return left_shot
        end
        """, {"url": self.mockurl("red-green")})

        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.text, 'None')

    def test_jpeg_with_pad(self):
        resp = self.request_lua("""
        function main(splash)
            local args = splash.args

            splash:set_viewport_size(1024, 768)
            splash:go(args.url)
            splash:wait(0.1)

            local full = splash:jpeg()
            local left = splash:select('#left')
            local left_shot = left:jpeg{pad=-10}
            local bounds = left:bounds()

            return {full = full, shot = left_shot, bounds = bounds}
        end
        """, {"url": self.mockurl("red-green")})

        pad = -10
        region_size = 1024 // 2 + pad * 2, 768 + pad * 2

        self.assertStatusCode(resp, 200)
        out = resp.json()
        full_img = Image.open(BytesIO(base64.b64decode(out["full"])))

        element_img = Image.open(BytesIO(base64.b64decode(out["shot"])))
        bounds = out["bounds"]
        region = (bounds["left"] - pad, bounds["top"] - pad, bounds["right"] + pad, bounds["bottom"] + pad)

        self.assertEqual(element_img.size, region_size)
        self.assertImagesEqual(full_img.crop(region), element_img)

    def test_jpeg_with_complex_pad(self):
        resp = self.request_lua("""
        function main(splash)
            local args = splash.args

            splash:set_viewport_size(1024, 768)
            splash:go(args.url)
            splash:wait(0.1)

            local full = splash:jpeg()
            local left = splash:select('#left')
            local left_shot = left:jpeg{pad={-5, -10, -20, -30}}
            local bounds = left:bounds()

            return {full = full, shot = left_shot, bounds = bounds}
        end
        """, {"url": self.mockurl("red-green")})

        pad = (-5, -10, -20, -30)
        region_size = 1024 // 2 + (pad[0] + pad[2]), 768 + (pad[1] + pad[3])

        self.assertStatusCode(resp, 200)
        out = resp.json()
        full_img = Image.open(BytesIO(base64.b64decode(out["full"])))

        element_img = Image.open(BytesIO(base64.b64decode(out["shot"])))
        bounds = out["bounds"]
        region = (bounds["left"] - pad[0], bounds["top"] - pad[1], bounds["right"] + pad[2], bounds["bottom"] + pad[3])

        self.assertEqual(element_img.size, region_size)
        self.assertImagesEqual(full_img.crop(region), element_img)

    def test_jpeg_with_width(self):
        resp = self.request_lua("""
        function main(splash)
            local args = splash.args

            splash:set_viewport_size(1024, 768)
            splash:go(args.url)
            splash:wait(0.1)

            local left = splash:select('#left')
            local left_shot = left:jpeg{width=100, quality=100}

            return left_shot
        end
        """, {"url": self.mockurl("red-green")})

        self.assertStatusCode(resp, 200)
        self.assertJpeg(resp, 100, 150)

    def test_event_handlers(self):
        resp = self.request_lua("""
        function main(splash)
            splash:go(splash.args.url)
            splash:wait(0.1)

            local x, y = 0, 0
            local prevented = nil
            local called = 0

            local button = splash:select('button')
            button.node.onclick = function(event)
                event:preventDefault()
                event:stopImmediatePropagation()
                event:stopPropagation()
                called = called + 1
                x = event.clientX
                y = event.clientY
                prevented = event.defaultPrevented
            end

            assert(button:mouse_click())
            assert(splash:wait(0))
            assert(button:mouse_click())
            assert(splash:wait(0))

            return {called=called, x=x, y=y, prevented=prevented}
        end
        """, {"url": self.mockurl("various-elements")})

        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {"called": 2, "x": 2, "y": 2, "prevented": True})

    def test_event_handlers_bad_event_name(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:go(splash.args.url))
            assert(splash:wait(0.1))

            local body = splash:select('body')
            body.on = function(event) end

            return true
        end
        """, {"url": self.mockurl("various-elements")})

        err = self.assertScriptError(resp, ScriptError.SPLASH_LUA_ERROR,
                                     message='event_name must be specified')
        self.assertEqual(err['info']['splash_method'], 'set_event_handler')

    def test_event_handlers_bad_handler(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:go(splash.args.url))
            assert(splash:wait(0.1))

            local body = splash:select('body')
            body.onclick = 123

            return true
        end
        """, {"url": self.mockurl("various-elements")})

        err = self.assertScriptError(resp, ScriptError.SPLASH_LUA_ERROR,
                                     message='handler is not a function')
        self.assertEqual(err['info']['splash_method'], 'set_event_handler')

    def test_event_handlers_error_in_handler(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:go(splash.args.url))
            assert(splash:wait(0.1))

            local body = splash:select('body')
            body.onclick = function()
                error('make some noise')
            end

            assert(body:mouse_click())
            assert(splash:wait(1))

            return true
        end
        """, {"url": self.mockurl("various-elements")})

        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.text, 'True')

    def test_unset_event_handlers(self):
        resp = self.request_lua("""
        function main(splash)
            splash:go(splash.args.url)
            splash:wait(0.1)

            local called = 0

            local button = splash:select('button')
            button.node.onclick = function(event)
                called = called + 1
            end

            assert(button:mouse_click())
            assert(splash:wait(0))
            assert(button:mouse_click())
            assert(splash:wait(0))

            button.node.onclick = nil

            assert(button:mouse_click())
            assert(splash:wait(0))

            return {called=called}
        end
        """, {"url": self.mockurl("various-elements")})

        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {"called": 2})

    def test_element_properties_getters(self):
        resp = self.request_lua("""
        function main(splash)
            splash:go(splash.args.url)
            splash:wait(0.1)


            local properties = splash.args.properties;
            local element = splash:select('#clickMe')

            local properties = {
                'attributes',
                'className',
            }
            local lua_properties = {}

            for i,v in ipairs(properties) do
                lua_properties[v] = element.node[v]
            end

            return lua_properties
        end
          """, {"url": self.mockurl("various-elements")})

        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {
            'attributes': {
                'onclick': 'this.innerText = (+this.innerText) + 1',
                'id': 'clickMe',
                'class': 'test'
            },
            'className': 'test',
        })

    def test_element_properties_setters(self):
        resp = self.request_lua("""
        function main(splash)
            splash:go(splash.args.url)
            splash:wait(0.1)

            local properties = splash.args.properties;
            local element = splash:select('#clickMe')

            element.node.className = 'my-class'

            return splash:evaljs('document.querySelector("#clickMe").className')
        end
          """, {"url": self.mockurl("various-elements")})

        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.text, 'my-class')

    def test_element_properties_returns_element(self):
        resp = self.request_lua("""
        local treat = require('treat')
        function main(splash)
            splash:go(splash.args.url)
            splash:wait(0.1)

            local el = splash:select('button')
            local ids = {}

            while el do
                table.insert(ids, el.node.id)
                el = el.node.nextSibling
            end

            return treat.as_array(ids)
        end
          """, {"url": self.mockurl("various-elements")})

        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), ['showTitleBtn', 'title', 'login', 'form', 'editable',
                                       'multiline-inline', 'block', 'clickMe', 'hoverMe', 'parent'])

    def test_element_methods(self):
        resp = self.request_lua("""
        local treat = require('treat')

        function main(splash)
            splash:go(splash.args.url)
            splash:wait(0.1)

            local clickMe = splash:select('#clickMe')

            clickMe.node:click()
            clickMe.node:click()
            clickMe.node:click()

            assert(splash:wait(0))

            return clickMe.innerHTML
        end
          """, {"url": self.mockurl("various-elements")})

        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.text, '3')

    def test_element_style(self):
        resp = self.request_lua("""
        function main(splash)
            splash:go(splash.args.url)
            splash:wait(0.1)

            local title = splash:select('#title')
            local display = title.node.style.display;
            title.node.style.display = 'block';

            local styles = title:styles()

            return {old=display, new=styles.display}
        end
          """, {"url": self.mockurl("various-elements")})

        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {'old': "none", 'new': "block"})

    def test_select_empty(self):
        resp = self.request_lua("""
        local treat = require('treat')
        function main(splash)
            splash:go(splash.args.url)
            splash:wait(0.1)

            local el = splash:select('h5')

            if not el then
                return 'ok'
            else
                return 'bad'
            end
        end
          """, {"url": self.mockurl("various-elements")})

        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.text, 'ok')

    def test_select_all(self):
        resp = self.request_lua("""
        local treat = require('treat')
        function main(splash)
            splash:go(splash.args.url)
            splash:wait(0.1)

            local divs = splash:select_all('div')

            local ids = {}
            for i,el in ipairs(divs) do
                ids[i] = el.node.id
            end

            return treat.as_array(ids)
        end
          """, {"url": self.mockurl("various-elements")})

        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), ['editable', 'block', 'nestedBlock', 'clickMe', 'hoverMe', 'parent', 'child'])

    def test_select_all_empty(self):
        resp = self.request_lua("""
        local treat = require('treat')
        function main(splash)
            splash:go(splash.args.url)
            splash:wait(0.1)

            local el = splash:select_all('h5')

            local count = 0
                for _ in pairs(el) do count = count + 1 end
            return count
        end
          """, {"url": self.mockurl("various-elements")})

        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.text, '0')

    def test_select_returns_elements(self):
        resp = self.request_lua("""
        local treat = require('treat')
        function main(splash)
            splash:go(splash.args.url)
            splash:wait(0.1)

            local body = splash:select('body')
            local divs = body.node:querySelectorAll('div')

            local ids = {}
            for i,el in ipairs(divs) do
                ids[i] = el.node.id
            end

            return treat.as_array(ids)
        end
          """, {"url": self.mockurl("various-elements")})

        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), ['editable', 'block', 'nestedBlock', 'clickMe', 'hoverMe', 'parent', 'child'])

    def test_inner_id(self):
        resp = self.request_lua("""
        function main(splash)
          splash:go(splash.args.url)
          splash:wait(0.1)

          local body = splash:select('body')

          return body.inner_id
        end
        """, {"url": self.mockurl("various-elements")})

        self.assertStatusCode(resp, 200)
        self.assertTrue(len(resp.text) > 0)

    def test_event_listener(self):
        resp = self.request_lua("""
        function main(splash)
            splash:go(splash.args.url)
            splash:wait(0.1)

            local x, y = 0, 0
            local prevented = nil
            local called = 0

            local button = splash:select('button')

            local handler = function(event)
                event:preventDefault()
                event:stopImmediatePropagation()
                event:stopPropagation()
                called = called + 1
                x = event.clientX
                y = event.clientY
                prevented = event.defaultPrevented
            end

            button.node:addEventListener('click', handler)

            assert(button:mouse_click())
            assert(splash:wait(0))
            assert(button:mouse_click())
            assert(splash:wait(0))

            button.node:removeEventListener('click', handler)

            assert(button:mouse_click())
            assert(splash:wait(0))

            return {called=called, x=x, y=y, prevented=prevented}
        end
        """, {"url": self.mockurl("various-elements")})

        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {"called": 2, "x": 2, "y": 2, "prevented": True})

    def test_event_listener_options(self):
        resp = self.request_lua("""
        local treat = require('treat')
        function main(splash)
            splash:go(splash.args.url)
            splash:wait(0.1)

            local orders = {}

            local parent = splash:select('#parent')
            local child = splash:select('#child')

            local get_handler = function(i)
                return function()
                    orders[#orders + 1] = i
                end
            end

            child.node:addEventListener('click', get_handler(1), true) -- children capture
            child.node:addEventListener('click', get_handler(2), false) -- children bubble
            parent.node:addEventListener('click', get_handler(3), true) -- parent capture
            parent.node:addEventListener('click', get_handler(4), false) -- parent bubble

            assert(child:mouse_click())
            assert(splash:wait(0))

            return treat.as_array(orders)
        end
        """, {"url": self.mockurl("various-elements")})

        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), [3, 1, 2, 4])

    def test_event_listeners_bad_event_name(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:go(splash.args.url))
            assert(splash:wait(0.1))

            local body = splash:select('body')
            body.node:addEventListener('', function(event) end)

            return true
        end
        """, {"url": self.mockurl("various-elements")})

        err = self.assertScriptError(resp, ScriptError.SPLASH_LUA_ERROR,
                                     message='event_name must be specified')
        self.assertEqual(err['info']['splash_method'], 'addEventListener')

    def test_event_listeners_bad_options(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:go(splash.args.url))
            assert(splash:wait(0.1))

            local body = splash:select('body')
            body.node:addEventListener('click', function(event) end, 1)

            return true
        end
        """, {"url": self.mockurl("various-elements")})

        err = self.assertScriptError(resp, ScriptError.SPLASH_LUA_ERROR,
                                     message='options must be a boolean or a table')
        self.assertEqual(err['info']['splash_method'], 'addEventListener')

    def test_event_listeners_bad_handler(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:go(splash.args.url))
            assert(splash:wait(0.1))

            local body = splash:select('body')
            body.node:addEventListener('click', 123)

            return true
        end
        """, {"url": self.mockurl("various-elements")})

        err = self.assertScriptError(resp, ScriptError.SPLASH_LUA_ERROR,
                                     message='handler is not a function')
        self.assertEqual(err['info']['splash_method'], 'addEventListener')

    def test_remove_event_listeners_bad_event_name(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:go(splash.args.url))
            assert(splash:wait(0.1))

            local body = splash:select('body')
            body.node:addEventListener('click', function(event) end)
            body.node:removeEventListener('', function(event) end)

            return true
        end
        """, {"url": self.mockurl("various-elements")})

        err = self.assertScriptError(resp, ScriptError.SPLASH_LUA_ERROR,
                                     message='event_name must be specified')
        self.assertEqual(err['info']['splash_method'], 'removeEventListener')

    def test_remove_not_added_event_listeners(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:go(splash.args.url))
            assert(splash:wait(0.1))

            local body = splash:select('body')
            body.node:removeEventListener('click', function(event) end)

            return true
        end
        """, {"url": self.mockurl("various-elements")})

        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.text, 'True')

    def test_submit(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:go(splash.args.url))
            assert(splash:wait(0.1))

            local submitted = false

            local form = splash:select('form')

            assert(form:submit())
            assert(splash:wait(0.5))

            return splash:url()
        end
        """, {"url": self.mockurl("various-elements")})

        self.assertStatusCode(resp, 200)
        self.assertRegexpMatches(resp.text, '/submitted\?username=admin&password=pass123')

    def test_submit_not_form(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:go(splash.args.url))
            assert(splash:wait(0.1))

            local submitted = false

            local input = splash:select('input')

            assert(input:submit())
        end
        """, {"url": self.mockurl("various-elements")})

        self.assertScriptError(resp, ScriptError.LUA_ERROR,
                               "Node should be 'form'")

    def test_element_arg(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:go(splash.args.url))
            assert(splash:wait(0.1))

            local body = splash:select('body')
            local div = splash:evaljs('document.createElement("div")')

            div.node.id = 'mydiv';
            body.node:appendChild(div);

            return body.node.lastChild.node.id
        end
        """, {"url": self.mockurl("various-elements")})

        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.text, 'mydiv')

    def test_element_as_jsfunc_argument(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:go(splash.args.url))
            local tagname = splash:jsfunc("function(el) {return el.tagName}")
            local body = splash:select('body')
            return tagname(body)
        end
        """, {"url": self.mockurl("various-elements")})

        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.text, 'BODY')

    def test_elements_after_go(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:go(splash.args.url))
            assert(splash:wait(0.1))

            local body = splash:select('body')

            assert(splash:go(splash.args.url))
            assert(splash:wait(0.1))

            return body.id
        end
        """, {"url": self.mockurl("various-elements")})

        self.assertScriptError(resp, ScriptError.LUA_ERROR,
                               'TypeError: undefined is not an object')

    def test_elements_jsredirect(self):
        resp = self.request_lua("""
        function main(splash)
            assert(splash:go(splash.args.url))

            local body = splash:select('body')

            function get_text()
                return body.node.childNodes[1].node:text()
            end

            local text = get_text()

            assert(splash:wait(0.1))

            local ok = pcall(get_text)
            return {text=text, ok=ok}
        end
        """, {"url": self.mockurl("jsredirect")})

        self.assertStatusCode(resp, 200)
        self.assertEqual(resp.json(), {'text': 'Redirecting now..', 'ok': False})
