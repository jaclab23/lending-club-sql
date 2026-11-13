SELECT purpose_name, COUNT(*) AS Count, ROUND(AVG(default_flag*100.0),2) AS DefaultRate
FROM fact_loan AS f INNER JOIN dim_purpose AS p ON f.purpose_id = p.purpose_id
GROUP BY purpose_name 
HAVING (COUNT(*) > 50000) AND (AVG(default_flag*100.0)>20)
ORDER BY DefaultRate DESC