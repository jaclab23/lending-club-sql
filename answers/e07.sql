SELECT purpose_name, COUNT(loan_id), ROUND(AVG(default_flag*100.0),2) AS DefaultRate
FROM fact_loan AS f INNER JOIN dim_purpose AS p ON f.purpose_id=p.purpose_id
GROUP BY purpose_name
ORDER BY DefaultRate DESC