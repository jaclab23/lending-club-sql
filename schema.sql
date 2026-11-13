-- schema.sql
-- Star schema over the Lending Club loan extract (2007-2018).
-- One fact table at loan grain, three conformed dimensions.
--
-- Load order matters: dimensions first, then the fact table, so the
-- foreign keys resolve. build_db.py does this in one transaction.

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- Dimension: US states
-- state_name and census_region are US Census Bureau reference data, not
-- loan data. Every state_code here also appears in the source file; the
-- loader only inserts codes it actually saw, so the dimension never claims
-- coverage the data does not have.
-- ---------------------------------------------------------------------------
CREATE TABLE dim_state (
    state_code    TEXT PRIMARY KEY,
    state_name    TEXT NOT NULL,
    census_region TEXT NOT NULL CHECK (census_region IN ('Northeast', 'Midwest', 'South', 'West'))
);

-- ---------------------------------------------------------------------------
-- Dimension: loan purpose, as recorded by Lending Club.
-- Populated from the distinct values in the source file rather than a
-- hardcoded list, so the dimension cannot drift from the fact table.
-- ---------------------------------------------------------------------------
CREATE TABLE dim_purpose (
    purpose_id   INTEGER PRIMARY KEY,
    purpose_name TEXT NOT NULL UNIQUE
);

-- ---------------------------------------------------------------------------
-- Dimension: employment length.
-- The source stores this as text ("10+ years", "< 1 year", "NI"). The band
-- boundaries are what make it sortable and joinable; keeping the raw label
-- keeps it traceable back to the source.
-- years_min / years_max are NULL for "NI" (not indicated) - absence of a
-- value, not a zero.
-- ---------------------------------------------------------------------------
CREATE TABLE dim_emp_length (
    emp_length_id    INTEGER PRIMARY KEY,
    emp_length_label TEXT NOT NULL UNIQUE,
    years_min        INTEGER,
    years_max        INTEGER,
    CHECK ((years_min IS NULL AND years_max IS NULL)
        OR (years_min IS NOT NULL AND years_max IS NOT NULL AND years_min <= years_max))
);

-- ---------------------------------------------------------------------------
-- Fact: one row per loan.
-- ---------------------------------------------------------------------------
CREATE TABLE fact_loan (
    loan_id        INTEGER PRIMARY KEY,
    issue_date     TEXT    NOT NULL,   -- ISO 8601, first of month: YYYY-MM-01
    issue_year     INTEGER NOT NULL,
    loan_amount    REAL    NOT NULL CHECK (loan_amount > 0),
    annual_income  REAL,
    dti            REAL,               -- debt-to-income, percent
    fico           INTEGER,            -- FICO score at origination
    home_ownership TEXT    NOT NULL CHECK (home_ownership IN ('MORTGAGE', 'RENT', 'OWN', 'OTHER')),
    purpose_id     INTEGER NOT NULL REFERENCES dim_purpose(purpose_id),
    state_code     TEXT    NOT NULL REFERENCES dim_state(state_code),
    emp_length_id  INTEGER          REFERENCES dim_emp_length(emp_length_id),
    default_flag   INTEGER NOT NULL CHECK (default_flag IN (0, 1))
);

-- Indexes chosen for the queries in queries.sql: every one of them filters
-- or groups by year, state or purpose.
CREATE INDEX idx_loan_year     ON fact_loan(issue_year);
CREATE INDEX idx_loan_state    ON fact_loan(state_code);
CREATE INDEX idx_loan_purpose  ON fact_loan(purpose_id);
CREATE INDEX idx_loan_fico     ON fact_loan(fico);
