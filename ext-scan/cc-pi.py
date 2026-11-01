# Usage: cc-pi.py <warc>...  Counts xml-stylesheet PIs in the prolog of every response (any content type).
import collections, multiprocessing, re, sys
from warcio.archiveiterator import ArchiveIterator
PI = re.compile(rb'<\?xml-stylesheet\s([^?]*(?:\?(?!>)[^?]*)*)\?>')
ATTR = re.compile(rb'(\w+)\s*=\s*(["\'])(.*?)\2', re.S)
def scan(path):
    c = collections.Counter(); ex = {}
    with open(path, 'rb') as f:
        for rec in ArchiveIterator(f):
            if rec.rec_type != 'response': continue
            body = rec.content_stream().read(8192)
            head = body.split(b'<', 1)
            if b'<?xml-stylesheet' not in body: continue
            # Prolog: up to the first element start tag.
            m = re.search(rb'<(?![?!])', body)
            prolog = body[:m.start()] if m else body
            pis = PI.findall(prolog)
            if not pis: continue
            c['docs'] += 1
            ct = (rec.http_headers.get_header('Content-Type') or '').split(';')[0].strip().lower()
            c['ct:' + ct] += 1
            xslt_like = 0
            for p in pis:
                a = {k.lower(): v for k, v, in ((k, v) for k, _, v in ATTR.findall(p))}
                t = a.get(b'type', b'<missing>').decode('latin-1')
                c['type:' + t] += 1
                ex.setdefault('type:' + t, rec.rec_headers.get_header('WARC-Target-URI'))
                if b'alternate' in a: c['alternate:' + a[b'alternate'].decode('latin-1')] += 1; ex.setdefault('alternate', rec.rec_headers.get_header('WARC-Target-URI'))
            if len(pis) > 1:
                c['multi'] += 1; ex.setdefault('multi', rec.rec_headers.get_header('WARC-Target-URI'))
                c['multi:' + ' + '.join(sorted({ {k.lower(): v for k, _, v in ATTR.findall(p)}.get(b'type', b'?').decode('latin-1') for p in pis}))] += 1
    return c, ex
if __name__ == '__main__':
    tot = collections.Counter(); exs = {}
    with multiprocessing.Pool(6) as pool:
        for c, ex in pool.imap_unordered(scan, sys.argv[1:]):
            tot.update(c); [exs.setdefault(k, v) for k, v in ex.items()]
    for k, v in sorted(tot.items(), key=lambda kv: (-kv[1], kv[0])): print(v, k, exs.get(k, ''))
