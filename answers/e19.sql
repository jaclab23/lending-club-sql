WITH defCTE AS (SELECT issue_date, ROUND(AVG(default_flag*100.0),2) AS DefaultRate FROM fact_loan GROUP BY issue_date)
SELECT issue_date, DefaultRate, DefaultRate-(LAG(DefaultRate) OVER(ORDER BY issue_date)) AS MoMChange
FROM defCTE
ORDER BY issue_date