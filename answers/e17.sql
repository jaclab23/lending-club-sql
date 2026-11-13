WITH defCTE AS (SELECT issue_date, ROUND(AVG(default_flag*100.0),2) AS DefaultRate FROM fact_loan GROUP BY issue_date)
SELECT issue_date, DefaultRate, AVG(DefaultRate) OVER(ORDER BY issue_date ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) AS "3MAvg"
FROM defCTE
ORDER BY issue_date