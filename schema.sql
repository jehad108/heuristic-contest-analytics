-- DDL Script for Algorithmic Contest Platform Schema
-- Designed by Lead Database Architect

-- Enable the UUID extension in case we want to support UUIDs later,
-- though for maximum write throughput sequential/identity IDs are preferred.
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ==========================================
-- 1. USERS TABLE
-- ==========================================
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) DEFAULT 'user' NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    
    CONSTRAINT chk_role CHECK (role IN ('user', 'admin', 'moderator')),
    CONSTRAINT chk_username_length CHECK (LENGTH(username) >= 3),
    CONSTRAINT chk_email_format CHECK (email LIKE '%@%.%')
);

-- Indexes for users
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

-- ==========================================
-- 2. CONTESTS TABLE
-- ==========================================
CREATE TABLE IF NOT EXISTS contests (
    id SERIAL PRIMARY KEY,
    title VARCHAR(150) NOT NULL,
    description TEXT,
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    
    CONSTRAINT chk_contest_times CHECK (start_time < end_time),
    CONSTRAINT chk_title_length CHECK (LENGTH(title) >= 3)
);

-- Indexes for contests
CREATE INDEX IF NOT EXISTS idx_contests_start_time ON contests(start_time);
CREATE INDEX IF NOT EXISTS idx_contests_end_time ON contests(end_time);

-- ==========================================
-- 3. PROBLEMS TABLE
-- ==========================================
CREATE TABLE IF NOT EXISTS problems (
    id SERIAL PRIMARY KEY,
    contest_id INT,
    title VARCHAR(150) NOT NULL,
    description TEXT NOT NULL,
    time_limit_ms INT NOT NULL DEFAULT 2000,
    memory_limit_kb INT NOT NULL DEFAULT 262144, -- 256 MB
    difficulty VARCHAR(20) NOT NULL DEFAULT 'Medium',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    
    CONSTRAINT fk_problems_contest FOREIGN KEY (contest_id) REFERENCES contests(id) ON DELETE SET NULL,
    CONSTRAINT chk_time_limit CHECK (time_limit_ms > 0 AND time_limit_ms <= 15000), -- max 15 seconds
    CONSTRAINT chk_memory_limit CHECK (memory_limit_kb > 0 AND memory_limit_kb <= 1048576), -- max 1 GB
    CONSTRAINT chk_difficulty CHECK (difficulty IN ('Easy', 'Medium', 'Hard'))
);

-- Indexes for problems
CREATE INDEX IF NOT EXISTS idx_problems_contest_id ON problems(contest_id);

-- ==========================================
-- 4. SUBMISSIONS TABLE
-- ==========================================
-- For millions of submissions, we use BIGSERIAL (BIGINT) to avoid ID exhaustion.
CREATE TABLE IF NOT EXISTS submissions (
    id BIGSERIAL PRIMARY KEY,
    user_id INT NOT NULL,
    problem_id INT NOT NULL,
    contest_id INT,
    language VARCHAR(20) NOT NULL,
    code TEXT NOT NULL,
    status VARCHAR(30) NOT NULL,
    execution_time_ms INT,
    memory_used_kb INT,
    submitted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    
    CONSTRAINT fk_submissions_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_submissions_problem FOREIGN KEY (problem_id) REFERENCES problems(id) ON DELETE CASCADE,
    CONSTRAINT fk_submissions_contest FOREIGN KEY (contest_id) REFERENCES contests(id) ON DELETE SET NULL,
    
    CONSTRAINT chk_language CHECK (language IN ('C++', 'Java', 'Python', 'Go', 'Rust', 'JavaScript')),
    CONSTRAINT chk_status CHECK (status IN ('Pending', 'Accepted', 'Wrong Answer', 'Time Limit Exceeded', 'Memory Limit Exceeded', 'Runtime Error', 'Compilation Error')),
    CONSTRAINT chk_execution_time CHECK (execution_time_ms >= 0),
    CONSTRAINT chk_memory_used CHECK (memory_used_kb >= 0)
);

-- Crucial Indexes for Performance on Submissions (Millions of rows)
-- Index to fetch a user's submission history rapidly
CREATE INDEX IF NOT EXISTS idx_submissions_user_id ON submissions(user_id);
-- Index to fetch submissions for a specific problem (useful for stats & analysis)
CREATE INDEX IF NOT EXISTS idx_submissions_problem_id ON submissions(problem_id);
-- Compound Index for contest leaderboards (filter by contest, sort/group by user, order by submission time)
CREATE INDEX IF NOT EXISTS idx_submissions_contest_leaderboard ON submissions(contest_id, submitted_at DESC);
