-- Problem Difficulty Analyzer
-- Finds the hardest problems (lowest acceptance rate) that also have the highest average execution time.
-- Uses Common Table Expressions (CTEs), window functions, and ranking logic to compute a combined difficulty index.

WITH problem_stats AS (
    -- Calculate basic submission statistics for each problem
    SELECT
        problem_id,
        COUNT(*) AS total_submissions,
        COUNT(CASE WHEN status = 'Accepted' THEN 1 END) AS accepted_submissions,
        -- Calculate acceptance rate (avoiding division by zero)
        ROUND(
            (COUNT(CASE WHEN status = 'Accepted' THEN 1 END)::numeric / COUNT(*)) * 100.0, 
            2
        ) AS acceptance_rate,
        ROUND(AVG(execution_time_ms)::numeric, 2) AS avg_execution_time_ms,
        ROUND(AVG(memory_used_kb)::numeric, 2) AS avg_memory_used_kb
    FROM submissions
    GROUP BY problem_id
    HAVING COUNT(*) > 0 -- Only analyze problems that have at least one submission
),

ranked_problems AS (
    -- Assign ranks based on both low acceptance rate and high execution time
    SELECT
        ps.problem_id,
        ps.total_submissions,
        ps.accepted_submissions,
        ps.acceptance_rate,
        ps.avg_execution_time_ms,
        ps.avg_memory_used_kb,
        -- Lower acceptance rate = harder (rank 1 is hardest)
        RANK() OVER (ORDER BY ps.acceptance_rate ASC) AS acceptance_difficulty_rank,
        -- Higher execution time = harder (rank 1 is slowest)
        RANK() OVER (ORDER BY ps.avg_execution_time_ms DESC NULLS LAST) AS time_difficulty_rank
    FROM problem_stats ps
),

difficulty_composite AS (
    -- Combine both ranks into a composite difficulty score (average of both ranks)
    SELECT
        rp.*,
        (rp.acceptance_difficulty_rank + rp.time_difficulty_rank) / 2.0 AS composite_difficulty_score
    FROM ranked_problems rp
)

-- Join metadata and output the top hardest problems
SELECT
    -- Assign a final analytical rank based on the composite score
    DENSE_RANK() OVER (ORDER BY dc.composite_difficulty_score ASC) AS analytical_difficulty_rank,
    dc.problem_id,
    p.title AS problem_title,
    p.difficulty AS metadata_difficulty,
    p.time_limit_ms,
    dc.total_submissions,
    dc.accepted_submissions,
    dc.acceptance_rate AS acceptance_rate_pct,
    dc.avg_execution_time_ms,
    dc.avg_memory_used_kb,
    dc.acceptance_difficulty_rank,
    dc.time_difficulty_rank,
    ROUND(dc.composite_difficulty_score::numeric, 1) AS composite_difficulty_score
FROM difficulty_composite dc
JOIN problems p ON dc.problem_id = p.id
ORDER BY analytical_difficulty_rank ASC, dc.acceptance_rate ASC
LIMIT 50;
