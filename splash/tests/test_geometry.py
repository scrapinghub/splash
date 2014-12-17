from .test_runjs import BaseJsTest


class RunGeometryTest(BaseJsTest):
    _clientwidth_js_code = '''
        (function () {
            return document.body.clientWidth;
        })();
    '''

    def width_test(self, dimension, width):
        params = {'viewport': 'full', 'wait': '10', 'geometry': dimension}
        ret = self._runjs_request(self._clientwidth_js_code, params=params).json()
        js_width = int(ret['script'])
        assert width == js_width

    def test_small(self):
        return self.width_test('480x800', 480)

    def test_tablet(self):
        return self.width_test('768x1200', 768)

    def test_desktop(self):
        return self.width_test('1024x768', 1024)

    def test_large_desktop(self):
        return self.width_test('1280x1024', 1280)
