-- queries.sql
-- Eight analytical queries over the Lending Club star schema.
--
-- Every query is self-contained and runnable against lending_club.db:
--     sqlite3 lending_club.db < queries.sql
--
-- The techniques are labelled on each one, because that is the point of the
-- repository: multi-table joins, aggregate filtering, window functions,
-- CTEs and conditional aggregation, each answering a question a credit-risk
-- analyst would actually ask.

PRAGMA foreign_keys = ON;


-- ===========================================================================
-- Q1  Default rate by census region and loan purpose
--     Technique: three-table INNER JOIN, GROUP BY, HAVING on a volume floor
--
--     The question: which region and purpose combinations actually carry
--     risk, and which ones only look risky because the sample is tiny?
--     The HAVING clause is what stops a 40-loan category from topping the
--     table on noise alone.
-- ===========================================================================
SELECT
    s.census_region,
    p.purpose_name,
    COUNT(*)                                          AS loans,
    ROUND(SUM(f.loan_amount) / 1e6, 1)                AS total_loan_millions,
    ROUND(100.0 * AVG(f.default_flag), 2)             AS default_rate_pct
FROM fact_loan       AS f
JOIN dim_state       AS s ON s.state_code  = f.state_code
JOIN dim_purpose     AS p ON p.purpose_id  = f.purpose_id
GROUP BY s.census_region, p.purpose_name
HAVING COUNT(*) >= 10000
ORDER BY default_rate_pct DESC, loans DESC;


-- ===========================================================================
-- Q2  What the missing employment-length answers hide
--     Technique: LEFT JOIN, IS NULL anti-join semantics, COALESCE
--
--     "NI" means the borrower did not state an employment length. It is a
--     missing answer, not a short tenure. Treating it as zero would quietly
--     bias every employment-based cut, so the dimension keeps its bounds
--     NULL and this query measures the exposure.
-- ===========================================================================
SELECT
    COALESCE(e.emp_length_label, 'no dimension row')  AS emp_length,
    COUNT(*)                                          AS loans,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM fact_loan), 2) AS pct_of_portfolio,
    ROUND(100.0 * AVG(f.default_flag), 2)             AS default_rate_pct
FROM fact_loan AS f
LEFT JOIN dim_emp_length AS e ON e.emp_length_id = f.emp_length_id
GROUP BY e.emp_length_label
ORDER BY loans DESC;


-- ===========================================================================
-- Q3  Purposes whose default rate beats the portfolio average
--     Technique: scalar subquery in HAVING, GROUP BY with two conditions
--
--     The comparison value is computed from the table itself rather than
--     typed in, so the query stays correct if the dataset changes.
-- ===========================================================================
SELECT
    p.purpose_name,
    COUNT(*)                              AS loans,
    ROUND(100.0 * AVG(f.default_flag), 2) AS default_rate_pct,
    ROUND(100.0 * AVG(f.default_flag)
          - (SELECT 100.0 * AVG(default_flag) FROM fact_loan), 2) AS pts_vs_portfolio
FROM fact_loan   AS f
JOIN dim_purpose AS p ON p.purpose_id = f.purpose_id
GROUP BY p.purpose_name
HAVING COUNT(*) >= 5000
   AND AVG(f.default_flag) > (SELECT AVG(default_flag) FROM fact_loan)
ORDER BY default_rate_pct DESC;


-- ===========================================================================
-- Q4  Rank states by default rate inside their own region
--     Technique: window function RANK() OVER (PARTITION BY ... ORDER BY ...)
--
--     A national ranking is misleading because regional loan volumes and
--     underwriting differ. Partitioning by region compares like with like.
--     RANK rather than ROW_NUMBER because ties should share a position.
-- ===========================================================================
WITH state_rates AS (
    SELECT
        s.census_region,
        s.state_code,
        COUNT(*)                    AS loans,
        AVG(f.default_flag) AS default_rate   -- exact; rounding is display only
    FROM fact_loan AS f
    JOIN dim_state AS s ON s.state_code = f.state_code
    GROUP BY s.census_region, s.state_code
    HAVING COUNT(*) >= 1000
)
SELECT
    census_region,
    state_code,
    loans,
    ROUND(100.0 * default_rate, 2) AS default_rate_pct,
    RANK() OVER (PARTITION BY census_region ORDER BY default_rate DESC) AS rank_in_region
FROM state_rates
ORDER BY census_region, rank_in_region;


-- ===========================================================================
-- Q5  Monthly originations with a cumulative total and running share
--     Technique: window SUM() OVER (ORDER BY ... ROWS UNBOUNDED PRECEDING)
--
--     Answers "how did volume build, and when had we written half the book".
--     A self-join could do this, but a window function says it in one pass.
-- ===========================================================================
WITH monthly AS (
    SELECT
        issue_date,
        COUNT(*)                  AS loans,
        SUM(loan_amount) / 1e6    AS loan_millions
    FROM fact_loan
    GROUP BY issue_date
)
SELECT
    issue_date,
    loans,
    ROUND(loan_millions, 1)                                        AS loan_millions,
    SUM(loans) OVER (ORDER BY issue_date ROWS UNBOUNDED PRECEDING) AS cumulative_loans,
    ROUND(100.0 * SUM(loans) OVER (ORDER BY issue_date ROWS UNBOUNDED PRECEDING)
          / SUM(loans) OVER (), 1)                                 AS cumulative_pct
FROM monthly
ORDER BY issue_date;


-- ===========================================================================
-- Q6  Three-month moving average of the default rate
--     Technique: window AVG() over a sliding frame, LAG for month-over-month
--
--     Raw monthly default rates are noisy because vintages are still
--     resolving. The moving average shows the trend; LAG shows the direction.
--     Note the censoring: late vintages have not had time to default, which
--     is why the series falls away at the end and must not be read as
--     improving credit quality.
-- ===========================================================================
WITH monthly AS (
    SELECT
        issue_date,
        COUNT(*)                    AS loans,
        AVG(default_flag) AS default_rate   -- exact; rounding is display only
    FROM fact_loan
    GROUP BY issue_date
)
SELECT
    issue_date,
    loans,
    ROUND(100.0 * default_rate, 2) AS default_rate_pct,
    ROUND(100.0 * AVG(default_rate) OVER (
        ORDER BY issue_date ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
    ), 2) AS moving_avg_3m,
    ROUND(100.0 * (default_rate
          - LAG(default_rate) OVER (ORDER BY issue_date)), 2) AS change_vs_prev_month
FROM monthly
ORDER BY issue_date;


-- ===========================================================================
-- Q7  Top three purposes by volume in each region, with share of that region
--     Technique: CTE, ROW_NUMBER() partitioned, window SUM() for the share
--
--     "Top N per group" is the classic window-function question. Filtering
--     happens outside the CTE because a window function cannot appear in
--     WHERE in the same SELECT level.
-- ===========================================================================
WITH region_purpose AS (
    SELECT
        s.census_region,
        p.purpose_name,
        COUNT(*)                     AS loans,
        SUM(COUNT(*)) OVER (PARTITION BY s.census_region) AS region_total
    FROM fact_loan   AS f
    JOIN dim_state   AS s ON s.state_code = f.state_code
    JOIN dim_purpose AS p ON p.purpose_id = f.purpose_id
    GROUP BY s.census_region, p.purpose_name
),
ranked AS (
    SELECT
        region_purpose.*,
        ROW_NUMBER() OVER (PARTITION BY census_region ORDER BY loans DESC) AS rn
    FROM region_purpose
)
SELECT
    census_region,
    rn                                                    AS position,
    purpose_name,
    loans,
    ROUND(100.0 * loans / region_total, 1)                AS pct_of_region
FROM ranked
WHERE rn <= 3
ORDER BY census_region, position;


-- ===========================================================================
-- Q8  Default rate by FICO band crossed with home ownership
--     Technique: CTE, CASE bucketing, conditional aggregation as a pivot
--
--     SQLite has no PIVOT keyword, so the pivot is built with SUM(CASE ...).
--     This is the query that should reproduce the Power BI dashboard's
--     risk-segment page: 25.30 / 21.45 / 17.30 / 13.81 / 11.15 / 8.32 by
--     ascending FICO band, over 1,347,681 loans.
-- ===========================================================================
WITH banded AS (
    SELECT
        CASE
            WHEN fico IS NULL THEN 'unknown'
            WHEN fico <  680  THEN '1. < 680'
            WHEN fico <  700  THEN '2. 680-699'
            WHEN fico <  720  THEN '3. 700-719'
            WHEN fico <  740  THEN '4. 720-739'
            WHEN fico <  760  THEN '5. 740-759'
            ELSE                   '6. 760+'
        END AS fico_band,
        home_ownership,
        default_flag
    FROM fact_loan
)
SELECT
    fico_band,
    COUNT(*)                                                AS loans,
    ROUND(100.0 * AVG(default_flag), 2)                     AS default_rate_pct,
    ROUND(100.0 * SUM(CASE WHEN home_ownership = 'MORTGAGE' THEN default_flag END)
          / NULLIF(SUM(CASE WHEN home_ownership = 'MORTGAGE' THEN 1 END), 0), 2) AS rate_mortgage,
    ROUND(100.0 * SUM(CASE WHEN home_ownership = 'RENT'     THEN default_flag END)
          / NULLIF(SUM(CASE WHEN home_ownership = 'RENT'     THEN 1 END), 0), 2) AS rate_rent,
    ROUND(100.0 * SUM(CASE WHEN home_ownership = 'OWN'      THEN default_flag END)
          / NULLIF(SUM(CASE WHEN home_ownership = 'OWN'      THEN 1 END), 0), 2) AS rate_own
FROM banded
GROUP BY fico_band
ORDER BY fico_band;
