WITH PurpRate AS (SELECT purpose_name, COUNT(*) AS Count, AVG(default_flag*100.0) AS DefaultRate
FROM fact_loan AS f INNER JOIN dim_purpose AS d ON f.purpose_id=d.purpose_id
GROUP BY purpose_name),
PortRate AS (SELECT AVG(default_flag*100.0) AS DefaultRatePort FROM fact_loan)
SELECT purpose_name, Count, ROUND(DefaultRate,2)
FROM PurpRate CROSS JOIN PortRate
WHERE DefaultRate>DefaultRatePort
ORDER BY DefaultRate DESC