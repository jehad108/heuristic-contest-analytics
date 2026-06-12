-- User Progression: Month-over-Month Memory Efficiency Tracker
-- Tracks a user's month-over-month change in average memory efficiency for accepted solutions.
-- Memory efficiency improvement is calculated as:
--   ((prev_month_avg_memory - current_month_avg_memory) / prev_month_avg_memory) * 100.0
--   A positive percentage indicates an improvement (memory usage decreased).

WITH target_user AS (
    SELECT 1 AS user_id -- Change this ID to track a different user
),

-- Aggregate accepted submission memory usage by user and month
user_monthly_memory AS (
    SELECT
        s.user_id,
        DATE_TRUNC('month', s.submitted_at) AS submission_month,
        AVG(s.memory_used_kb) AS avg_memory_used_kb,
        COUNT(*) AS accepted_submissions_count
    FROM submissions s
    WHERE s.status = 'Accepted'
      -- Filter for the target user (remove this condition or join with target_user to see all users)
      AND s.user_id = (SELECT user_id FROM target_user)
    GROUP BY s.user_id, DATE_TRUNC('month', s.submitted_at)
),

-- Retrieve prior month stats for the same user using the LAG() window function
monthly_progression AS (
    SELECT
        umm.user_id,
        umm.submission_month,
        umm.avg_memory_used_kb,
        umm.accepted_submissions_count,
        -- Get the previous month's submission month and average memory usage
        LAG(umm.submission_month) OVER (
            PARTITION BY umm.user_id 
            ORDER BY umm.submission_month
        ) AS prev_submission_month,
        LAG(umm.avg_memory_used_kb) OVER (
            PARTITION BY umm.user_id 
            ORDER BY umm.submission_month
        ) AS prev_avg_memory_used_kb
    FROM user_monthly_memory umm
)

-- Calculate Month-over-Month progression and display results
SELECT
    mp.user_id,
    u.username,
    TO_CHAR(mp.submission_month, 'YYYY-MM') AS current_month,
    ROUND(mp.avg_memory_used_kb::numeric, 2) AS avg_memory_used_kb,
    mp.accepted_submissions_count,
    TO_CHAR(mp.prev_submission_month, 'YYYY-MM') AS previous_month,
    ROUND(mp.prev_avg_memory_used_kb::numeric, 2) AS prev_avg_memory_used_kb,
    -- Calculate improvement percentage (decrease in memory usage = positive efficiency improvement)
    CASE 
        WHEN mp.prev_avg_memory_used_kb IS NULL THEN NULL -- First month baseline
        ELSE ROUND(
            ((mp.prev_avg_memory_used_kb - mp.avg_memory_used_kb) / mp.prev_avg_memory_used_kb * 100.0)::numeric, 
            2
        )
    END AS mom_efficiency_improvement_pct
FROM monthly_progression mp
JOIN users u ON mp.user_id = u.id
ORDER BY mp.user_id, mp.submission_month;
