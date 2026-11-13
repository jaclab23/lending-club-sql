SELECT census_region, COUNT(loan_id) As Count, ROUND(AVG(default_flag*100.0),2) AS DefaultRate
from fact_loan AS f INNER JOIN dim_state AS s ON f.state_code=s.state_code
GROUP BY census_region
ORDER BY DefaultRate DESC