# Heuristic Contest Analytics: Database Architecture & Performance Tuning

## Overview
Managing millions of execution times, memory limits, and dynamic user rankings requires a robust, highly optimized database. This repository demonstrates a production-grade backend data architecture designed to handle the heavy read/write throughput of a competitive algorithmic judging system.

Beyond the initial schema design, this project showcases advanced SQL capabilities (Recursive CTEs, Window Functions), an interactive analytics dashboard, and a documented performance tuning study proving the real-world impact of compound indexing on slow queries.

## Tech Stack
* **Database:** PostgreSQL
* **Data Engineering:** SQL (Advanced Aggregation, Window Functions, CTEs)
* **Data Generation:** Python (`Faker`)
* **Visualization:** Python (`Streamlit`, `Plotly`, `SQLAlchemy`)

---

## Database Architecture
The relational database is normalized to efficiently track user performance across multiple heuristic and algorithmic contests. 

### Core Tables:
* `users`: Demographics and global ranking scores.
* `contests`: Metadata for time-boxed coding events.
* `problems`: Problem statements, memory limits (KB), and time limit thresholds (ms).
* `submissions`: The highest-throughput table tracking `execution_time_ms`, `memory_used_kb`, and execution `status` (e.g., *Accepted*, *Time Limit Exceeded*, *Wrong Answer*).

---

## Key Features

### 1. High-Volume Data Simulation
Includes a Python script utilizing the `Faker` library to autonomously generate and seed the database with **250,000+ rows** of realistic mock submission data, mimicking the traffic of a live coding contest.

### 2. Advanced SQL Analytics
Located in the `queries/` directory, these scripts solve complex business logic problems directly at the database layer:
* **Dynamic Leaderboards:** Utilizes Window Functions (`RANK()`, `DENSE_RANK()`) to calculate real-time standings with penalty logic applied for incorrect attempts.
* **Difficulty Analyzer:** Uses Common Table Expressions (CTEs) to isolate the hardest problems by correlating low acceptance rates with high average execution times.
* **User Progression:** Tracks month-over-month memory efficiency improvements for individual users.

### 3. Query Optimization Case Study
A deep dive into database performance. The `OPTIMIZATION_CASE_STUDY.md` file demonstrates:
* Intentional bottlenecking using sub-optimal querying.
* Pre-optimization `EXPLAIN ANALYZE` execution plans.
* The application of compound indexing and query rewriting.
* Post-optimization metrics showing drastic reductions in query cost and execution time.

### 4. Interactive Data Dashboard
A Streamlit web application that connects to the local PostgreSQL instance to visualize the SQL outputs. Features responsive Plotly charts, including a ranked leaderboard bar chart and a scatter plot analyzing algorithmic execution difficulty.

---

## Local Setup & Installation

**1. Clone the repository:**
```bash
git clone [https://github.com/yourusername/heuristic-contest-analytics.git](https://github.com/yourusername/heuristic-contest-analytics.git)
cd heuristic-contest-analytics
