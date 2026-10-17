# Extrapolates the reviewed ratings to each stratum, with exact binomial (Clopper-Pearson) 95% intervals.
# Usage: extrapolate.py <out-dir>/review.csv sample.jsonl
import collections, csv, json, math, sys

reviews = list(csv.DictReader(open(sys.argv[1])))
sizes = {}
for l in open(sys.argv[2]):
    r = json.loads(l)
    sizes[r['stratum']] = r['stratum_size']
RATINGS = ['broken', 'worse', 'no visible change', 'not assessable']


def beta_cdf(x, a, b, steps=4000):
    norm = math.exp(math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b))
    total = 0.0
    for k in range(steps):
        t = (k + 0.5) / steps * x
        total += math.exp((a - 1) * math.log(t) + (b - 1) * math.log(1 - t))
    return total * x / steps / norm


def beta_ppf(p, a, b):
    lo, hi = 0.0, 1.0
    for _ in range(50):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if beta_cdf(mid, a, b) < p else (lo, mid)
    return lo


def clopper_pearson(k, n):
    lo = 0.0 if k == 0 else beta_ppf(0.025, k, n - k + 1)
    hi = 1.0 if k == n else beta_ppf(0.975, k + 1, n - k)
    return lo, hi


print('| Stratum | Pages hit | Sampled | ' + ' | '.join(r.capitalize() for r in RATINGS) + ' |')
print('|---|---|---|' + '---|' * len(RATINGS))
totals = collections.defaultdict(lambda: [0.0, 0.0, 0.0])
for stratum in sorted(sizes):
    rs = [r for r in reviews if r['stratum'] == stratum]
    n, N = len(rs), sizes[stratum]
    counts = collections.Counter(r['rating'] for r in rs)
    cells = []
    for rating in RATINGS:
        k = counts[rating]
        lo, hi = clopper_pearson(k, n)
        cells.append(f'{k} (~{k / n * N:.0f}, {lo * N:.0f}–{hi * N:.0f})')
        t = totals[(stratum.split('-')[0], rating)]
        t[0] += k / n * N
        t[1] += lo * N
        t[2] += hi * N
    print(f'| {stratum} | {N} | {n} | ' + ' | '.join(cells) + ' |')
print()
print('| Counter | ' + ' | '.join(r.capitalize() for r in RATINGS) + ' |')
print('|---|' + '---|' * len(RATINGS))
for counter in sorted({s.split('-')[0] for s in sizes}):
    print(f'| {counter} | ' + ' | '.join(
        '~{:.0f} ({:.0f}–{:.0f})'.format(*totals[(counter, r)]) for r in RATINGS) + ' |')
