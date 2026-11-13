WITH PurpRate AS (SELECT d.purpose_id, purpose_name, COUNT(*) AS Count, AVG(loan_amount) AS AvgAmnt
FROM fact_loan AS f INNER JOIN dim_purpose AS d ON f.purpose_id=d.purpose_id
GROUP BY f.purpose_id)
SELECT purpose_name, COUNT(*) AS Counts
FROM fact_loan AS f INNER JOIN PurpRate p ON f.purpose_id=p.purpose_id
WHERE loan_amount>AvgAmnt
GROUP BY purpose_name
ORDER BY Counts DESC, purpose_name