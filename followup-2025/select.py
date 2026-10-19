# Lists the pages rated broken in the August 2025 analysis (sheet-2025.csv, exported from the
# spreadsheet linked in whatwg/html#11523) and whether they hit the counters in the 2026-09-01 crawl.
# Usage: select.py sheet-2025.csv ../hits.csv broken-2025.csv
import csv, sys
sheet, hits, out = sys.argv[1:4]
seen = {}
for h in csv.DictReader(open(hits)):
    seen.setdefault(h['page'], set()).add(f"{h['client']}:{h['counters']}")
with open(out, 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['page', 'rank', 'in2026', 'notes'])
    for r in csv.DictReader(open(sheet)):
        if r['Would essential/main functionality be broken without XSLT?'] == 'Yes':
            w.writerow([r['page'], r['rank'], ' '.join(sorted(seen.get(r['page'], []))), r['Notes']])
