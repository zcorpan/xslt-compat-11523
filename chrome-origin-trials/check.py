# Loads each URL of an XSLT origin-trial list desktop-sized in four setups, in a fresh context or
# profile per visit, and records measurements, console messages, page errors, and (Chrome) the
# XSLT trial status from CDP Page.getOriginTrials, and XSLTProcessor use (construction, import,
# transform, with the top stack frames) in every frame:
#   C   Chrome, default flags (XSLT off unless the page's origin-trial token turns it on)
#   C0  Chrome, default flags, with Origin-Trial headers and meta tags stripped from documents (as
#       after the trial ends; --disable-origin-trial-controlled-blink-features leaves it enabled)
#   F   Firefox, dom.xslt.enabled false
#   F1  Firefox, dom.xslt.enabled true
# Writes <crawl date>/results.jsonl, review/<id>.png (C | C0 | F | F1 viewports), meta.json, and
# review.csv (rows added for new ids only, prefilled from the previous month's ratings).
# For pages in INTERACT, it then runs each step (read-only actions such as a catalog search), waits,
# and records the measurements again in `after`, with review/<id>-after<n>.png.
# Pass ids to redo just those visits. Set GECKODRIVER to skip Selenium Manager.
# Usage: check.py <chrome> <firefox> XSLT-urls-<date>.csv [id,id,...]
import asyncio, csv, datetime, difflib, functools, glob, html, http.server, json, os, re, sys, threading, time, urllib.parse
from PIL import Image, ImageDraw

chrome_exe, firefox_exe, csv_path = sys.argv[1:4]
only = set(sys.argv[4].split(',')) if len(sys.argv) > 4 else None
HERE = os.path.dirname(os.path.abspath(__file__))
DATE = re.search(r'\d{4}-\d{2}-\d{2}', os.path.basename(csv_path)).group(0)
OUT = f'{HERE}/{DATE}'
TAGS = ('C', 'C0', 'F', 'F1')
META_OT = re.compile(rb'<meta[^>]+http-equiv\s*=\s*["\']?origin-trial[^>]*>', re.I)
INIT = """(() => {
  const log = [];
  Object.defineProperty(window, '__xsltLog', {value: log});
  const where = () => (new Error().stack || '').split('\\n').filter(l => l && !l.includes('__xsltWrap')).slice(1, 4).join(' | ');
  const wrap = () => {
    if (typeof XSLTProcessor !== 'function' || window.__xsltNative) return;
    Object.defineProperty(window, '__xsltNative', {value: XSLTProcessor});
    const P = XSLTProcessor.prototype;
    for (const m of ['importStylesheet', 'transformToFragment', 'transformToDocument']) {
      const o = P[m];
      P[m] = function __xsltWrap(...a) { log.push(m + ' ' + where()); return o.apply(this, a); };
    }
    const O = XSLTProcessor;
    const W = function __xsltWrap() { log.push('new ' + where()); return new O(); };
    W.prototype = O.prototype;
    Object.defineProperty(window, 'XSLTProcessor', {value: W, writable: true, configurable: true});
  };
  wrap();
  document.addEventListener('DOMContentLoaded', wrap);
  window.addEventListener('load', wrap);
})();"""
WAIT_MS = 5000
INTERACT = {
    # Catalog search for a common author name, then the first result's record card.
    'https://opac.tverlib.ru/': ["""
      document.getElementById('itemsimple').value = 'Пушкин';
      document.querySelector('.simplebutton').dispatchEvent(new MouseEvent('mousedown', {bubbles: true}));
    """, """
      const el = [...document.querySelectorAll('*')].find(e => e.children.length === 0 && e.textContent.trim() === 'Карточка');
      for (const t of ['mousedown', 'mouseup', 'click']) el.dispatchEvent(new MouseEvent(t, {bubbles: true}));
      setTimeout(() => el.scrollIntoView({block: 'start'}), 5000);
    """],
}
MEASURE = """
return (() => ({
  url: location.href,
  contentType: document.contentType,
  title: document.title,
  pi: [...document.childNodes].filter(n => n.nodeType === 7).map(n => n.target + ' ' + n.data),
  xmlViewer: !!document.getElementById('xml-viewer-style') || (document.documentElement && document.documentElement.namespaceURI !== 'http://www.w3.org/1999/xhtml'),
  text: (document.body ? document.body.innerText : document.documentElement ? document.documentElement.textContent : '').slice(0, 3000),
  xsltProcessor: typeof XSLTProcessor !== 'function' ? 'none' : window.__xsltNative || String(XSLTProcessor).includes('native code') ? 'native' : 'other',
  xsltLog: (window.__xsltLog || []).slice(0, 20),
  textLength: document.body ? document.body.innerText.length : 0,
  textHash: document.body ? [...document.body.innerText].reduce((h, c) => (h * 31 + c.codePointAt(0)) >>> 0, 7) : 0,
  navStatus: (performance.getEntriesByType('navigation')[0] || {}).responseStatus,
}))()
"""
FRAME_KEYS = ('url', 'contentType', 'pi', 'xmlViewer', 'xsltProcessor', 'xsltLog')


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


server = http.server.ThreadingHTTPServer(
    ('127.0.0.1', 0), functools.partial(QuietHandler, directory=os.path.join(HERE, '..', 'sanity')))
threading.Thread(target=server.serve_forever, daemon=True).start()
SANITY = f'http://127.0.0.1:{server.server_port}/doc.xml'
SANITY_PROC = f'http://127.0.0.1:{server.server_port}/proc.html'


async def strip_origin_trial(route):
    if route.request.resource_type != 'document':
        return await route.continue_()
    try:
        resp = await route.fetch(max_redirects=0)
    except Exception:
        return await route.abort()
    headers = {k: v for k, v in resp.headers.items() if k.lower() != 'origin-trial'}
    body = await resp.body()
    if 300 <= resp.status < 400 and 'location' in headers:
        # Playwright doesn't route a redirect's target, so redirect with a meta refresh instead.
        target = html.escape(urllib.parse.urljoin(route.request.url, headers.pop('location')))
        headers = {k: v for k, v in headers.items() if k.lower() in ('set-cookie',)}
        headers['content-type'] = 'text/html'
        return await route.fulfill(status=200, headers=headers,
                                   body=f'<meta http-equiv="refresh" content="0;url={target}">')
    if 'html' in headers.get('content-type', ''):
        body = META_OT.sub(b'', body)
    await route.fulfill(status=resp.status, headers=headers, body=body)


async def chrome_frames(page):
    frames = []
    for fr in page.frames[1:20]:
        try:
            fm = await fr.evaluate('() => {' + MEASURE + '}')
            frames.append({k: fm[k] for k in FRAME_KEYS} | {'text': fm['text'][:200]})
        except Exception as e:
            frames.append({'url': fr.url, 'error': str(e)[:100]})
    return frames


async def chrome_visit(browsers, url, tag, shot):
    rec = {'tag': tag, 'console': [], 'pageErrors': []}
    ctx = await browsers.new_context(viewport={'width': 1366, 'height': 768}, ignore_https_errors=True)
    await ctx.add_init_script(INIT)
    if tag == 'C0':
        await ctx.route('**/*', strip_origin_trial)
    try:
        page = await ctx.new_page()
        page.on('console', lambda m: len(rec['console']) < 40 and rec['console'].append(
            {'type': m.type, 'text': m.text[:300], 'url': (m.location or {}).get('url', '')[:200]}))
        page.on('pageerror', lambda e: len(rec['pageErrors']) < 20 and rec['pageErrors'].append(
            {'message': str(e.message)[:300], 'stack': (e.stack or '')[:600]}))
        try:
            resp = await page.goto(url, wait_until='load', timeout=30000)
            rec['status'] = resp.status if resp else None
        except Exception as e:
            rec['loadError'] = str(e).splitlines()[0][:200]
        await page.wait_for_timeout(WAIT_MS)
        await page.wait_for_load_state('load')
        rec.update(await page.evaluate('() => {' + MEASURE + '}'))
        cdp = await ctx.new_cdp_session(page)
        tree = await cdp.send('Page.getFrameTree')
        trials = (await cdp.send('Page.getOriginTrials', {'frameId': tree['frameTree']['frame']['id']}))['originTrials']
        rec['originTrials'] = [{'trialName': t['trialName'], 'status': t['status'],
                                'tokens': [{'status': k['status'],
                                            'origin': (k.get('parsedToken') or {}).get('origin'),
                                            'matchSubDomains': (k.get('parsedToken') or {}).get('matchSubDomains')}
                                           for k in t['tokensWithStatus']]}
                               for t in trials]
        rec['frames'] = await chrome_frames(page)
        await page.screenshot(path=shot, timeout=20000)
        rec['shot'] = os.path.relpath(shot, os.path.dirname(HERE))
        rec['after'] = []
        for n, step in enumerate(INTERACT.get(url, [])):
            await page.evaluate('() => {' + step + '}')
            await page.wait_for_timeout(2 * WAIT_MS)
            rec['after'].append(await page.evaluate('() => {' + MEASURE + '}') | {'frames': await chrome_frames(page)})
            await page.screenshot(path=shot.replace('.png', f'-after{n}.png'), timeout=20000)
    except Exception as e:
        rec['error'] = str(e).splitlines()[0][:300]
    finally:
        await ctx.close()
    return rec


def firefox_visit_sync(url, tag, shot, holder):
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.firefox.options import Options
    from selenium.webdriver.firefox.service import Service
    rec = {'tag': tag, 'console': [], 'pageErrors': []}
    o = Options()
    o.binary_location = firefox_exe
    o.add_argument('-headless')
    o.accept_insecure_certs = True
    o.enable_bidi = True
    o.set_preference('dom.xslt.enabled', tag == 'F1')
    d = webdriver.Firefox(options=o, service=Service(os.environ.get('GECKODRIVER')))
    holder.append(d)
    try:
        rec['browserVersion'] = d.capabilities.get('browserVersion')
        d.set_window_size(1366, 768)
        iw, ih = d.execute_script('return [innerWidth, innerHeight]')
        d.set_window_size(1366 + 1366 - iw, 768 + 768 - ih)
        d.script.pin('() => { ' + INIT + ' }')
        d.set_page_load_timeout(30)
        d.script.add_console_message_handler(lambda m: len(rec['console']) < 40 and rec['console'].append(
            {'type': m.level, 'text': str(m.text)[:300]}))
        d.script.add_javascript_error_handler(lambda m: len(rec['pageErrors']) < 20 and rec['pageErrors'].append(
            {'message': str(m.text)[:300], 'stack': json.dumps(getattr(m, 'stacktrace', None) or getattr(m, 'stack_trace', None), default=str)[:600]}))
        try:
            d.get(url)
        except Exception as e:
            rec['loadError'] = str(e).splitlines()[0][:200]
        time.sleep(WAIT_MS / 1000)
        rec.update(d.execute_script(MEASURE))
        rec['status'] = rec['navStatus'] or None
        def firefox_frames():
            frames = []
            for el in d.find_elements(By.CSS_SELECTOR, 'iframe, frame, object')[:19]:
                try:
                    d.switch_to.frame(el)
                    fm = d.execute_script(MEASURE)
                    frames.append({k: fm[k] for k in FRAME_KEYS} | {'text': fm['text'][:200]})
                except Exception as e:
                    frames.append({'error': str(e).splitlines()[0][:100]})
                finally:
                    d.switch_to.default_content()
            return frames
        rec['frames'] = firefox_frames()
        with open(shot, 'wb') as f:
            f.write(d.get_screenshot_as_png())
        rec['shot'] = os.path.relpath(shot, os.path.dirname(HERE))
        rec['after'] = []
        for n, step in enumerate(INTERACT.get(url, [])):
            d.execute_script(step)
            time.sleep(2 * WAIT_MS / 1000)
            rec['after'].append(d.execute_script(MEASURE) | {'frames': firefox_frames()})
            with open(shot.replace('.png', f'-after{n}.png'), 'wb') as f:
                f.write(d.get_screenshot_as_png())
    except Exception as e:
        rec['error'] = str(e).splitlines()[0][:300]
    finally:
        try:
            d.quit()
        except Exception:
            pass
    return rec


async def firefox_visit(url, tag, shot):
    holder = []
    try:
        return await asyncio.wait_for(asyncio.to_thread(firefox_visit_sync, url, tag, shot, holder), 110)
    except asyncio.TimeoutError:
        for d in holder:
            threading.Thread(target=d.quit, daemon=True).start()
        raise


async def visit(browsers, url, tag, shot):
    try:
        c = chrome_visit(browsers, url, tag, shot) if tag.startswith('C') else firefox_visit(url, tag, shot)
        return await asyncio.wait_for(c, 120)
    except asyncio.TimeoutError:
        return {'tag': tag, 'error': 'visit timed out after 120s', 'pageErrors': [], 'console': []}


def review_image(rid, suffix=''):
    shots = [f'{OUT}/shots/{rid}-{t}{suffix}.png' for t in TAGS]
    imgs = [Image.open(s).convert('RGB') if os.path.exists(s) else Image.new('RGB', (1366, 768), 'gray') for s in shots]
    w, h = max(i.width for i in imgs), max(i.height for i in imgs)
    im = Image.new('RGB', (4 * w + 3 * 12, h + 40), 'red')
    draw = ImageDraw.Draw(im)
    for n, (t, i) in enumerate(zip(TAGS, imgs)):
        im.paste(i, (n * (w + 12), 40))
        draw.text((n * (w + 12) + 8, 8), t, fill='white', font_size=28)
    im.thumbnail((2800, 1000))
    im.save(f'{OUT}/review/{rid}{suffix}.png')


def text_ratio(a, b):
    return round(difflib.SequenceMatcher(None, a.get('text', ''), b.get('text', '')).ratio(), 3)


def auto_rating(r):
    c, f = r['C'], r['F']
    if any('error' in r[t] for t in TAGS) or (c.get('status') or 0) >= 400:
        return 'not assessable', 'auto: a setup failed to load or C got HTTP 4xx/5xx'
    states = lambda x: [x] + x.get('after', [])
    raw = lambda x: any(m.get('xmlViewer') or any(fr.get('xmlViewer') for fr in m.get('frames', [])) for m in states(x))
    if raw(f) and not raw(c):
        return '', 'auto: F shows raw XML in the page or a frame, C does not'
    used = lambda x: any(m.get('xsltLog') or any(fr.get('xsltLog') for fr in m.get('frames', [])) for m in states(x))
    if not used(c) and not used(r['F1']):
        return '', 'auto: no XSLTProcessor use in C or F1'
    if r['textRatioCF'] >= 0.98 and not raw(f):
        return '', 'auto: F text matches C'
    return '', 'auto: needs review'


def previous_ratings():
    prev = sorted(d for d in glob.glob(f'{HERE}/????-??-??/review.csv') if os.path.dirname(d) < OUT)
    if not prev:
        return {}
    return {r['page']: r for r in csv.DictReader(open(prev[-1]))}


async def main():
    rows = [r | {'id': f'{i:02}'} for i, r in enumerate(csv.DictReader(open(csv_path)))]
    for d in ('shots', 'review'):
        os.makedirs(f'{OUT}/{d}', exist_ok=True)
    results_path = f'{OUT}/results.jsonl'
    old = [json.loads(l) for l in open(results_path)] if os.path.exists(results_path) else []
    if only:
        old = [r for r in old if r['id'] not in only]
        open(results_path, 'w').write(''.join(json.dumps(r) + '\n' for r in old))
    done = {r['id'] for r in old}
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browsers = await p.chromium.launch(executable_path=chrome_exe, headless=True)
        meta = {'run': datetime.date.today().isoformat(), 'csv': os.path.basename(csv_path),
                'chrome': browsers.version}
        for t in TAGS:
            rec = await visit(browsers, SANITY, t, f'{OUT}/shots/sanity-{t}.png')
            want_native = t == 'F1'
            ok = (('transformed: hello' in rec.get('text', '')) == want_native and
                  rec.get('xsltProcessor') == ('native' if want_native else 'none'))
            print(t, 'sanity check', 'passed' if ok else f'FAILED {rec}', flush=True)
            if not ok:
                sys.exit(1)
            if t == 'F':
                meta['firefox'] = rec.get('browserVersion')
        for t in ('C', 'F1'):
            log = (await visit(browsers, SANITY_PROC, t, f'{OUT}/shots/sanity-proc-{t}.png')).get('xsltLog', [])
            ok = [l.split()[0] for l in log] == (['new', 'importStylesheet'] if t == 'F1' else [])
            print(t, 'logging sanity check', 'passed' if ok else f'FAILED {log}', flush=True)
            if not ok:
                sys.exit(1)
        meta_path = f'{OUT}/meta.json'
        if not os.path.exists(meta_path):
            json.dump(meta, open(meta_path, 'w'), indent=1)
        sem = asyncio.Semaphore(4)

        async def one(r):
            if r['id'] in done or (only and r['id'] not in only):
                return
            async with sem:
                res = {'id': r['id'], 'page': r['URL'], 'run': meta['run']}
                for t in TAGS:
                    res[t] = await visit(browsers, r['URL'], t, f"{OUT}/shots/{r['id']}-{t}.png")
            res['textRatioCF'] = text_ratio(res['C'], res['F'])
            res['textRatioCC0'] = text_ratio(res['C'], res['C0'])
            res['textRatioFF1'] = text_ratio(res['F'], res['F1'])
            with open(results_path, 'a') as f:
                f.write(json.dumps(res) + '\n')
            review_image(r['id'])
            for n, _ in enumerate(INTERACT.get(r['URL'], [])):
                review_image(r['id'], f'-after{n}')
            print(r['id'], r['URL'], res['textRatioCF'], [res[t].get('xsltProcessor') for t in TAGS], flush=True)

        await asyncio.gather(*(one(r) for r in rows))
        await browsers.close()

    results = {json.loads(l)['id']: json.loads(l) for l in open(results_path)}
    review_path = f'{OUT}/review.csv'
    existing = list(csv.DictReader(open(review_path))) if os.path.exists(review_path) else []
    have = {r['id'] for r in existing}
    prev = previous_ratings()
    for r in rows:
        if r['id'] in have or r['id'] not in results:
            continue
        rating, note = auto_rating(results[r['id']])
        if r['URL'] in prev:
            rating, note = prev[r['URL']]['rating'], 'prev: ' + prev[r['URL']]['note']
        existing.append({'id': r['id'], 'page': r['URL'], 'rating': rating, 'note': note})
    existing.sort(key=lambda r: r['id'])
    with open(review_path, 'w', newline='') as f:
        w = csv.DictWriter(f, ['id', 'page', 'rating', 'note'])
        w.writeheader()
        w.writerows(existing)

asyncio.run(main())
