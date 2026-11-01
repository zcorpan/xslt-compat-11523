# Fetches each page (raw, no browser) and records the xml-stylesheet PIs in its prolog and whether it
# contains a <script> element. Usage: live.py <pages.jsonl> <out.jsonl>
import concurrent.futures, json, re, ssl, sys, urllib.request
PI = re.compile(r'<\?xml-stylesheet\s(.*?)\?>', re.S)
ATTR = re.compile(r'(\w+)\s*=\s*(["\'])(.*?)\2', re.S)
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/158.0.0.0 Safari/537.36'
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
urls = sorted({json.loads(l)['page'] for l in open(sys.argv[1])})
def get(u):
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': UA}), timeout=15, context=ctx) as r:
            body = r.read(200000).decode('latin-1')
    except Exception as e:
        return {'page': u, 'error': type(e).__name__}
    m = re.search(r'<(?![?!])', body)
    prolog = body[:m.start()] if m else body
    return {'page': u, 'pis': [{k.lower(): v for k, _, v in ATTR.findall(p)} for p in PI.findall(prolog)],
            'hasScript': bool(re.search(r'<(\w+:)?script\b', body))}
with concurrent.futures.ThreadPoolExecutor(12) as pool, open(sys.argv[2], 'w') as out:
    for rec in pool.map(get, urls):
        out.write(json.dumps(rec) + '\n')
