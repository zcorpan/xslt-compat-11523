# Rates the clear cases in compare.py's output and writes A|B pairs for the rest to review by hand.
# Usage: analyze.py <out-dir>   (writes <out-dir>/auto.csv and <out-dir>/review/<idx>.png)
import csv, json, os, re, sys
from PIL import Image

out_dir = sys.argv[1]
rows = sorted((json.loads(l) for l in open(f'{out_dir}/results.jsonl')), key=lambda r: r['idx'])


def xslt_source(r):
    stacks = r['A'].get('xsltStacks', []) + [s for f in r['A'].get('frames', []) for s in f.get('xsltStacks', [])]
    for s in stacks:
        urls = re.findall(r'(https?://[^\s)]+?):\d+:\d+', s)
        if urls:
            return re.sub(r'\?.*', '', urls[0])
    return ''


def auto(r):
    A, A2, B = r['A'], r['A2'], r['B']
    if A.get('error') or B.get('error') or A2.get('error'):
        return 'not assessable', 'load error'
    if (A.get('status') or 200) >= 400:
        return 'not assessable', f"HTTP {A['status']}"
    if A.get('xmlViewer'):
        return 'not assessable', 'XSLT not applied even when on'
    if r['textRatioAB'] >= min(r['textRatioAA2'], 0.98) and (r['pixAB'] or 0) <= max((r['pixAA2'] or 0) * 1.5, 0.01):
        return 'no visible change', 'A vs B within A vs A2 noise'
    if B.get('xmlViewer'):
        u = (r['page'] + ' ' + A.get('title', '') + ' ' + A.get('text', '')[:300]).lower()
        if re.search(r'sitemap|rss|feed|atom|oai|backend|web feed|kanał', u):
            return 'worse', 'machine-readable resource shown as raw XML'
        return '', 'raw XML; needs review'
    return '', 'differs; needs review'


os.makedirs(f'{out_dir}/review', exist_ok=True)
with open(f'{out_dir}/auto.csv', 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['idx', 'stratum', 'page', 'auto_rating', 'reason', 'textRatioAA2', 'textRatioAB', 'pixAA2', 'pixAB', 'xslt_source', 'b_errors'])
    for r in rows:
        rating, reason = auto(r)
        w.writerow([r['idx'], r['stratum'], r['page'], rating, reason, r['textRatioAA2'], r['textRatioAB'], r['pixAA2'], r['pixAB'],
                    xslt_source(r), ' | '.join(e[:100] for e in r['B'].get('pageErrors', [])[:2])])
        if rating:
            continue
        a, b = Image.open(r['A']['shot']), Image.open(r['B']['shot'])
        h = min(1100, max(a.height, b.height))
        im = Image.new('RGB', (a.width + b.width + 12, h), 'red')
        im.paste(a.crop((0, 0, a.width, min(h, a.height))), (0, 0))
        im.paste(b.crop((0, 0, b.width, min(h, b.height))), (a.width + 12, 0))
        im.thumbnail((1500, 1100))
        im.save(f"{out_dir}/review/{r['idx']:03}.png")
