-- Dynamic Leaderboard for Algorithmic Contest
-- Calculates real-time ranks using RANK() and DENSE_RANK()
-- Penalty calculation:
--   - Only submissions within the contest start and end times are considered.
--   - Solved Problems: Count of unique problems with at least one 'Accepted' status.
--   - Time Penalty: For each solved problem, the duration from contest start to the first 'Accepted' submission + 20 minutes for each wrong submission before that 'Accepted' submission.
--   - No penalty is added for problems that are not solved.

WITH target_contest AS (
    SELECT 4 AS contest_id -- Change this value to view leaderboard for other contests
),

contest_info AS (
    SELECT id, start_time, end_time
    FROM contests
    WHERE id = (SELECT contest_id FROM target_contest)
),

-- Get the first accepted submission timestamp for each user and problem in the contest
first_accepts AS (
    SELECT 
        s.user_id,
        s.problem_id,
        MIN(s.submitted_at) AS first_accepted_at
    FROM submissions s
    JOIN contest_info c ON s.contest_id = c.id
    WHERE s.status = 'Accepted'
      AND s.submitted_at BETWEEN c.start_time AND c.end_time
    GROUP BY s.user_id, s.problem_id
),

-- Count wrong submissions before the first accepted submission (if any)
wrong_submissions AS (
    SELECT 
        s.user_id,
        s.problem_id,
        COUNT(*) AS wrong_count
    FROM submissions s
    JOIN contest_info c ON s.contest_id = c.id
    LEFT JOIN first_accepts fa ON s.user_id = fa.user_id AND s.problem_id = fa.problem_id
    WHERE s.submitted_at BETWEEN c.start_time AND c.end_time
      -- Submission was wrong (exclude Accepted, Compilation Error, Pending)
      AND s.status NOT IN ('Accepted', 'Compilation Error', 'Pending')
      -- Submission was before the first accepted submission
      AND (fa.first_accepted_at IS NULL OR s.submitted_at < fa.first_accepted_at)
    GROUP BY s.user_id, s.problem_id
),

-- Calculate stats per user per problem
user_problem_stats AS (
    SELECT
        fa.user_id,
        fa.problem_id,
        fa.first_accepted_at,
        COALESCE(ws.wrong_count, 0) AS wrong_attempts,
        -- Total penalty for this problem in minutes: time elapsed since contest start + 20 mins per wrong attempt
        (EXTRACT(EPOCH FROM (fa.first_accepted_at - c.start_time)) / 60) + (COALESCE(ws.wrong_count, 0) * 20) AS problem_penalty
    FROM first_accepts fa
    JOIN contest_info c ON 1 = 1
    LEFT JOIN wrong_submissions ws ON fa.user_id = ws.user_id AND fa.problem_id = ws.problem_id
),

-- Aggregate stats per user
user_leaderboard AS (
    SELECT
        u.id AS user_id,
        u.username,
        COUNT(ups.problem_id) AS problems_solved,
        COALESCE(SUM(ups.problem_penalty), 0) AS total_penalty_minutes,
        -- Also capture total submissions count for user during the contest for stats
        (
            SELECT COUNT(*) 
            FROM submissions s 
            JOIN contest_info c ON s.contest_id = c.id
            WHERE s.user_id = u.id 
              AND s.submitted_at BETWEEN c.start_time AND c.end_time
        ) AS total_submissions
    FROM users u
    LEFT JOIN user_problem_stats ups ON u.id = ups.user_id
    -- Only list users who have at least one submission during the contest
    WHERE EXISTS (
        SELECT 1 
        FROM submissions s
        JOIN contest_info c ON s.contest_id = c.id
        WHERE s.user_id = u.id
          AND s.submitted_at BETWEEN c.start_time AND c.end_time
    )
    GROUP BY u.id, u.username
)

-- Rank users using window functions
SELECT
    RANK() OVER (ORDER BY problems_solved DESC, total_penalty_minutes ASC) AS rank,
    DENSE_RANK() OVER (ORDER BY problems_solved DESC, total_penalty_minutes ASC) AS dense_rank,
    user_id,
    username,
    problems_solved,
    ROUND(total_penalty_minutes::numeric, 2) AS total_penalty_minutes,
    total_submissions
FROM user_leaderboard
ORDER BY rank ASC, username ASC
LIMIT 100; -- Limit results to top 100 for display / reporting
