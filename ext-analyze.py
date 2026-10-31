# Flags pages where the extension (E) differs from native XSLT (A) beyond the A vs A2 noise, shows
# the polyfill spinner or raw XML, or logs errors that A and A2 don't, and writes A|E pairs for them.
# Usage: ext-analyze.py <out-dir>   (writes <out-dir>/auto.csv and <out-dir>/review/<id>.png)
import csv, json, os, re, sys
from PIL import Image

out_dir = sys.argv[1]
rows = sorted((json.loads(l) for l in open(f'{out_dir}/results.jsonl')), key=lambda r: r['id'])
# Browser messages about XSLT's removal, and the extension's own progress messages.
IGNORE = re.compile(r'XSLTProcessor and XSLT Processing Instructions have been|XSLT polyfill transformation|'
                    r'XSLT Polyfill has transformed|Not running the XSLT polyfill')


def norm(s):
    return re.sub(r'\d+', 'N', s)[:150]


def messages(rec):
    out = {('exception', norm(e['message'])) for e in rec.get('pageErrors', [])}
    out |= {(c['type'], norm(c['text'])) for c in rec.get('console', [])
            if c['type'] in ('error', 'warning', 'warn') and not IGNORE.search(c['text'])}
    return out


def polyfill_log(rec):
    # Messages from libxslt in the polyfill (compile/transform diagnostics) and the polyfill itself.
    return [c['text'][:150] for c in rec.get('console', []) if not IGNORE.search(c['text']) and
            re.search(r'xsl|xpath|polyfill|wasm', c['text'], re.I)]


def flags(r):
    A, A2, E = r['A'], r['A2'], r['E']
    if A.get('error') or A2.get('error'):
        return 'not assessable', ['load error with native XSLT']
    if (A.get('status') or 200) >= 400:
        return 'not assessable', [f"HTTP {A['status']}"]
    out = []
    if E.get('error'):
        out.append('E: ' + E['error'][:80])
    if E.get('spinner') or any(f.get('spinner') for f in E.get('frames', [])):
        out.append('spinner still shown')
    if E.get('xmlViewer') and not A.get('xmlViewer'):
        out.append('raw XML in E')
    fa = sum(bool(f.get('xmlViewer')) for f in A.get('frames', []))
    fe = sum(bool(f.get('xmlViewer')) for f in E.get('frames', []))
    if fe > fa:
        out.append(f'raw XML in {fe - fa} frame(s) in E')
    if r['textRatioAE'] < min(r['textRatioAA2'], 0.98) or (r['pixAE'] or 0) > max((r['pixAA2'] or 0) * 1.5, 0.01):
        out.append(f"differs (text {r['textRatioAE']} vs noise {r['textRatioAA2']}, pixels {r['pixAE']} vs noise {r['pixAA2']})")
    return ('needs review' if out else 'same'), out


os.makedirs(f'{out_dir}/review', exist_ok=True)
with open(f'{out_dir}/auto.csv', 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['id', 'set', 'client', 'page', 'auto_rating', 'flags', 'e_only_messages', 'e_polyfill_log',
                'textRatioAA2', 'textRatioAE', 'pixAA2', 'pixAE'])
    for r in rows:
        rating, fl = flags(r)
        new = sorted(messages(r['E']) - messages(r['A']) - messages(r['A2']))
        if rating == 'same' and new:
            rating = 'needs review'
        w.writerow([r['id'], r['set'], r['client'], r['page'], rating, ' | '.join(fl),
                    ' | '.join(f'{t}: {m}' for t, m in new[:5]), ' | '.join(polyfill_log(r['E'])[:5]),
                    r['textRatioAA2'], r['textRatioAE'], r['pixAA2'], r['pixAE']])
        if rating != 'needs review' or not (r['A'].get('shot') and r['E'].get('shot')):
            continue
        a, b = Image.open(r['A']['shot']), Image.open(r['E']['shot'])
        h = min(1100, max(a.height, b.height))
        im = Image.new('RGB', (a.width + b.width + 12, h), 'red')
        im.paste(a.crop((0, 0, a.width, min(h, a.height))), (0, 0))
        im.paste(b.crop((0, 0, b.width, min(h, b.height))), (a.width + 12, 0))
        im.thumbnail((1500, 1100))
        im.save(f"{out_dir}/review/{r['id']}.png")
