# Prints the counts cited in the issues from the files in this directory.
# Usage: summarize.py <ext-scan-dir>
import collections, json, os, re, sys
d = sys.argv[1]
load = lambda f: [json.loads(l) for l in open(os.path.join(d, f))]

live = load('live.jsonl')
with_pi = [r for r in live if r.get('pis')]
types = collections.Counter(p.get('type', '<missing>') for r in with_pi for p in r['pis'])
xslt = [r for r in with_pi if any(p.get('type', '').lower() in ('text/xsl', 'text/xml', 'application/xml', 'application/xslt+xml') for p in r['pis'])]
print(f"live.jsonl: {len(live)} URLs, {sum('error' in r for r in live)} fetch errors, {len(with_pi)} with a prolog xml-stylesheet PI")
print('  PI types:', dict(types))
print('  multiple PIs:', collections.Counter(' + '.join(p.get('type', '?') for p in r['pis']) for r in with_pi if len(r['pis']) > 1))
print('  alternate:', sum('alternate' in p for r in with_pi for p in r['pis']))
print(f"  {len(xslt)} with an XSLT PI, {sum(r['hasScript'] for r in xslt)} containing <script>:", [r['page'] for r in xslt if r['hasScript']])

def docs(f):
    out = {}
    for r in load(f):
        for fr in r.get('xsltFrames', []):
            out.setdefault(fr['url'].split('?')[0], []).append(fr)
    return out
UP = re.compile(r'(?:^|[\s>+~(])[A-Za-z]*[A-Z][A-Za-z0-9]*|\[\s*[A-Za-z-]*[A-Z]')
case = docs('case.jsonl')
sel = sorted(u for u, frs in case.items() if any(n and n > 0 for fr in frs for _, n in fr.get('upperSelectors', [])))
dom = sorted(u for u, frs in case.items() for fr in frs for e in fr.get('log', [])
             if e['result'] not in (None, 0, False) and (e['api'] not in ('querySelector', 'querySelectorAll', 'matches', 'closest') or UP.search(e['arg'])))
print(f"\ncase.jsonl: {len(case)} XSLT-produced documents; uppercase selectors that match: {sel}; case-dependent DOM calls: {sorted(set(dom))}")

reset = {u: frs[0] for u, frs in docs('reset.jsonl').items()}
print(f"\nreset.jsonl: {len(reset)} XSLT-produced documents")
for label, test in [('tables', lambda f: f['tables'] > 0), ('tables inheriting a non-default font-family', lambda f: f['tablesInheritFont'] > 0),
                    ('tables inheriting a non-16px font-size', lambda f: f['tablesInheritFontSize'] > 0),
                    ('cells relying on the default middle', lambda f: f['tdMiddle'] > 0), ('cells with valign', lambda f: f['tdValign'] > 0),
                    ('body margin attributes', lambda f: bool(f['bodyMarginAttrs'])), ('tables in white-space: pre', lambda f: f['tablesInPre'] > 0)]:
    print(f'  {sum(map(test, reset.values()))} {label}')

write = docs('write.jsonl')
print(f"\nwrite.jsonl: {len(write)} XSLT-produced documents, {sum(any(e['api'] in ('write', 'writeln') for fr in frs for e in fr.get('log', [])) for frs in write.values())} calling document.write/writeln")
