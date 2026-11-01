# Like scan-case.py, with document.write and writeln instrumented too (instr-write.js).
# Usage: scan-write.py <pages.jsonl> <out.jsonl>
import asyncio, json, os, re, sys
from playwright.async_api import async_playwright
CHROME = '/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary'
INSTR = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instr-write.js')).read()
MOBILE_UA = 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/158.0.0.0 Mobile Safari/537.36'
FRAME_JS = """() => ({url: location.href, contentType: document.contentType, log: window.__caseLog || [],
  inline: [...document.querySelectorAll('style')].map(s => s.textContent).join('\\n'),
  sheets: [...document.styleSheets].map(s => s.href).filter(Boolean)})"""
rows = [json.loads(l) for l in open(sys.argv[1])]
out = open(sys.argv[2], 'a')
async def visit(browser, r):
    mobile = r['client'] == 'mobile'
    ctx = await browser.new_context(viewport={'width': 360, 'height': 640} if mobile else {'width': 1366, 'height': 768}, is_mobile=mobile, has_touch=mobile, user_agent=MOBILE_UA if mobile else None, ignore_https_errors=True)
    await ctx.add_init_script(INSTR)
    page = await ctx.new_page()
    doc_types, css = {}, {}
    async def on_response(resp):
        try:
            rt = resp.request.resource_type
            if rt == 'document': doc_types[resp.url] = (resp.headers.get('content-type') or '').split(';')[0].strip().lower()
            elif rt == 'stylesheet' and resp.ok: css[resp.url] = (await resp.text())[:300000]
        except Exception: pass
    page.on('response', lambda resp: asyncio.ensure_future(on_response(resp)))
    rec = {'page': r['page'], 'client': r['client'], 'id': r['id']}
    try:
        await page.goto(r['page'], wait_until='load', timeout=30000); await page.wait_for_timeout(3000)
        frames = []
        for fr in page.frames[:20]:
            try: frames.append(await fr.evaluate(FRAME_JS))
            except Exception as e: frames.append({'url': fr.url, 'error': str(e)[:100]})
        # XSLT output: the response was XML, the document is HTML.
        xslt = []
        for f in frames:
            rtype = doc_types.get(f.get('url'), '')
            if f.get('contentType') == 'text/html' and (rtype in ('text/xml', 'application/xml') or rtype.endswith('+xml')):
                f['cssText'] = f['inline'] + '\n' + '\n'.join(css.get(h, '') for h in f['sheets'])
                xslt.append(f)
        # Selectors with uppercase type or attribute names, tested natively in their frame.
        for f in xslt:
            sels = set()
            text = re.sub(r'/\*.*?\*/', '', f.pop('cssText'), flags=re.S)
            for block in re.findall(r'([^{}@;]+)\{', text):
                for sel in block.split(','):
                    sel = sel.strip()
                    if re.search(r'(?:^|[\s>+~(])[A-Za-z]*[A-Z][A-Za-z0-9]*|\[\s*[A-Za-z-]*[A-Z]', sel) and len(sel) < 200: sels.add(sel)
            fr = next((x for x in page.frames if x.url == f['url']), None)
            f['upperSelectors'] = []
            for sel in sorted(sels)[:300]:
                n = await fr.evaluate('(s) => { try { return document.querySelectorAll(s).length } catch (e) { return -1 } }', sel) if fr else None
                f['upperSelectors'].append([sel, n])
            del f['inline']
        rec['xsltFrames'] = xslt
        rec['otherFrames'] = len(frames) - len(xslt)
    except Exception as e:
        rec['error'] = str(e).splitlines()[0][:200]
    await ctx.close()
    return rec
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME, args=['--enable-features=XSLT', '--disable-features=GenerateXSLTWarningBanner'])
        sem = asyncio.Semaphore(4)
        async def one(r):
            async with sem:
                try: rec = await asyncio.wait_for(visit(b, r), 90)
                except asyncio.TimeoutError: rec = {'page': r['page'], 'client': r['client'], 'id': r['id'], 'error': 'timeout'}
            out.write(json.dumps(rec) + '\n'); out.flush()
            print(r['id'], len(rec.get('xsltFrames', [])), rec.get('error', ''), flush=True)
        await asyncio.gather(*(one(r) for r in rows))
        await b.close()
asyncio.run(main())
