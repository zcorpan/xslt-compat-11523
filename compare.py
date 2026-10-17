# Loads each sampled page in Chrome with XSLT on (A, A2) and off (B) and records measurements.
# Usage: compare.py <chrome-executable> <sample.jsonl> <out-dir>
import asyncio, difflib, functools, http.server, json, os, sys, threading
from playwright.async_api import async_playwright
from PIL import Image, ImageChops

FLAGS = {
    'on': ['--enable-features=XSLT', '--disable-features=GenerateXSLTWarningBanner'],
    'off': ['--disable-features=XSLT'],
}
MOBILE_UA = ('Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) '
             'Chrome/158.0.0.0 Mobile Safari/537.36')
INIT = """
(() => {
  window.__xslt = [];
  if (typeof XSLTProcessor === 'function') {
    const Orig = XSLTProcessor;
    const Wrapped = function() { window.__xslt.push(new Error().stack); return new Orig(); };
    Wrapped.prototype = Orig.prototype;
    try { Object.defineProperty(window, 'XSLTProcessor', {value: Wrapped, writable: true, configurable: true}); } catch (e) {}
  }
})();
"""
MEASURE = """
() => ({
  url: location.href,
  contentType: document.contentType,
  title: document.title,
  xmlViewer: !!document.getElementById('xml-viewer-style') || (document.documentElement && document.documentElement.namespaceURI !== 'http://www.w3.org/1999/xhtml'),
  text: (document.body ? document.body.innerText : document.documentElement ? document.documentElement.textContent : '').slice(0, 3000),
  scrollHeight: document.documentElement ? document.documentElement.scrollHeight : 0,
  xsltStacks: (window.__xslt || []).slice(0, 3),
})
"""

chrome, sample_path, out_dir = sys.argv[1], sys.argv[2], sys.argv[3]
class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


sanity_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sanity')
server = http.server.ThreadingHTTPServer(
    ('127.0.0.1', 0), functools.partial(QuietHandler, directory=sanity_dir))
threading.Thread(target=server.serve_forever, daemon=True).start()
os.makedirs(f'{out_dir}/shots', exist_ok=True)
results_path = f'{out_dir}/results.jsonl'
done = set()
if os.path.exists(results_path):
    done = {json.loads(l)['page'] + '|' + json.loads(l)['client'] for l in open(results_path)}


async def visit(browser, row, tag):
    mobile = row['client'] == 'mobile'
    ctx = await browser.new_context(
        viewport={'width': 360, 'height': 640} if mobile else {'width': 1366, 'height': 768},
        is_mobile=mobile, has_touch=mobile, user_agent=MOBILE_UA if mobile else None,
        ignore_https_errors=True)
    await ctx.add_init_script(INIT)
    page = await ctx.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)[:300]))
    rec = {'tag': tag}
    try:
        resp = await page.goto(row['page'], wait_until='load', timeout=30000)
        rec['status'] = resp.status if resp else None
        await page.wait_for_timeout(3000)
        rec.update(await page.evaluate(MEASURE))
        frames = []
        for fr in page.frames[1:20]:
            try:
                fm = await fr.evaluate(MEASURE)
                frames.append({k: fm[k] for k in ('url', 'contentType', 'xmlViewer', 'xsltStacks')} | {'text': fm['text'][:200]})
            except Exception as e:
                frames.append({'url': fr.url, 'error': str(e)[:100]})
        rec['frames'] = frames
        shot = f"{out_dir}/shots/{row['idx']}-{tag}.png"
        await page.screenshot(path=shot, full_page=True, scale='css', timeout=20000)
        img = Image.open(shot)
        if img.height > 4000:
            img.crop((0, 0, img.width, 4000)).save(shot)
        rec['shot'] = shot
    except Exception as e:
        rec['error'] = str(e).splitlines()[0][:300]
    rec['pageErrors'] = errors[:10]
    await ctx.close()
    return rec


async def guarded(browser, row, tag):
    try:
        return await asyncio.wait_for(visit(browser, row, tag), 90)
    except asyncio.TimeoutError:
        return {'tag': tag, 'error': 'visit timed out after 90s', 'pageErrors': []}


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
    rows = [json.loads(l) for l in open(sample_path)]
    for i, r in enumerate(rows):
        r['idx'] = i
    async with async_playwright() as p:
        on = await p.chromium.launch(executable_path=chrome, args=FLAGS['on'])
        off = await p.chromium.launch(executable_path=chrome, args=FLAGS['off'])
        for name, br in (('on', on), ('off', off)):
            pg = await br.new_page()
            await pg.goto(f'http://127.0.0.1:{server.server_port}/doc.xml')
            ok = ('transformed' in await pg.content()) == (name == 'on')
            print(name, 'sanity check', 'passed' if ok else 'FAILED', flush=True)
            if not ok:
                sys.exit(1)
            await pg.close()
        sem = asyncio.Semaphore(4)

        async def one(r):
            if r['page'] + '|' + r['client'] in done:
                return
            async with sem:
                a = await guarded(on, r, 'A')
                a2 = await guarded(on, r, 'A2')
                b = await guarded(off, r, 'B')
            res = {k: r[k] for k in ('idx', 'page', 'client', 'is_root_page', 'rank', 'counters', 'stratum', 'stratum_size')}
            res.update({'A': a, 'A2': a2, 'B': b})
            res['textRatioAA2'] = round(difflib.SequenceMatcher(None, a.get('text', ''), a2.get('text', '')).ratio(), 3)
            res['textRatioAB'] = round(difflib.SequenceMatcher(None, a.get('text', ''), b.get('text', '')).ratio(), 3)
            res['pixAA2'] = pixel_diff(a.get('shot'), a2.get('shot'))
            res['pixAB'] = pixel_diff(a.get('shot'), b.get('shot'))
            with open(results_path, 'a') as f:
                f.write(json.dumps(res) + '\n')
            print(r['idx'], r['stratum'], res['textRatioAB'], res['pixAB'], flush=True)

        await asyncio.gather(*(one(r) for r in rows))
        await on.close()
        await off.close()

asyncio.run(main())
