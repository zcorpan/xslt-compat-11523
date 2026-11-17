# Prints a Markdown table of ratings per page across every <crawl date>/review.csv, plus counts.
# Usage: report.py
import collections, csv, glob, os

HERE = os.path.dirname(os.path.abspath(__file__))
months = sorted(os.path.basename(os.path.dirname(p)) for p in glob.glob(f'{HERE}/????-??-??/review.csv'))
ratings = {m: {r['page']: r['rating'] for r in csv.DictReader(open(f'{HERE}/{m}/review.csv'))} for m in months}
pages = sorted({p for m in months for p in ratings[m]})
print('| Page | ' + ' | '.join(months) + ' |')
print('|---|' + '---|' * len(months))
for p in pages:
    print(f'| {p} | ' + ' | '.join(ratings[m].get(p, '') for m in months) + ' |')
print()
for m in months:
    c = collections.Counter(ratings[m].values())
    print(f'{m}: {len(ratings[m])} pages: ' + ', '.join(f'{n} {k}' for k, n in c.most_common()))
