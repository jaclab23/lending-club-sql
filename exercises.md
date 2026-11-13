# SQL exercises

Twenty exercises against the Lending Club database. The goal is not to finish
them, it is to be able to write them **from a blank file, without help**, in
front of an interviewer.

## How this works

You write the query. `check.py` tells you pass or fail. It does not tell you the
answer.

```bash
# one-time: build the database (about 40 seconds)
python build_db.py --source ..\lending-club\LC_loans_granting_model_dataset.csv --db lending_club.db

# your workflow, per exercise
mkdir answers                                  # once
notepad answers\e05.sql                        # write your query
python check.py --exercise 5 --file answers\e05.sql
```

A pass looks like:

```
Exercise 5: Default rate by home ownership
  PASS - 4 row(s), columns ['home_ownership', 'loans', 'default_rate_pct']
```

A fail tells you *what* is wrong, not the fix:

```
Exercise 5: Default rate by home ownership
  FAIL - exercise 5: Default rate by home ownership
    row count: got 4, expected 5
```

Then read the hint, think about it, try again. That loop is the whole method.

## What the checker actually checks

It compares **result sets, not code**. Your query runs, the reference runs, and
the rows are compared. It never looks at how you wrote it, so a CTE, a
subquery, a join and an `EXCEPT` can all pass the same exercise. Column aliases
are free; column *count* has to match. Row order is only checked where the
exercise says ordering is part of the answer.

Two consequences:

- A **float** is compared to two decimal places, so `19.98` and `19.980000001`
  are the same answer.
- Nothing in the checker knows whether you *understand* the query. Passing
  twenty exercises means your output is right, not that you could explain it.
  That is what rule 1 below is for.

Because output comparison alone can be gamed, three guards run on top of it.

**1. The query has to read the data.** Every exercise checks that your query
mentions the tables the answer comes from. `SELECT 19.98` returns the right
number without doing any work, and so does a query filtered to `WHERE 1 = 0`.

**2. Mutation test, where a lucky wrong answer would pass.** For exercises 2, 4
and 9, your query is re-run on a tiny four-row database where the answer is
different. A query that only looks right on the real data fails there:

| Exercise | The hole | The mutation test |
|---|---|---|
| 2 | the real answer is **0**, so `COUNT(fico)` under `WHERE fico IS NULL` matches (it is always 0) | the small dataset has one loan with no FICO score, so the answer is 1 |
| 4 | `SELECT 19.98 FROM fact_loan` returns the right number | the small dataset's rate is 25.00 |
| 9 | the answer is **0 rows**, so any query returning nothing matches | the small dataset has two orphaned states |

**3. The order has to be asked for.** Where the exercise specifies a row order,
your query needs a statement-level `ORDER BY`. Rows that *look* sorted were not
asked to be sorted, and SQL promises nothing about the order without one.
`ORDER BY` inside `OVER (...)` does not count: it sorts a window, not the
output.

So if you ever see `FAIL - your query never reads: fact_loan`, or a pass
followed by `FAIL ... not on a small test dataset`, that is a guard firing, not
the answer. It means your query produced the right-looking output without doing
the work.

You can prove the guards are still working at any time:

```bash
python check.py --guards     # every known cheat must be rejected
python check.py --selftest   # every reference query must still run
```

## Three rules

1. **Do not open `check.py`.** The answers are in it. Reading it skips the only
   part that transfers to an interview.
2. **Do not open `solutions/reference_queries.sql` until you have finished all
   twenty.** It holds a working set of queries for eight overlapping problems.
   Read it afterwards as a comparison, to see how someone else phrased the same
   idea.
3. **Do not use an AI to write the answers.** You will be asked to explain your
   own query out loud. There is no version of that where borrowed SQL helps.

## What goes where

| Folder | Whose | What |
|---|---|---|
| `answers/` | yours | one file per exercise, `e01.sql` through `e20.sql` |
| `queries.sql` | yours | your final eight-question analysis, written once the block is done |
| `solutions/` | reference | working answers, opened only after you finish |

The repo only becomes yours when `queries.sql` and `answers/` are files you
wrote. Until then it is scaffolding plus an answer key, and it should not go on
a CV.

## What you are learning

Not "SQL syntax". Four specific things, in this order:

| Block | Skill | Why it is asked in interviews |
|---|---|---|
| 1–3 | Filtering, grouping, joining | Every screen starts here |
| 4–5 | Filtering aggregates, subqueries, CTEs | Separates people who use SQL from people who understand it |
| 6 | Window functions | The single strongest differentiator at junior level |
| 7 | The classic puzzles | "Second-highest", "top-N per group", dedup |

## The schema, at a glance

One big table and three small lookup tables. Every join you write starts from one
of the three `FK` lines below.

```
dim_state (51)          dim_purpose (14)        dim_emp_length (12)
  state_code   PK         purpose_id  PK          emp_length_id PK
  state_name              purpose_name            emp_length_label
  census_region                                   years_min, years_max
        │                       │                       │
        └───────────┬───────────┴───────────────────────┘
                    ▼
              fact_loan  (1,347,681 rows)
                loan_id        PK
                issue_date, issue_year
                loan_amount, annual_income, dti, fico
                home_ownership
                purpose_id     FK -> dim_purpose
                state_code     FK -> dim_state
                emp_length_id  FK -> dim_emp_length
                default_flag   1 = defaulted, 0 = repaid
```

Run `python inspect.py` any time to get this from the database itself rather than
from a comment, or `python inspect.py --table fact_loan` for one table only.

The three join paths, which is all you really need to remember:

```sql
FROM fact_loan AS f
JOIN dim_purpose   AS p ON p.purpose_id   = f.purpose_id     -- readable purpose
JOIN dim_state     AS s ON s.state_code   = f.state_code     -- state + region
JOIN dim_emp_length AS e ON e.emp_length_id = f.emp_length_id -- tenure band
```

`census_region` only exists in `dim_state`, so exercises 8, 15 and 18 need that
join. `purpose_name` only exists in `dim_purpose`, so 7, 10, 12, 13, 14 and 18
need that one.

---

## The exercises

Column order matters. Where it says **ordered**, the row order is part of the
criteria — use an `ORDER BY` that produces exactly that order, with a tiebreaker
where several rows could share a value.

---

### Block 1 — Filtering

**1. 2017 defaults over 20,000** · 10 rows, 4 columns, ordered
Return `loan_id`, `issue_date`, `loan_amount`, `fico` for loans issued in 2017
that defaulted and are larger than 20,000. Largest first, 10 rows only.

> Hint: three conditions joined with `AND`. For a stable order when two loans
> share an amount, add `loan_id` after `loan_amount DESC`.

**2. Loans with no FICO score** · 1 row, 1 column
How many loans have no FICO score at all?

> Hint: a missing value is not zero and not `= NULL`. There is a keyword for it.

**3. Top 10 states by loan count** · 10 rows, 2 columns, ordered
Return `state_code` and the number of loans, ten states with the most loans.

> Hint: `GROUP BY` then `ORDER BY` the count. Name the count with `AS`.

---

### Block 2 — Aggregation

**4. Overall default rate** · 1 row, 1 column
Return the portfolio default rate as a percentage, two decimal places. The
answer is `19.98`.

> Hint: `default_flag` is 1 or 0, so `AVG()` of it is already a proportion.
> Multiply by 100.0 before rounding, and use `100.0` not `100` so SQLite does
> not do integer arithmetic.

**5. Default rate by home ownership** · 4 rows, 3 columns, ordered
Return `home_ownership`, the number of loans, and the default rate percentage.
Highest default rate first.

**6. Loans and average amount by issue year** · 12 rows, 3 columns, ordered
Return `issue_year`, the loan count, and the average loan amount to two decimal
places. Oldest year first.

> Hint: `issue_year` is already a column, so you do not need to parse a date.
> There are 12 years, 2007 to 2018.

---

### Block 3 — Joins

**7. Default rate by purpose name** · 14 rows, 3 columns, ordered
Same shape as exercise 5, but grouped by `purpose_name` instead of the raw
`purpose_id`. Highest default rate first.

> Hint: the fact table stores `purpose_id`. The readable name lives in
> `dim_purpose`. This is a two-table `JOIN` on that key. Alias the tables — `f`
> and `p` — because both will have a `COUNT(*)` involved.

**8. Default rate by census region** · 4 rows, 3 columns, ordered
Group by `census_region` and return loan count and default rate. Highest first.

> Hint: `census_region` is in `dim_state`, which joins on `state_code`. Two
> tables here, not three.

**9. States in the dimension with no loans** · 0 rows, 1 column
Return the `state_code` of any state that appears in `dim_state` but has no
loans in `fact_loan`. **The correct answer is zero rows** — and that is the
point of the exercise.

> Hint: `LEFT JOIN` from `dim_state` to `fact_loan`, then keep only rows where
> the fact side is `NULL`. This is called an anti-join and it is the standard
> data-quality check for orphaned or missing dimension members. Zero rows means
> the loader did its job.

---

### Block 4 — Filtering aggregates

**10. Big purposes with a high default rate** · 2 rows, 3 columns, ordered
Return `purpose_name`, loan count and default rate, keeping only purposes with
more than 50,000 loans **and** a default rate above 20%. Highest rate first.

> Hint: `WHERE` cannot filter on an aggregate. There is a separate clause that
> runs after grouping. You cannot use the column alias inside it, so repeat the
> expression.

**11. Default rate by FICO band** · 6 rows, 3 columns, ordered
Bucket `fico` into six bands and return the count and default rate for each.
Add a seventh label for a missing score:

| Band label | Condition |
|---|---|
| `unknown` | `fico` is NULL |
| `1. < 680` | below 680 |
| `2. 680-699` | 680 to 699 |
| `3. 700-719` | 700 to 719 |
| `4. 720-739` | 720 to 739 |
| `5. 740-759` | 740 to 759 |
| `6. 760+` | 760 and above |

On this dataset the result is 6 rows, not 7: no loan is missing a FICO score, so
the `unknown` group is empty and produces no row. The branch still has to be
there, and the checker re-runs your query on a small dataset that *does* contain
a missing score, so a query that leaves those loans unlabelled will fail there.

Order by the band label.

> Hint: `CASE WHEN ... THEN ... END` in the `SELECT`, then `GROUP BY` the alias.
> SQLite allows grouping by a `SELECT` alias, which saves repeating the whole
> `CASE`. The leading numbers are there so alphabetical order equals band order.
>
> `CASE` stops at the first branch that is true, so order the branches
> deliberately. `NULL < 680` is not true, it is NULL, so a missing score falls
> through every numeric branch and lands wherever you put the catch-all. Check
> `IS NULL` first.

---

### Block 5 — Subqueries and CTEs

**12. Purposes above the portfolio default rate** · 8 rows, 3 columns, ordered
Return `purpose_name`, loan count and default rate for purposes whose default
rate is **above the portfolio-wide rate**. Highest first.

> Hint: the comparison value is a single number you can compute with
> `(SELECT AVG(default_flag) FROM fact_loan)` placed directly inside `HAVING`.
> Do not type `0.1998` — compute it, so the query stays correct if the data
> changes.

**13. Same answer, but built with a CTE** · 8 rows, 3 columns, ordered
Produce the identical result to exercise 12, but structure it with
`WITH ... AS (...)` instead of a subquery inside `HAVING`. The output must
match exercise 12 exactly.

> Hint: one CTE for the per-purpose aggregates, one CTE for the portfolio rate,
> then join them with `CROSS JOIN` and filter in `WHERE`. This is the shape most
> teams prefer because each step is readable.

**14. Loans above their own purpose average** · 14 rows, 2 columns, ordered
For each purpose, count the loans whose amount is greater than the average loan
amount **for that purpose**. Return `purpose_name` and the count. Largest count
first, then purpose name.

> Hint: one CTE computing the average per `purpose_id`, then join it back to
> `fact_loan` and filter. **Do not** use a correlated subquery here — it
> re-runs once per row and will take minutes on 1.35 million rows. Learning to
> recognise that shape and rewrite it is part of the exercise.

---

### Block 6 — Window functions

This is the block that matters most. Everything so far is expected of any
candidate. These five are what separate you.

**15. States ranked inside their own region** · 51 rows, 5 columns, ordered
Return `census_region`, `state_code`, loan count, default rate, and the state's
rank by default rate **within its own region**. Order by region, then rank.

> Hint: `RANK() OVER (PARTITION BY census_region ORDER BY default_rate_pct DESC)`.
> `PARTITION BY` restarts the ranking for each region. Build the per-state rates
> in a CTE first, because you cannot window over an aggregate in the same
> `SELECT` in one step.

**16. Running total of loans by month** · 139 rows, 3 columns, ordered
Return `issue_date`, that month's loan count, and the cumulative loan count from
the first month through to that one.

> Hint: `SUM(loans) OVER (ORDER BY issue_date ROWS UNBOUNDED PRECEDING)`. The
> final row must read `1,347,681` — that is your proof the window is correct.
> Without the `ROWS` clause SQLite defaults to a running total too, but be
> explicit; interviewers ask about the difference between `ROWS` and `RANGE`.

**17. Three-month moving average default rate** · 139 rows, 3 columns, ordered
Return `issue_date`, the monthly default rate, and the average of that month and
the two before it.

> Hint: `AVG(...) OVER (ORDER BY issue_date ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)`.
> The first row has no earlier months, so its average equals itself — that is
> correct behaviour, not a bug.

**18. Top 3 purposes by volume in each region** · 12 rows, 4 columns, ordered
For each census region return its three largest purposes by loan count, as
`census_region`, `position` (1, 2, 3), `purpose_name`, `loans`.

> Hint: this is "top N per group". Compute the counts in a CTE, add
> `ROW_NUMBER() OVER (PARTITION BY census_region ORDER BY loans DESC)` in a
> second CTE, then filter `WHERE rn <= 3` in the outer query. **You cannot filter
> on a window function in the same `SELECT` that defines it** — that is the trap,
> and it is the most common window-function interview question.

**19. Month-over-month change in default rate** · 139 rows, 3 columns, ordered
Return `issue_date`, the monthly default rate, and the change from the previous
month. The first month must show `NULL`.

> Hint: `LAG(default_rate_pct) OVER (ORDER BY issue_date)` reaches back one row.
> Subtract it from the current value. `LAG` returns `NULL` for the first row,
> and any arithmetic with `NULL` is `NULL`, which is what you want.

---

### Block 7 — The classic puzzles

**20. Second-highest default rate among large purposes** · 1 row, 3 columns
Among purposes with more than 10,000 loans, return the **second** highest
default rate as `purpose_name`, `loans`, `default_rate_pct`.

> Hint: `ORDER BY ... DESC LIMIT 1 OFFSET 1`. `OFFSET` skips rows, so
> `LIMIT 1 OFFSET 1` is the second row. The alternative interview answer is
> `ROW_NUMBER()` in a CTE with `WHERE rn = 2`. Know both; they are asked as a
> pair precisely to see whether you know the second one.

---

### Block 8 — the eight questions

The twenty exercises taught the techniques. This block is the artifact: a single
`queries.sql` that answers eight questions about the loan book, written the way
an analyst hands work over. It is the file a reader of the repository opens
first, so it has to be readable, not merely correct.

Same rule as the exercises: you write it. `solutions/reference_queries.sql` is
open to you now, but write each one yourself first, then compare phrasing.

Four conventions for the file:

1. **One statement per question**, preceded by a comment starting `-- Q1`,
   `-- Q2` and so on. `run_queries.py` reads that label to title the output and
   `--query 8` runs one question alone.
2. **Name every output column.** No bare expressions in the header.
3. **Round only what you display.** Compare exact values, round the column you
   print.
4. **Order every result** that has a natural order. A result set with no
   `ORDER BY` has no order.

Shapes below are the acceptance criteria: column count, row count, grain, and
ordering. `check_queries.py` checks the shape without showing you the answer.

```bash
python check_queries.py               # all eight
python check_queries.py --query 4     # one of them
```

#### Q1 — Which region × purpose combinations carry real risk?

| | |
|---|---|
| Grain | one row per region and purpose |
| Columns (5) | `census_region`, `purpose_name`, `loans`, `total_loan_millions`, `default_rate_pct` |
| Filter | keep only combinations with **10,000 or more** loans |
| Order | `default_rate_pct` descending, `loans` descending as tiebreak |
| Rows | **17** of 56 |

The volume floor is the point of the question, and the reason is not abstract.
Drop it and the top of the table is all four regions of `small_business`
(31.34%, 30.78%, 29.29%, 27.59%), a purpose that never reaches 10,000 loans in
any single region. With the floor, the leader is `debt_consolidation` at 21.80%
on 279,397 loans.

That is worth thinking about before you write it, because it cuts both ways: the
floor is what makes the table actionable, and it is also what deletes a
consistently high-risk category from the answer. Say so in a comment. An analyst
who notices what their own filter removed is worth more than one who does not.

#### Q2 — What are the missing employment-length answers hiding?

| | |
|---|---|
| Grain | one row per employment-length band, including the non-answer |
| Columns (4) | `emp_length`, `loans`, `pct_of_portfolio`, `default_rate_pct` |
| Order | `loans` descending |
| Rows | **12** |

Two traps, and the exercise is about both:

- The `NI` row of `dim_emp_length` has **`years_min` and `years_max` set to
  NULL**. Anything that averages or buckets on years silently drops those
  loans, and `COALESCE`-ing them to zero claims they have no experience.
- `pct_of_portfolio` is the band's share of all 1,347,681 loans, so it needs a
  total that is not the band's own count. A correlated subquery or a window
  `SUM(...) OVER ()` both work.

The `NI` row must appear, labelled, as its own line. The join is not the trap:
`emp_length_id` is never NULL in `fact_loan`, so even an inner join keeps all
twelve bands. Filtering on `years_min IS NOT NULL` is what loses the row, and
that returns eleven rows instead of twelve.

#### Q3 — Which purposes beat the portfolio default rate?

| | |
|---|---|
| Grain | one row per purpose |
| Columns (4) | `purpose_name`, `loans`, `default_rate_pct`, `pts_vs_portfolio` |
| Filter | rate above the portfolio rate **and** at least 5,000 loans |
| Order | `default_rate_pct` descending |
| Rows | **6** |

`pts_vs_portfolio` is the difference in percentage points, signed, rounded to
two decimals. The portfolio rate is a scalar you compute, never type out: a
subquery returning `AVG(default_flag)` over the whole fact table. Note this is
exercise 12 plus a volume floor, so it is not the same row set.

#### Q4 — How do states rank within their own region?

| | |
|---|---|
| Grain | one row per state |
| Columns (5) | `census_region`, `state_code`, `loans`, `default_rate_pct`, `rank_in_region` |
| Filter | at least 1,000 loans per state |
| Order | `census_region`, then `rank_in_region` |
| Rows | **50** |

Fifty, not 51: DC is in the data and earns its place, while **Iowa has 14
loans** in this extract and the floor drops it. A state with 14 loans can post
any default rate it likes, so the floor is doing the same job as in Q1.

`RANK()`, not `ROW_NUMBER()`, because ties should share a position and the next
rank should skip. On this data the two happen to give identical output, since no
two states tie to the decimal. Use `RANK` anyway and be able to say why.

The one way to get this wrong is subtle. Rank inside the CTE on the **exact**
rate and round only in the outer `SELECT`. If you round first and then rank, you
invent ties that are not there: Missouri (21.338) and South Dakota (21.336) both
print as 21.34, and ranking the rounded value hands them a shared rank 3 and
skips rank 4. That is the "round only what you display" rule with teeth.

#### Q5 — How did volume build, and when had we written half the book?

| | |
|---|---|
| Grain | one row per issue month |
| Columns (5) | `issue_date`, `loans`, `loan_millions`, `cumulative_loans`, `cumulative_pct` |
| Order | `issue_date` |
| Rows | **139** |

`cumulative_loans` is a window `SUM(loans) OVER (ORDER BY issue_date ROWS
UNBOUNDED PRECEDING)`. `cumulative_pct` divides that by `SUM(loans) OVER ()` —
the same window with no `ORDER BY`, so it totals the whole book.

Then answer the second half of the question in a comment above the query: which
month first crosses 50%, and how many loans were on the book by then.

#### Q6 — What is the underlying trend under the monthly noise?

| | |
|---|---|
| Grain | one row per issue month |
| Columns (5) | `issue_date`, `loans`, `default_rate_pct`, `moving_avg_3m`, `change_vs_prev_month` |
| Order | `issue_date` |
| Rows | **139** |

`moving_avg_3m` averages this month and the two before it, so the frame is
`ROWS BETWEEN 2 PRECEDING AND CURRENT ROW`. `change_vs_prev_month` is this month
minus last month, and the first month is NULL because there is no previous
month. Do not substitute zero for that NULL.

The finding is at the end: the three-month average falls through 2016 and 2017
while the raw rate stays noisy. In a comment, say whether that is real
improvement or the censoring described in the README. It is censoring, and
getting that wrong in an interview is the mistake this exercise exists to
prevent.

#### Q7 — Top three purposes by volume in each region?

| | |
|---|---|
| Grain | one row per region and position |
| Columns (5) | `census_region`, `position`, `purpose_name`, `loans`, `pct_of_region` |
| Order | `census_region`, then `position` |
| Rows | **12** |

`pct_of_region` is the purpose's share of that region's loans, so the
denominator is a partition total: `SUM(COUNT(*)) OVER (PARTITION BY
census_region)`, or a second CTE with the regional totals. National denominator
lands near 5–10% and is obviously wrong once you look at the numbers.

`ROW_NUMBER()` here, not `RANK()`: "top three" means exactly three rows per
region, so a tie must break rather than expand the set. Filter on `rn <= 3`
**outside** the CTE, because a window function cannot appear in `WHERE` at the
same level it is defined.

#### Q8 — Default rate by FICO band × home ownership?

| | |
|---|---|
| Grain | one row per FICO band |
| Columns (6) | `fico_band`, `loans`, `default_rate_pct`, `rate_mortgage`, `rate_rent`, `rate_own` |
| Order | `fico_band` |
| Rows | **6** |

This is the cross-check. It must reproduce the README's Q8 table: band counts
summing to exactly 1,347,681, and rates matching the Power BI dashboard's risk
page to two decimals. Same data, same definitions, different engine, same
answer. That is the claim the repository makes, so it has to hold.

Prefix the band labels with their order (`1. < 680` … `6. 760+`) so text
sorting on `fico_band` comes out in risk order. Include the `unknown` branch for
a missing score even though none exist, same as exercise 11 — put it **first** in
the `CASE`, because a `NULL` compared with `<` is `NULL` and falls through to
`ELSE` if you check it last. Conditional aggregation is the pivot: `AVG(CASE WHEN
home_ownership = 'RENT' THEN default_flag END)` gives one column per tenure
without a separate query.

---

## How long this should take

Roughly three sittings, not one. Doing all twenty in an evening means you are
copying rather than learning, and the interview will find that out.

| Sitting | Exercises | Time |
|---|---|---|
| 1 | 1–9 | 60–90 min |
| 2 | 10–14 | 60 min |
| 3 | 15–20 | 90 min — the ones worth repeating |

## When you can say you know SQL

Two checkpoints, and be strict with yourself:

1. **You can write exercises 1–14 from a blank file** without looking anything
   up, in under two minutes each. That clears EUROFINS, whose bar is "basic".
2. **You can write 15–19 from a blank file** and explain `PARTITION BY`, the
   `ROWS` frame, and why a window function cannot go in `WHERE`. That clears
   POLENERGIA's "very good SQL" bar and is above what most juniors can do.

Do exercise 18 twice more the day before any interview. It is the one they ask.
