SELECT loan_id, issue_date, loan_amount, fico FROM fact_loan
WHERE (issue_year=2017) AND (default_flag=1) AND (loan_amount>20000)
ORDER BY loan_amount DESC, loan_id
LIMIT 10