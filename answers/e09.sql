SELECT s.state_code
FROM dim_state AS s LEFT JOIN fact_loan f ON s.state_code=f.state_code
WHERE f.state_code IS NULL