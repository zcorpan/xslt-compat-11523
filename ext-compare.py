# Loads each affected page with native XSLT on and no extension (A, A2), and with native XSLT off and
# an XSLT polyfill extension installed (E), in a fresh browser profile per visit, and records
# measurements, console messages, and exceptions.
# Chrome: --enable-features=XSLT vs --disable-features=XSLT plus the extension via CDP
# Extensions.loadUnpacked. Firefox (geckodriver): dom.xslt.enabled true vs false plus the extension
# as a temporary add-on.
# Set GECKODRIVER to skip Selenium Manager, whose concurrent lookups race.
# Usage: ext-compare.py chrome|firefox <browser-executable> <extension-dir> <out-dir>
import asyncio, csv, difflib, functools, http.server, json, os, socket, sys, tempfile, threading, time
from PIL import Image, ImageChops

browser_name, exe, ext_dir, out_dir = sys.argv[1:5]
ROOT = os.path.dirname(os.path.abspath(__file__))
CHROME_MOBILE_UA = ('Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/158.0.0.0 Mobile Safari/537.36')
FIREFOX_MOBILE_UA = 'Mozilla/5.0 (Android 10; Mobile; rv:161.0) Gecko/161.0 Firefox/161.0'
WAIT_MS = 5000
MEASURE = """
return (() => ({
  url: location.href,
  contentType: document.contentType,
  title: document.title,
  xmlViewer: !!document.getElementById('xml-viewer-style') || (document.documentElement && document.documentElement.namespaceURI !== 'http://www.w3.org/1999/xhtml'),
  text: (document.body ? document.body.innerText : document.documentElement ? document.documentElement.textContent : '').slice(0, 3000),
  scrollHeight: document.documentElement ? document.documentElement.scrollHeight : 0,
  xsltProcessor: typeof XSLTProcessor !== 'function' ? 'none' : String(XSLTProcessor).includes('native code') ? 'native' : 'polyfill',
  spinner: !!document.getElementById('xslt-polyfill-spinner'),
  navStatus: (performance.getEntriesByType('navigation')[0] || {}).responseStatus,
}))()
"""
FRAME_KEYS = ('url', 'contentType', 'xmlViewer', 'xsltProcessor', 'spinner')


def load_rows():
    rows = []
    for i, l in enumerate(open(f'{ROOT}/sample.jsonl')):
        rows.append(json.loads(l) | {'id': f's{i:03}', 'set': 'sample'})
    for i, l in enumerate(open(f'{ROOT}/top100k.jsonl')):
        rows.append(json.loads(l) | {'id': f't{i:02}', 'set': 'top100k'})
    for i, r in enumerate(csv.DictReader(open(f'{ROOT}/followup-2025/broken-2025.csv'))):
        rows.append({'page': r['page'], 'client': 'desktop', 'id': f'f{i:02}', 'set': 'followup-2025'})
    return rows


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


server = http.server.ThreadingHTTPServer(
    ('127.0.0.1', 0), functools.partial(QuietHandler, directory=f'{ROOT}/sanity'))
threading.Thread(target=server.serve_forever, daemon=True).start()
SANITY = f'http://127.0.0.1:{server.server_port}/doc.xml'


def save_shot(png, path):
    with open(path, 'wb') as f:
        f.write(png)
    img = Image.open(path)
    if img.height > 4000:
        img.crop((0, 0, img.width, 4000)).save(path)


def free_port():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port


async def chrome_visit(p, row, tag):
    mobile = row['client'] == 'mobile'
    native = tag != 'E'
    port = free_port()
    args = (['--enable-features=XSLT', '--disable-features=GenerateXSLTWarningBanner'] if native else
            ['--disable-features=XSLT', '--enable-unsafe-extension-debugging', f'--remote-debugging-port={port}'])
    rec = {'tag': tag, 'console': [], 'pageErrors': []}
    ctx = await p.chromium.launch_persistent_context(
        tempfile.mkdtemp(prefix='xslt-ext-'), executable_path=exe, headless=True, args=args,
        ignore_default_args=['--disable-extensions'], ignore_https_errors=True,
        viewport={'width': 360, 'height': 640} if mobile else {'width': 1366, 'height': 768},
        is_mobile=mobile, has_touch=mobile, user_agent=CHROME_MOBILE_UA if mobile else None)
    try:
        if not native:
            cdp = await p.chromium.connect_over_cdp(f'http://127.0.0.1:{port}')
            session = await cdp.new_browser_cdp_session()
            await session.send('Extensions.loadUnpacked', {'path': ext_dir})
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        page.on('console', lambda m: len(rec['console']) < 40 and rec['console'].append(
            {'type': m.type, 'text': m.text[:300], 'url': (m.location or {}).get('url', '')[:200]}))
        page.on('pageerror', lambda e: len(rec['pageErrors']) < 20 and rec['pageErrors'].append(
            {'message': str(e.message)[:300], 'stack': (e.stack or '')[:600]}))
        resp = await page.goto(row['page'], wait_until='load', timeout=30000)
        rec['status'] = resp.status if resp else None
        await page.wait_for_timeout(WAIT_MS)
        rec.update(await page.evaluate('() => {' + MEASURE + '}'))
        frames = []
        for fr in page.frames[1:20]:
            try:
                fm = await fr.evaluate('() => {' + MEASURE + '}')
                frames.append({k: fm[k] for k in FRAME_KEYS} | {'text': fm['text'][:200]})
            except Exception as e:
                frames.append({'url': fr.url, 'error': str(e)[:100]})
        rec['frames'] = frames
        shot = f"{out_dir}/shots/{row['id']}-{tag}.png"
        save_shot(await page.screenshot(full_page=True, scale='css', timeout=20000), shot)
        rec['shot'] = shot
    except Exception as e:
        rec['error'] = str(e).splitlines()[0][:300]
    finally:
        await ctx.close()
    return rec


def firefox_visit_sync(row, tag, holder):
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.firefox.options import Options
    from selenium.webdriver.firefox.service import Service
    mobile = row['client'] == 'mobile'
    native = tag != 'E'
    rec = {'tag': tag, 'console': [], 'pageErrors': []}
    o = Options()
    o.binary_location = exe
    o.add_argument('-headless')
    o.accept_insecure_certs = True
    o.enable_bidi = True
    o.set_preference('dom.xslt.enabled', native)
    if mobile:
        o.set_preference('general.useragent.override', FIREFOX_MOBILE_UA)
    d = webdriver.Firefox(options=o, service=Service(os.environ.get('GECKODRIVER')))
    holder.append(d)
    try:
        d.set_window_size(360, 640) if mobile else d.set_window_size(1366, 768)
        d.set_page_load_timeout(30)
        d.script.add_console_message_handler(lambda m: len(rec['console']) < 40 and rec['console'].append(
            {'type': m.level, 'text': str(m.text)[:300]}))
        d.script.add_javascript_error_handler(lambda m: len(rec['pageErrors']) < 20 and rec['pageErrors'].append(
            {'message': str(m.text)[:300], 'stack': json.dumps(getattr(m, 'stacktrace', None) or getattr(m, 'stack_trace', None), default=str)[:600]}))
        if not native:
            d.install_addon(ext_dir, temporary=True)
        try:
            d.get(row['page'])
        except Exception as e:
            rec['loadError'] = str(e).splitlines()[0][:200]
        time.sleep(WAIT_MS / 1000)
        rec.update(d.execute_script(MEASURE))
        rec['status'] = rec['navStatus'] or None
        frames = []
        for i, _ in enumerate(d.find_elements(By.CSS_SELECTOR, 'iframe, frame')[:19]):
            try:
                d.switch_to.frame(i)
                fm = d.execute_script(MEASURE)
                frames.append({k: fm[k] for k in FRAME_KEYS} | {'text': fm['text'][:200]})
            except Exception as e:
                frames.append({'error': str(e).splitlines()[0][:100]})
            finally:
                d.switch_to.default_content()
        rec['frames'] = frames
        shot = f"{out_dir}/shots/{row['id']}-{tag}.png"
        try:
            save_shot(d.get_full_page_screenshot_as_png(), shot)
        except Exception:
            save_shot(d.get_screenshot_as_png(), shot)
        rec['shot'] = shot
    except Exception as e:
        rec['error'] = str(e).splitlines()[0][:300]
    finally:
        try:
            d.quit()
        except Exception:
            pass
    return rec


async def firefox_visit(p, row, tag):
    holder = []
    task = asyncio.to_thread(firefox_visit_sync, row, tag, holder)
    try:
        return await asyncio.wait_for(task, 110)
    except asyncio.TimeoutError:
        for d in holder:
            threading.Thread(target=d.quit, daemon=True).start()
        raise


VISIT = {'chrome': chrome_visit, 'firefox': firefox_visit}[browser_name]


async def guarded(p, row, tag):
    try:
        return await asyncio.wait_for(VISIT(p, row, tag), 120)
    except asyncio.TimeoutError:
        return {'tag': tag, 'error': 'visit timed out after 120s', 'pageErrors': [], 'console': []}


def pixel_diff(a, b):
    try:
        ia, ib = Image.open(a).convert('RGB'), Image.open(b).convert('RGB')
    except Exception:
        return None
    w, h = min(ia.width, ib.width), min(ia.height, ib.height, 2000)
    d = ImageChops.difference(ia.crop((0, 0, w, h)), ib.crop((0, 0, w, h))).convert('L')
    changed = sum(1 for p in d.get_flattened_data() if p > 16)
    return round(changed / (w * h), 4) if w * h else None


async def main():
    rows = load_rows()
    only = set(sys.argv[5].split(',')) if len(sys.argv) > 5 else None
    os.makedirs(f'{out_dir}/shots', exist_ok=True)
    results_path = f'{out_dir}/results.jsonl'
    done = {json.loads(l)['id'] for l in open(results_path)} if os.path.exists(results_path) else set()
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        for tag in ('A', 'E'):
            rec = await VISIT(p, {'page': SANITY, 'client': 'desktop', 'id': 'sanity'}, tag)
            want = 'native' if tag == 'A' else 'polyfill'
            ok = 'transformed: hello' in rec.get('text', '') and rec.get('xsltProcessor') == want
            print(tag, 'sanity check', 'passed' if ok else f'FAILED {rec}', flush=True)
            if not ok:
                sys.exit(1)
        sem = asyncio.Semaphore(4)

        async def one(r):
            if r['id'] in done or (only and r['id'] not in only):
                return
            async with sem:
                a = await guarded(p, r, 'A')
                a2 = await guarded(p, r, 'A2')
                e = await guarded(p, r, 'E')
            res = {k: r[k] for k in ('id', 'set', 'page', 'client', 'counters', 'stratum') if k in r}
            res.update({'A': a, 'A2': a2, 'E': e})
            res['textRatioAA2'] = round(difflib.SequenceMatcher(None, a.get('text', ''), a2.get('text', '')).ratio(), 3)
            res['textRatioAE'] = round(difflib.SequenceMatcher(None, a.get('text', ''), e.get('text', '')).ratio(), 3)
            res['pixAA2'] = pixel_diff(a.get('shot'), a2.get('shot'))
            res['pixAE'] = pixel_diff(a.get('shot'), e.get('shot'))
            with open(results_path, 'a') as f:
                f.write(json.dumps(res) + '\n')
            print(r['id'], res['textRatioAE'], res['pixAE'], len(e.get('pageErrors', [])), flush=True)

        await asyncio.gather(*(one(r) for r in rows))

asyncio.run(main())
