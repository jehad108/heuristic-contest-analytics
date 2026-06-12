# Database Query Optimization Case Study: Contest Leaderboard

This case study analyzes the performance tuning of the **Dynamic Leaderboard** query on our PostgreSQL database containing **250,000 submission rows** and **5,000 users**. 

By applying modern database engineering principles, we achieved an **819x speedup** in execution time and a **6,391x reduction** in database memory/page reads.

---

## 1. The Bottleneck: Inefficient Query Design

The initial approach to calculating the leaderboard relied on a nested-loop, N+1 query model written directly inside the SQL `SELECT` list. 

### The Inefficient SQL
```sql
SELECT
    u.id AS user_id,
    u.username,
    -- Inefficient: Correlated subquery for counting solved problems, using non-sargable COALESCE
    (
        SELECT COUNT(DISTINCT s.problem_id)
        FROM submissions s
        WHERE s.user_id = u.id
          AND COALESCE(s.contest_id, 0) = 4
          AND s.status = 'Accepted'
          AND s.submitted_at >= (SELECT start_time FROM contests WHERE id = 4)
          AND s.submitted_at <= (SELECT end_time FROM contests WHERE id = 4)
    ) AS problems_solved,
    
    -- Inefficient: Correlated subquery calculating total penalty by repeating query logic
    COALESCE((
        SELECT SUM(
            EXTRACT(EPOCH FROM (first_acc.submitted_at - c.start_time)) / 60 + 
            (
                SELECT COUNT(*) 
                FROM submissions s3
                WHERE s3.user_id = u.id 
                  AND s3.problem_id = first_acc.problem_id
                  AND COALESCE(s3.contest_id, 0) = 4
                  AND s3.status NOT IN ('Accepted', 'Compilation Error', 'Pending')
                  AND s3.submitted_at < first_acc.submitted_at
            ) * 20
        )
        FROM (
            SELECT s2.problem_id, MIN(s2.submitted_at) AS submitted_at
            FROM submissions s2
            WHERE s2.user_id = u.id
              AND COALESCE(s2.contest_id, 0) = 4
              AND s2.status = 'Accepted'
              AND s2.submitted_at >= (SELECT start_time FROM contests WHERE id = 4)
              AND s2.submitted_at <= (SELECT end_time FROM contests WHERE id = 4)
            GROUP BY s2.problem_id
        ) first_acc
        CROSS JOIN contests c
        WHERE c.id = 4
    ), 0) AS total_penalty_minutes,
    
    -- Inefficient: Correlated subquery for total submissions
    (
        SELECT COUNT(*)
        FROM submissions s
        WHERE s.user_id = u.id
          AND COALESCE(s.contest_id, 0) = 4
          AND s.submitted_at >= (SELECT start_time FROM contests WHERE id = 4)
          AND s.submitted_at <= (SELECT end_time FROM contests WHERE id = 4)
    ) AS total_submissions
FROM users u
WHERE (
    SELECT COUNT(*)
    FROM submissions s
    WHERE s.user_id = u.id
      AND COALESCE(s.contest_id, 0) = 4
      AND s.submitted_at >= (SELECT start_time FROM contests WHERE id = 4)
      AND s.submitted_at <= (SELECT end_time FROM contests WHERE id = 4)
) > 0;
```

### Why it is slow:
1. **Correlated Subqueries in SELECT List**: PostgreSQL has to execute multiple subqueries **for every single user** in the table (5,000 iterations).
2. **Non-Sargable Conditions**: Using `COALESCE(contest_id, 0) = 4` prevents PostgreSQL from using normal indexes on `contest_id`, forcing full index/table filter operations on every query iteration.
3. **Repeated Subquery Execution**: SubPlan 13 alone runs `5,000` times. SubPlan 3 runs `3,526` times. SubPlan 7 runs `3,526` times.

### Inefficient Execution Plan (`EXPLAIN ANALYZE`)
* **Total Execution Time**: **`22,041.361 ms`**
* **Total Shared Buffers Hit**: **`1,419,013`** (~11 GB of pages read from cache)
* **Estimated Query Cost**: **`1,237,916.90`**

```
Seq Scan on users u  (cost=0.00..1237916.90 rows=1667 width=67) (actual time=5.716..22037.873 rows=3526.00 loops=1)
  Filter: ((SubPlan 13) > 0)
  Rows Removed by Filter: 1474
  Buffers: shared hit=1419013
  SubPlan 3
    ->  Aggregate  (cost=116.88..116.89 rows=1 width=8) (actual time=1.323..1.323 rows=1.00 loops=3526)
          Buffers: shared hit=316404
...
  SubPlan 13
    ->  Aggregate  (cost=116.86..116.87 rows=1 width=8) (actual time=1.323..1.323 rows=1.00 loops=5000)
          Buffers: shared hit=446126
          ->  Bitmap Heap Scan on submissions s_2  (cost=110.34..114.36 rows=1 width=0) (actual time=1.300..1.304 rows=1.22 loops=5000)
                Recheck Cond: ((user_id = u.id) AND (submitted_at >= (InitPlan 11).col1) AND (submitted_at <= (InitPlan 12).col1))
                Filter: (COALESCE(contest_id, 0) = 4)
                Buffers: shared hit=446126
...
Planning Time: 7.297 ms
Execution Time: 22041.361 ms
```

---

## 2. The Solution: Set-Based Refactoring & Indexing

To resolve the bottleneck, we redesigned the query using a set-based model with Common Table Expressions (CTEs) and created a covering compound B-Tree index.

### Step 1: Optimized Database Index
We created a compound index covering all search and aggregate fields of the submissions table:
```sql
CREATE INDEX IF NOT EXISTS idx_submissions_leaderboard_optimized 
ON submissions(contest_id, status, user_id, problem_id, submitted_at);
```
This index enables **Index Only Scans**, retrieving all required data directly from the index tree without fetching blocks from the heap table.

### Step 2: Set-Based Query Rewrite
The query was refactored to eliminate all correlated SELECT subqueries, aggregates are pre-grouped, and joined using hash merges.

```sql
WITH target_contest AS (
    SELECT 4 AS contest_id
),
contest_info AS (
    SELECT id, start_time, end_time 
    FROM contests 
    WHERE id = (SELECT contest_id FROM target_contest)
),
-- Set-based aggregation of user submission counts
user_submission_counts AS (
    SELECT s.user_id, COUNT(*) AS total_submissions 
    FROM submissions s 
    JOIN contest_info c ON s.contest_id = c.id 
    WHERE s.submitted_at BETWEEN c.start_time AND c.end_time 
    GROUP BY s.user_id
),
-- Set-based computation of first accepted submission time per problem
first_accepts AS (
    SELECT s.user_id, s.problem_id, MIN(s.submitted_at) AS first_accepted_at 
    FROM submissions s 
    JOIN contest_info c ON s.contest_id = c.id 
    WHERE s.status = 'Accepted' 
      AND s.submitted_at BETWEEN c.start_time AND c.end_time 
    GROUP BY s.user_id, s.problem_id
),
-- Set-based computation of incorrect attempts before first accept
wrong_submissions AS (
    SELECT s.user_id, s.problem_id, COUNT(*) AS wrong_count 
    FROM submissions s 
    JOIN contest_info c ON s.contest_id = c.id 
    LEFT JOIN first_accepts fa ON s.user_id = fa.user_id AND s.problem_id = fa.problem_id 
    WHERE s.submitted_at BETWEEN c.start_time AND c.end_time 
      AND s.status NOT IN ('Accepted', 'Compilation Error', 'Pending') 
      AND (fa.first_accepted_at IS NULL OR s.submitted_at < fa.first_accepted_at) 
    GROUP BY s.user_id, s.problem_id
),
-- Compile penalties
user_problem_stats AS (
    SELECT 
        fa.user_id, 
        fa.problem_id, 
        (EXTRACT(EPOCH FROM (fa.first_accepted_at - c.start_time)) / 60) + (COALESCE(ws.wrong_count, 0) * 20) AS problem_penalty 
    FROM first_accepts fa 
    JOIN contest_info c ON 1=1 
    LEFT JOIN wrong_submissions ws ON fa.user_id = ws.user_id AND fa.problem_id = ws.problem_id
),
-- Final aggregation
user_totals AS (
    SELECT 
        usc.user_id, 
        u.username, 
        COUNT(ups.problem_id) AS problems_solved, 
        COALESCE(SUM(ups.problem_penalty), 0) AS total_penalty_minutes, 
        usc.total_submissions 
    FROM user_submission_counts usc 
    JOIN users u ON usc.user_id = u.id 
    LEFT JOIN user_problem_stats ups ON usc.user_id = ups.user_id 
    GROUP BY usc.user_id, u.username, usc.total_submissions
)
SELECT 
    RANK() OVER (ORDER BY problems_solved DESC, total_penalty_minutes ASC) AS rank, 
    DENSE_RANK() OVER (ORDER BY problems_solved DESC, total_penalty_minutes ASC) AS dense_rank, 
    user_id, 
    username, 
    problems_solved, 
    ROUND(total_penalty_minutes::numeric, 2) AS total_penalty_minutes, 
    total_submissions 
FROM user_totals 
ORDER BY rank ASC, username ASC 
LIMIT 100;
```

---

## 3. The Result: Optimized Execution Plan

* **Total Execution Time**: **`26.940 ms`**
* **Total Shared Buffers Hit**: **`179 hits + 43 reads = 222 blocks`** (under 2 MB)
* **Estimated Query Cost**: **`1,038.30`**

### Plan Highlights
The planner performs **Index Only Scans** on `idx_submissions_leaderboard_optimized` with **0 Heap Fetches**:

```
CTE first_accepts
  ->  HashAggregate  (cost=164.01..167.68 rows=367 width=16) (actual time=1.649..2.055 rows=3072.00 loops=1)
        ->  Index Only Scan using idx_submissions_leaderboard_optimized on submissions s_2  (cost=0.42..157.57 rows=367 width=20) (actual time=0.069..0.599 rows=3319.00 loops=1)
              Index Cond: ((contest_id = c_3.id) AND (status = 'Accepted'::text) AND (submitted_at >= c_3.start_time) AND (submitted_at <= c_3.end_time))
              Heap Fetches: 0
```

---

## 4. Performance Summary Comparison

| Performance Metric | Before (Inefficient Correlated) | After (Set-Based + Optimized Index) | Improvement |
|---|---|---|---|
| **Execution Time** | `22,041.36 ms` | `26.94 ms` | **819.6x Faster** |
| **Shared Buffer Page Accesses** | `1,419,013` | `222` | **6,391.9x Fewer Reads** |
| **Estimated Query Cost** | `1,237,916.90` | `1,038.30` | **1,192.2x Cost Reduction** |
| **Subquery Loops** | `18,650` distinct subquery runs | `0` (Fully set-based) | **100% Elimination** |
| **Table Scanning Method** | Repeated Bitmap Heap scans | Hash Right/Left Joins + Index Only scans | **Optimal Scan Path** |

---

## Conclusion
By refactoring row-by-row correlated subqueries into set-based aggregates joined via Hash Joins, and backing them with a covering compound index (`idx_submissions_leaderboard_optimized`), we transformed a query that would bring a production database to its knees under concurrent traffic into a highly optimized query suitable for real-time dashboard rendering.
