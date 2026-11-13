SELECT home_ownership, COUNT(loan_id) AS Count, ROUND(AVG(default_flag)*100.0,2) AS DefaultRate
FROM fact_loan
GROUP BY home_ownership
ORDER BY DefaultRate DESC