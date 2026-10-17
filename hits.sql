SELECT
  client,
  is_root_page,
  rank,
  page,
  ARRAY_TO_STRING(ARRAY(SELECT DISTINCT f.id FROM UNNEST(features) f WHERE f.type = 'default' AND f.id IN ('78', '79', '5777', '5778') ORDER BY f.id), ' ') AS counters
FROM `httparchive.crawl.pages`
WHERE date = '2026-09-01'
  AND EXISTS(SELECT 1 FROM UNNEST(features) f WHERE f.type = 'default' AND f.id IN ('78', '79', '5777', '5778'))
