WITH perState AS (SELECT s.state_code, census_region, ROUND(AVG(default_flag*100.0),2) AS DefaultRate, COUNT(*) AS loans FROM dim_state s JOIN fact_loan f ON s.state_code=f.state_code GROUP BY s.state_code,s.census_region)
SELECT census_region, state_code, loans, DefaultRate, RANK() OVER (PARTITION BY census_region ORDER BY DefaultRate DESC) AS rank
FROM perState 
ORDER BY census_region, rank