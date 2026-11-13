SELECT issue_year, COUNT(loan_id) AS Count, ROUND(AVG(loan_amount),2) AS AverageLoan
FROM fact_loan
GROUP BY issue_year
ORDER BY issue_year