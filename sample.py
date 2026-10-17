# Draws a seeded random sample of 50 pages per counter and client from the hits query output.
# Usage: sample.py hits.csv sample.jsonl
import csv, hashlib, json, sys
rows = list(csv.DictReader(open(sys.argv[1])))
seed = 'xslt-2026'
out = []
for counter in ('78', '79'):
    for client in ('desktop', 'mobile'):
        stratum = [r for r in rows if r['counters'] == counter and r['client'] == client]
        stratum.sort(key=lambda r: hashlib.sha256((r['page'] + seed).encode()).hexdigest())
        for r in stratum[:50]:
            out.append({**r, 'stratum': f'{counter}-{client}', 'stratum_size': len(stratum)})
with open(sys.argv[2], 'w') as f:
    for r in out:
        f.write(json.dumps(r) + '\n')
print(len(out))
