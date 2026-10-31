# Loads each minimal test page in www/ with native XSLT (A) and with native XSLT off and the extension
# installed (E), and prints the page's result text and errors. Set GECKODRIVER for Firefox.
# post.xml is XML with a PI for POST and 405 for GET; csp.html is served with a CSP without
# 'wasm-unsafe-eval'.
# Usage: run.py chrome|firefox <extension-dir>
import asyncio, functools, http.server, os, socket, sys, tempfile, threading, time
WWW = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'www')
class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
    def end_headers(self):
        if self.path.startswith('/csp.html'):
            self.send_header('Content-Security-Policy', "script-src 'self' 'unsafe-inline'")
        super().end_headers()
    def do_GET(self):
        if self.path.startswith('/post.xml'):
            self.send_response(405); self.end_headers(); return
        super().do_GET()
    def do_POST(self):
        self.rfile.read(int(self.headers.get('Content-Length', 0)))
        body = b'<?xml version="1.0"?>\n<?xml-stylesheet type="text/xsl" href="s.xsl"?>\n<root><item>posted</item></root>\n'
        self.send_response(200); self.send_header('Content-Type', 'text/xml'); self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(H, directory=WWW))
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = f'http://127.0.0.1:{srv.server_port}/'
PAGES = ['event.xml', 'font.xml', 'type-text-xml.xml', 'type-application-xml.xml', 'cp1251.xml', 'latin1.xml', 'blank-iframe.html', 'post-form.html', 'csp.html', 'csp-none.html', 'script-source.xml', 'quirks-nodoctype.xml', 'quirks-doctype.xml',
         'utf16.xml', 'xsl1251.xml', 'doc1251.xml', 'bad-utf8.xml', 'bad-sjis.xml', 'bad-xsl.xml',
         'pi-css-then-xsl.xml', 'pi-alternate-then-xsl.xml', 'pi-alternate-title-then-xsl.xml', 'pi-bogus-then-xsl.xml', 'pi-nohref-then-xsl.xml', 'pi-two-xsl.xml', 'pi-type-application-xml.xml', 'pi-type-application-xslt.xml', 'pi-type-atom.xml', 'pi-type-missing.xml', 'pi-type-params.xml', 'pi-type-rss.xml', 'pi-type-space.xml', 'pi-type-text-xml.xml', 'pi-type-text-xsl.xml', 'pi-type-upper.xml', 'pi-type-xhtml.xml', 'case.xml', 'reset-viewer.xml', 'reset-noviewer.xml', 'reset-margin.xml']
M = "(() => { const t = document.getElementById('t'); return (t ? t.textContent : !document.documentElement ? '(empty document)' : (document.documentElement.textContent || '').trim().slice(0, 80)) })()"
browser, ext = sys.argv[1], sys.argv[2]

async def chrome():
    from playwright.async_api import async_playwright
    exe = '/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary'
    async with async_playwright() as p:
        for mode in ('A', 'E'):
            s = socket.socket(); s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]; s.close()
            args = ['--enable-features=XSLT', '--disable-features=GenerateXSLTWarningBanner'] if mode == 'A' else ['--disable-features=XSLT', '--enable-unsafe-extension-debugging', f'--remote-debugging-port={port}']
            ctx = await p.chromium.launch_persistent_context(tempfile.mkdtemp(), executable_path=exe, headless=True, args=args, ignore_default_args=['--disable-extensions'])
            if mode == 'E':
                b = await p.chromium.connect_over_cdp(f'http://127.0.0.1:{port}')
                await (await b.new_browser_cdp_session()).send('Extensions.loadUnpacked', {'path': ext})
            page = ctx.pages[0]
            errs = []
            page.on('pageerror', lambda e: errs.append(e.message[:100]))
            page.on('console', lambda m: m.type == 'error' and errs.append('console: ' + m.text[:100]))
            for u in PAGES:
                errs.clear()
                await page.goto(BASE + u); await page.wait_for_timeout(2500)
                print(mode, u, '|', await page.evaluate(M), '|', errs[:3], flush=True)
            await ctx.close()

def firefox():
    from selenium import webdriver
    from selenium.webdriver.firefox.options import Options
    from selenium.webdriver.firefox.service import Service
    for mode in ('A', 'E'):
        o = Options(); o.binary_location = '/Applications/Firefox Nightly.app/Contents/MacOS/firefox'; o.add_argument('-headless')
        o.set_preference('dom.xslt.enabled', mode == 'A'); o.enable_bidi = True
        d = webdriver.Firefox(options=o, service=Service(os.environ.get('GECKODRIVER')))
        errs = []
        d.script.add_javascript_error_handler(lambda m: errs.append(str(m.text)[:100]))
        d.script.add_console_message_handler(lambda m: m.level == 'error' and errs.append('console: ' + str(m.text)[:100]))
        if mode == 'E': d.install_addon(ext, temporary=True)
        d.set_page_load_timeout(20)
        for u in PAGES:
            errs.clear()
            try:
                d.get(BASE + u)
            except Exception:
                errs.append('load timed out')
            time.sleep(2.5)
            print(mode, u, '|', d.execute_script('return ' + M), '|', errs[:3], flush=True)
        d.quit()

asyncio.run(chrome()) if browser == 'chrome' else firefox()
