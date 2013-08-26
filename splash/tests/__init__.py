from splash.tests.utils import TestServers

ts = TestServers()

def setup():
    ts.__enter__()

def teardown():
    #leaks = requests.get("http://localhost:8050/debug").json()['leaks']
    #assert not leaks, "Leaks detected:\n%s" % leaks
    ts.__exit__(None, None, None)
