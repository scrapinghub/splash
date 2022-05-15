#!/usr/bin/env python

"""
Site downloader script for Splash benchmark suite.
"""

from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
import errno
import json
import os
import re
import subprocess
import logging
from urlparse import urlsplit

from lxml import html

import w3lib.html
from splash.benchmark.file_server import FileServerSubprocess
from splash.tests.stress import lua_runonce

SCRIPT_HTML = """
function main(splash)
splash:set_images_enabled(false)
splash:go(splash.args.url)
splash:wait(0.5)
return {url=splash:url(), html=splash:html()}
end
"""

#: This UA is used by httrack to mimic Splash requests when downloading sites.
USERAGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/534.34 (KHTML, like Gecko) Qt/4.8.1 Safari/534.34"

PORT = 8806

parser = ArgumentParser(description=__doc__,
                        formatter_class=ArgumentDefaultsHelpFormatter)
parser.add_argument('--sites-dir', default='sites',
                    help='Directory for downloaded sites')


def preprocess_main_page(sites_dir, url):
    """
    This function does several things:
    - strip javascript so that downloaded pages look exactly the same
    - add baseurl to resolve relative links properly (if it is missing)
    - add meta charset description (if it is missing)
    """
    out = json.loads(lua_runonce(SCRIPT_HTML, url=url,
                                 splash_args=['--disable-lua-sandbox',
                                              '--disable-xvfb',
                                              '--max-timeout=600'],
                                 timeout=600.,))
    final_url = urlsplit(out['url'])._replace(query='', fragment='').geturl()
    # Ensure there are no scripts to be executed.
    out['html'] = w3lib.html.remove_tags_with_content(out['html'], ('script',))
    root = html.fromstring(out['html'], parser=html.HTMLParser(),
                           base_url=final_url)
    try:
        head = root.xpath('./head')[0]
    except IndexError:
        head = html.Element('head')
        root.insert(0, head)
    if not head.xpath('./base/@href'):
        head.insert(0, html.Element('base', {'href': final_url}))
    if not head.xpath('./meta/@charset'):
        head.insert(0, html.Element('meta', {'charset': 'utf-8'}))
    out['html'] = html.tostring(root, encoding='utf-8',
                                doctype='<!DOCTYPE html>')
    filename = re.sub(r'[^\w]+', '_', url) + '.html'
    with open(os.path.join(sites_dir, filename), 'w') as f:
        f.write(out['html'])
    return filename


def download_sites(sites_dir, sites):
    local_files = [preprocess_main_page(sites_dir, s) for s in sites]

    local_urls = [
        'http://localhost:%(port)d/%(filename)s' % {
            'port': PORT, 'filename': filename
        }
        for filename in local_files
    ]
    args = ['--continue',
            '--near',           # Fetch referred non-html files.
            '-%P',              # Try parsing links in non-href/src sections
            '-F', USERAGENT,    # Emulate splash UA
            '--depth=1']
    subprocess.check_call(['httrack'] + args + local_urls, cwd=sites_dir)


def main():
    args = parser.parse_args()
    (logging.getLogger('requests.packages.urllib3.connectionpool')
     .setLevel(logging.WARNING))
    logging.basicConfig(level=logging.DEBUG)
    logging.info("Starting site download suite")
    try:
        os.makedirs(args.sites_dir)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise
        elif not os.path.isdir(args.sites_dir):
            raise RuntimeError("Not a directory: %s" % args.sites_dir)
    with FileServerSubprocess(port=PORT, path=args.sites_dir):
        download_sites(args.sites_dir, [
            'http://www.wikipedia.org',
            'http://www.google.com',
            'http://www.reddit.com',
            "http://w3.org",
            "http://w3.org/TR/2010/REC-xhtml-basic-20101123/",
            # "http://blog.pinterest.com",
            # "http://imgur.com",
        ])


if __name__ == '__main__':
    main()
