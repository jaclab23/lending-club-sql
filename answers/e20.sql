WITH PurpRate AS (SELECT purpose_name, COUNT(*) AS loans, AVG(default_flag*100.0) AS DefaultRate
FROM fact_loan AS f INNER JOIN dim_purpose AS d ON f.purpose_id=d.purpose_id
GROUP BY purpose_name
HAVING COUNT(*)>10000)
SELECT purpose_name, loans, DefaultRate
FROM PurpRate
ORDER BY DefaultRate DESC
LIMIT 1 OFFSET 1