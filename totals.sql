SELECT client, is_root_page, COUNT(*) AS pages
FROM `httparchive.crawl.pages`
WHERE date = '2026-09-01'
GROUP BY client, is_root_page
ORDER BY client, is_root_page
