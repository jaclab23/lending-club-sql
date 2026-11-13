SELECT purpose_name, COUNT(*) AS Count, ROUND(AVG(default_flag*100.0),2) AS DefaultRate
FROM fact_loan AS f INNER JOIN dim_purpose AS d ON f.purpose_id=d.purpose_id
GROUP BY purpose_name
HAVING AVG(default_flag*100.0)>(SELECT ROUND(AVG(default_flag*100.0),2) from fact_loan)
ORDER BY DefaultRate DESC