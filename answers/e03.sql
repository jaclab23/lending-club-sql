SELECT state_code, COUNT(loan_id) AS Count
FROM fact_loan
GROUP BY state_code
ORDER BY Count DESC, state_code
LIMIT 10