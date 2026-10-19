# Loads each page desktop-sized with XSLT on and off, records the document, frames, and XSLTProcessor
# use, and saves the two viewport screenshots side by side to <out-dir>/review/<i>.png.
# Usage: check.py <chrome> broken-2025.csv <out-dir>  (prints JSON lines)
import asyncio, csv, json, os, sys
from playwright.async_api import async_playwright
from PIL import Image
chrome, inp, out = sys.argv[1:4]
FLAGS = {'on': ['--enable-features=XSLT', '--disable-features=GenerateXSLTWarningBanner'], 'off': ['--disable-features=XSLT']}
INIT = """(() => { window.__xslt = []; if (typeof XSLTProcessor === 'function') { const O = XSLTProcessor;
 const W = function() { window.__xslt.push(new Error().stack); return new O(); }; W.prototype = O.prototype;
 try { Object.defineProperty(window, 'XSLTProcessor', {value: W, writable: true, configurable: true}); } catch (e) {} } })();"""
M = """() => ({url: location.href, ct: document.contentType, title: document.title,
 pi: [...document.childNodes].filter(n => n.nodeType === 7).map(n => n.target + ' ' + n.data),
 xmlViewer: !!document.getElementById('xml-viewer-style') || (document.documentElement && document.documentElement.namespaceURI !== 'http://www.w3.org/1999/xhtml'),
 text: (document.body ? document.body.innerText : document.documentElement ? document.documentElement.textContent : '').slice(0, 300),
 xslt: (window.__xslt || []).length})"""
async def visit(br, url, tag, i):
    ctx = await br.new_context(viewport={'width': 1366, 'height': 768}, ignore_https_errors=True)
    await ctx.add_init_script(INIT)
    pg = await ctx.new_page(); rec = {}
    try:
        r = await pg.goto(url, wait_until='load', timeout=30000); rec['status'] = r.status if r else None
        await pg.wait_for_timeout(3000)
        rec.update(await pg.evaluate(M))
        rec['frames'] = []
        for fr in pg.frames[1:15]:
            try:
                f = await fr.evaluate(M); rec['frames'].append({k: f[k] for k in ('url', 'ct', 'pi', 'xmlViewer', 'xslt')})
            except Exception: pass
        await pg.screenshot(path=f'{out}/shots/{i:02}-{tag}.png')
    except Exception as e:
        rec['error'] = str(e).splitlines()[0][:200]
    await ctx.close(); return rec
async def g(c):
    try: return await asyncio.wait_for(c, 90)
    except asyncio.TimeoutError: return {'error': 'timeout'}
async def main():
    rows = list(csv.DictReader(open(inp)))
    os.makedirs(f'{out}/shots', exist_ok=True)
    os.makedirs(f'{out}/review', exist_ok=True)
    async with async_playwright() as p:
        on = await p.chromium.launch(executable_path=chrome, args=FLAGS['on'])
        off = await p.chromium.launch(executable_path=chrome, args=FLAGS['off'])
        sem = asyncio.Semaphore(4)
        async def one(i, r):
            async with sem:
                a = await g(visit(on, r['page'], 'on', i)); b = await g(visit(off, r['page'], 'off', i))
            print(json.dumps({'i': i, 'page': r['page'], 'in2026': r['in2026'], 'on': a, 'off': b}), flush=True)
            shots = [f'{out}/shots/{i:02}-{tag}.png' for tag in ('on', 'off')]
            if all(map(os.path.exists, shots)):
                A, B = map(Image.open, shots)
                im = Image.new('RGB', (A.width + B.width + 12, max(A.height, B.height)), 'red')
                im.paste(A, (0, 0))
                im.paste(B, (A.width + 12, 0))
                im.thumbnail((1400, 500))
                im.save(f'{out}/review/{i:02}.png')
        await asyncio.gather(*(one(i, r) for i, r in enumerate(rows)))
asyncio.run(main())
