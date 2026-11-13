WITH counts AS (SELECT census_region, purpose_id, COUNT(*) AS loan_count FROM fact_loan AS f JOIN dim_state AS d ON f.state_code=d.state_code GROUP BY census_region, purpose_id),
rankings AS (SELECT census_region, purpose_id, loan_count, ROW_NUMBER() OVER (PARTITION BY census_region ORDER BY loan_count DESC) AS rn FROM counts)
SELECT census_region, rn, purpose_name, loan_count
FROM rankings as r JOIN dim_purpose AS p ON r.purpose_id=p.purpose_id
WHERE rn <=3
ORDER BY census_region, rn