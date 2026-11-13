WITH Counts AS (SELECT issue_date, COUNT(*) AS loanCount FROM fact_loan GROUP BY issue_date)
SELECT issue_date, loanCount, SUM(loanCount) OVER(ORDER BY issue_date ROWS UNBOUNDED PRECEDING) AS CumulativeLoans
FROM Counts
ORDER BY issue_date