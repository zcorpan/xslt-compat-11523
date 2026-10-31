# Checks whether a Wasm module compiled in an isolated-world content script can be handed to the page
# under a CSP without 'wasm-unsafe-eval' (csp.html), and without one (nocsp.html). Set GECKODRIVER for Firefox.
# Usage: run.py
import asyncio, functools, http.server, os, socket, sys, tempfile, threading, time
HERE = os.path.dirname(os.path.abspath(__file__))
class H(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
    def end_headers(self):
        if self.path.startswith('/csp.html'): self.send_header('Content-Security-Policy', "script-src 'self' 'unsafe-inline'")
        super().end_headers()
srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(H, directory=os.path.join(HERE, 'www')))
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = f'http://127.0.0.1:{srv.server_port}/'
EXT = os.path.join(HERE, 'ext')
async def chrome():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        s = socket.socket(); s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]; s.close()
        ctx = await p.chromium.launch_persistent_context(tempfile.mkdtemp(), executable_path='/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary', headless=True,
            args=['--enable-unsafe-extension-debugging', f'--remote-debugging-port={port}'], ignore_default_args=['--disable-extensions'])
        b = await p.chromium.connect_over_cdp(f'http://127.0.0.1:{port}')
        await (await b.new_browser_cdp_session()).send('Extensions.loadUnpacked', {'path': EXT})
        page = ctx.pages[0]
        for u in ('nocsp.html', 'csp.html'):
            await page.goto(BASE + u); await page.wait_for_timeout(1500)
            print('chrome', u, '|', await page.evaluate("document.getElementById('t').textContent"))
        await ctx.close()
def firefox():
    from selenium import webdriver
    from selenium.webdriver.firefox.options import Options
    from selenium.webdriver.firefox.service import Service
    o = Options(); o.binary_location = '/Applications/Firefox Nightly.app/Contents/MacOS/firefox'; o.add_argument('-headless')
    d = webdriver.Firefox(options=o, service=Service(os.environ['GECKODRIVER'])); d.install_addon(EXT, temporary=True)
    for u in ('nocsp.html', 'csp.html'):
        d.get(BASE + u); time.sleep(1.5)
        print('firefox', u, '|', d.execute_script("return document.getElementById('t').textContent"))
    d.quit()
asyncio.run(chrome()); firefox()
