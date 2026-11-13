-- Q1
SELECT census_region, purpose_name, COUNT(*) AS loans, ROUND(SUM(loan_amount)/1000000,1) AS total_loan_millions, ROUND(AVG(default_flag*100.0),2) AS default_rate_pct
FROM dim_state AS s JOIN fact_loan AS f ON s.state_code=f.state_code JOIN dim_purpose AS p ON p.purpose_id=f.purpose_id
GROUP BY census_region, purpose_name
HAVING COUNT(*)>=10000
ORDER BY default_rate_pct DESC, loans DESC;

-- Q2
SELECT emp_length_label AS emp_length, COUNT(*) AS loans, ROUND((COUNT(*)*100.0)/(SELECT COUNT(*) FROM fact_loan),2) AS pct_of_portfolio,ROUND(AVG(default_flag*100.0),2) AS default_rate_pct
from fact_loan AS f JOIN dim_emp_length AS e ON f.emp_length_id=e.emp_length_id
GROUP BY emp_length_label
ORDER BY COUNT(*) DESC;

-- Q3
WITH avgdefcte AS (SELECT AVG(default_flag*100.0) AS defavg FROM fact_loan)
SELECT purpose_name, COUNT(*) AS loans, ROUND(AVG(default_flag*100.0),2) AS default_rate_pct, ROUND(AVG(default_flag*100.0)-defavg,2) AS pts_vs_portfolio
FROM fact_loan AS f INNER JOIN dim_purpose AS d ON f.purpose_id=d.purpose_id CROSS JOIN avgdefcte
GROUP BY purpose_name
HAVING (AVG(default_flag*100.0)>defavg) AND (COUNT(*)>5000)
ORDER BY default_rate_pct DESC;

-- Q4 
WITH perState AS (SELECT s.state_code, census_region, AVG(default_flag*100.0) AS default_rate, COUNT(*) AS loans FROM dim_state s JOIN fact_loan f ON s.state_code=f.state_code GROUP BY s.state_code,s.census_region)
SELECT census_region, state_code, loans, ROUND(default_rate,2) AS default_rate_pct, RANK() OVER (PARTITION BY census_region ORDER BY default_rate DESC) AS rank_in_region
FROM perState 
WHERE loans>1000
ORDER BY census_region, rank_in_region;

-- Q5
WITH Counts AS (SELECT issue_date, COUNT(*) AS loans, SUM(COUNT(*)) OVER(ORDER BY issue_date ROWS UNBOUNDED PRECEDING) AS cumulative_loans, ROUND(SUM(loan_amount)/1000000,1) AS loan_millions FROM fact_loan GROUP BY issue_date)
SELECT issue_date, loans, loan_millions, cumulative_loans, ROUND(SUM(loans) OVER(ORDER BY issue_date ROWS UNBOUNDED PRECEDING)*100.0/SUM(loans) OVER(),1) AS cumulative_pct
FROM Counts 
ORDER BY issue_date;

-- Q6
WITH defCTE AS (SELECT issue_date, COUNT(*) as loans, AVG(default_flag*100.0) AS default_rate_pct FROM fact_loan GROUP BY issue_date)
SELECT issue_date, loans,ROUND(default_rate_pct,2) AS default_rate_pct, ROUND(AVG(default_rate_pct) OVER(ORDER BY issue_date ROWS BETWEEN 2 PRECEDING AND CURRENT ROW),2) AS moving_avg_3m, ROUND(default_rate_pct-(LAG(default_rate_pct) OVER(ORDER BY issue_date)),2) AS change_vs_prev_month
FROM defCTE
ORDER BY issue_date;

-- Q7
WITH counts AS (SELECT census_region, purpose_id, COUNT(*) AS loans FROM fact_loan AS f JOIN dim_state AS d ON f.state_code=d.state_code GROUP BY census_region, purpose_id),
rankings AS (SELECT census_region, purpose_id, loans, RANK() OVER (PARTITION BY census_region ORDER BY loans DESC) AS position, loans*100.0/(SUM(loans) OVER (PARTITION BY census_region)) AS pct_of_region FROM counts)
SELECT census_region, position, purpose_name, loans, ROUND(pct_of_region,1) AS pct_of_region
FROM rankings as r JOIN dim_purpose AS p ON r.purpose_id=p.purpose_id
WHERE position <=3
GROUP BY census_region, position
ORDER BY census_region, position;

-- Q8
SELECT CASE 
	WHEN fico IS NULL THEN 'unknown'
	WHEN fico < 680 THEN '1. < 680'
	WHEN (fico <= 699) AND (fico>=680) THEN '2. 680-699'	
	WHEN (fico <= 719) AND (fico>=700) THEN '3. 700-719'
	WHEN (fico <= 739) AND (fico>=720) THEN '4. 720-739'
	WHEN (fico <= 759) AND (fico>=740) THEN '5. 740-759'
	WHEN (fico>=760) THEN '6. 760+'
END AS fico_band, COUNT(*) AS loans, ROUND(AVG(default_flag*100.0),2) AS default_rate_pct, ROUND(100.0*AVG(CASE WHEN home_ownership = 'MORTGAGE' THEN default_flag END),2) AS rate_mortgage ,ROUND(100.0*AVG(CASE WHEN home_ownership = 'RENT' THEN default_flag END),2) AS rate_rent, ROUND(100.0*AVG(CASE WHEN home_ownership = 'OWN' THEN default_flag END),2) AS rate_own
FROM fact_loan
GROUP BY fico_band
ORDER BY fico_band;