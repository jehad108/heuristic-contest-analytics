import os
import sys
import csv
import io
import time
import random
from datetime import datetime, timedelta
import psycopg2
from psycopg2 import sql
from faker import Faker

# Database connection details
DB_HOST = "localhost"
DB_PORT = 5432
DB_USER = "postgres"
DB_PASS = "123"
DB_NAME = "algo_contest"

def create_database():
    """Create the target database if it doesn't exist."""
    print("Connecting to default 'postgres' database to check/create target database...")
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASS,
        database="postgres"
    )
    conn.autocommit = True
    cur = conn.cursor()
    
    # Check if database exists
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (DB_NAME,))
    exists = cur.fetchone()
    
    if not exists:
        print(f"Database '{DB_NAME}' does not exist. Creating...")
        cur.execute(sql.SQL("CREATE DATABASE {};").format(sql.Identifier(DB_NAME)))
        print(f"Database '{DB_NAME}' created successfully.")
    else:
        print(f"Database '{DB_NAME}' already exists.")
        
    cur.close()
    conn.close()

def run_ddl_schema():
    """Read and run the DDL schema file."""
    print(f"Connecting to '{DB_NAME}' database to apply DDL schema...")
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME
    )
    conn.autocommit = True
    cur = conn.cursor()
    
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    if not os.path.exists(schema_path):
        raise FileNotFoundError(f"Schema file not found at: {schema_path}")
        
    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()
        
    print("Executing schema.sql...")
    cur.execute(schema_sql)
    print("Schema applied successfully (tables and indexes created).")
    
    cur.close()
    conn.close()

def generate_mock_data():
    """Generate mock data and insert into PostgreSQL using COPY."""
    fake = Faker()
    # Seed for reproducibility if desired, otherwise let it be random
    Faker.seed(42)
    random.seed(42)
    
    print("\n--- Starting Data Generation ---")
    start_time = time.time()
    
    # Connect to target db
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME
    )
    cur = conn.cursor()
    
    # ---------------------------------------------------------
    # 1. GENERATE USERS
    # ---------------------------------------------------------
    print("Generating 5,000 users...")
    user_data = []
    for i in range(1, 5001):
        username = f"{fake.user_name()}_{i}"
        email = f"{username}@{fake.free_email_domain()}"
        password_hash = f"pbkdf2_sha256$260000${fake.sha256()[:40]}"
        role = 'user'
        if i <= 50:
            role = 'admin' if i <= 10 else 'moderator'
        created_at = fake.date_time_between(start_date='-2y', end_date='now')
        user_data.append((username, email, password_hash, role, created_at))
        
    # Bulk insert users using COPY
    user_buffer = io.StringIO()
    writer = csv.writer(user_buffer)
    writer.writerow(['username', 'email', 'password_hash', 'role', 'created_at'])
    for row in user_data:
        writer.writerow(row)
    user_buffer.seek(0)
    
    cur.copy_expert("COPY users (username, email, password_hash, role, created_at) FROM STDIN WITH CSV HEADER", user_buffer)
    conn.commit()
    print("Inserted 5,000 users.")
    
    # ---------------------------------------------------------
    # 2. GENERATE CONTESTS
    # ---------------------------------------------------------
    print("Generating 20 contests...")
    contest_data = []
    contests_meta = [] # Store tuple of (id, start_time, end_time) to align submission times
    for i in range(1, 21):
        title = f"Contest #{i}: {fake.catch_phrase()}"
        description = fake.paragraph()
        start = fake.date_time_between(start_date='-1y', end_date='+1m')
        end = start + timedelta(hours=random.randint(2, 5))
        created = start - timedelta(days=random.randint(7, 30))
        contest_data.append((title, description, start, end, created))
        
    # Bulk insert contests using COPY
    contest_buffer = io.StringIO()
    writer = csv.writer(contest_buffer)
    writer.writerow(['title', 'description', 'start_time', 'end_time', 'created_at'])
    for row in contest_data:
        writer.writerow(row)
    contest_buffer.seek(0)
    
    cur.copy_expert("COPY contests (title, description, start_time, end_time, created_at) FROM STDIN WITH CSV HEADER", contest_buffer)
    conn.commit()
    print("Inserted 20 contests.")
    
    # Fetch generated contest IDs and times
    cur.execute("SELECT id, start_time, end_time FROM contests ORDER BY id;")
    contests_meta = cur.fetchall()
    
    # ---------------------------------------------------------
    # 3. GENERATE PROBLEMS
    # ---------------------------------------------------------
    print("Generating 100 problems...")
    problem_data = []
    problems_meta = [] # Store tuple of (id, contest_id, time_limit, memory_limit)
    difficulty_choices = ['Easy', 'Medium', 'Hard']
    
    for i in range(1, 101):
        # 80 problems belong to contests (4 per contest), 20 are independent
        contest_id = contests_meta[(i - 1) // 4][0] if i <= 80 else None
        title = f"Problem {chr(65 + (i % 6))}{i}: {fake.sentence(nb_words=3)}"
        description = f"### Problem Statement\n{fake.text(max_nb_chars=500)}\n\n### Input Format\n{fake.text(max_nb_chars=100)}\n\n### Output Format\n{fake.text(max_nb_chars=100)}"
        time_limit_ms = random.choice([500, 1000, 2000, 3000])
        memory_limit_kb = random.choice([65536, 131072, 262144, 524288]) # 64, 128, 256, 512 MB
        difficulty = random.choice(difficulty_choices)
        created_at = fake.date_time_between(start_date='-2y', end_date='now')
        
        problem_data.append((contest_id, title, description, time_limit_ms, memory_limit_kb, difficulty, created_at))
        
    # Bulk insert problems using COPY
    problem_buffer = io.StringIO()
    writer = csv.writer(problem_buffer)
    writer.writerow(['contest_id', 'title', 'description', 'time_limit_ms', 'memory_limit_kb', 'difficulty', 'created_at'])
    for row in problem_data:
        writer.writerow(row)
    problem_buffer.seek(0)
    
    cur.copy_expert("COPY problems (contest_id, title, description, time_limit_ms, memory_limit_kb, difficulty, created_at) FROM STDIN WITH CSV HEADER", problem_buffer)
    conn.commit()
    print("Inserted 100 problems.")
    
    # Fetch generated problems meta
    cur.execute("SELECT id, contest_id, time_limit_ms, memory_limit_kb FROM problems ORDER BY id;")
    problems_meta = cur.fetchall()
    
    # ---------------------------------------------------------
    # 4. GENERATE SUBMISSIONS
    # ---------------------------------------------------------
    print("Generating 250,000 submissions (this may take a few seconds)...")
    
    # Fetch all user IDs
    cur.execute("SELECT id FROM users;")
    user_ids = [r[0] for r in cur.fetchall()]
    
    # Create contest timeline lookup
    contest_timeline = {c[0]: (c[1], c[2]) for c in contests_meta}
    
    languages = ['C++', 'Java', 'Python', 'Go', 'Rust', 'JavaScript']
    code_templates = {
        'C++': '#include <iostream>\nusing namespace std;\nint main() {\n    int n;\n    cin >> n;\n    cout << n * 2 << endl;\n    return 0;\n}',
        'Java': 'import java.util.Scanner;\npublic class Main {\n    public static void main(String[] args) {\n        Scanner sc = new Scanner(System.in);\n        int n = sc.nextInt();\n        System.out.println(n * 2);\n    }\n}',
        'Python': 'import sys\nfor line in sys.stdin:\n    print(int(line) * 2)',
        'Go': 'package main\nimport "fmt"\nfunc main() {\n    var n int\n    fmt.Scan(&n)\n    fmt.Println(n * 2)\n}',
        'Rust': 'use std::io;\nfn main() {\n    let mut input = String::new();\n    io::stdin().read_line(&mut input).unwrap();\n    let n: i32 = input.trim().parse().unwrap();\n    println!("{}", n * 2);\n}',
        'JavaScript': 'const fs = require("fs");\nconst input = fs.readFileSync(0, "utf-8").trim();\nconsole.log(parseInt(input) * 2);'
    }
    
    statuses = ['Accepted', 'Wrong Answer', 'Time Limit Exceeded', 'Memory Limit Exceeded', 'Runtime Error', 'Compilation Error']
    status_weights = [0.55, 0.23, 0.08, 0.04, 0.05, 0.05]
    
    submission_buffer = io.StringIO()
    writer = csv.writer(submission_buffer)
    writer.writerow(['user_id', 'problem_id', 'contest_id', 'language', 'code', 'status', 'execution_time_ms', 'memory_used_kb', 'submitted_at'])
    
    batch_size = 50000
    for i in range(250000):
        user_id = random.choice(user_ids)
        problem = random.choice(problems_meta)
        p_id, p_contest_id, time_limit, memory_limit = problem
        
        # Decide if this submission is during the contest or a random practice submission
        contest_id = None
        submitted_at = None
        
        if p_contest_id:
            # 60% chance to submit during the contest if problem belongs to a contest
            if random.random() < 0.60:
                contest_id = p_contest_id
                start, end = contest_timeline[contest_id]
                # Random time within contest duration
                submitted_at = start + (end - start) * random.random()
        
        if not submitted_at:
            # Practice submission, pick random date within the last year
            submitted_at = fake.date_time_between(start_date='-1y', end_date='now')
            
        language = random.choice(languages)
        code = code_templates[language]
        status = random.choices(statuses, weights=status_weights, k=1)[0]
        
        # Execution time & Memory usage matching status constraints
        if status in ['Accepted', 'Wrong Answer', 'Runtime Error']:
            execution_time = random.randint(5, int(time_limit * 0.85))
            memory_used = random.randint(1024, int(memory_limit * 0.70))
        elif status == 'Time Limit Exceeded':
            execution_time = time_limit + random.randint(1, 300)
            memory_used = random.randint(1024, memory_limit)
        elif status == 'Memory Limit Exceeded':
            execution_time = random.randint(5, time_limit)
            memory_used = memory_limit + random.randint(1024, 32768)
        else: # Compilation Error
            execution_time = None
            memory_used = None
            
        # Write to csv buffer (handling timezone formats)
        submitted_at_str = submitted_at.strftime('%Y-%m-%d %H:%M:%S%z') if hasattr(submitted_at, 'tzinfo') else submitted_at.strftime('%Y-%m-%d %H:%M:%S')
        writer.writerow([user_id, p_id, contest_id, language, code, status, execution_time, memory_used, submitted_at_str])
        
        # Periodically dump to database to save memory
        if (i + 1) % batch_size == 0:
            print(f"Writing batch of {batch_size} (progress: {i + 1}/250,000)...")
            submission_buffer.seek(0)
            cur.copy_expert("COPY submissions (user_id, problem_id, contest_id, language, code, status, execution_time_ms, memory_used_kb, submitted_at) FROM STDIN WITH CSV HEADER", submission_buffer)
            conn.commit()
            
            # Reset buffer
            submission_buffer.close()
            submission_buffer = io.StringIO()
            writer = csv.writer(submission_buffer)
            writer.writerow(['user_id', 'problem_id', 'contest_id', 'language', 'code', 'status', 'execution_time_ms', 'memory_used_kb', 'submitted_at'])

    submission_buffer.close()
    
    # Analyze table to update statistics for Postgres query optimizer
    print("Analyzing tables to optimize index statistics...")
    cur.execute("ANALYZE users;")
    cur.execute("ANALYZE contests;")
    cur.execute("ANALYZE problems;")
    cur.execute("ANALYZE submissions;")
    conn.commit()
    
    cur.close()
    conn.close()
    
    elapsed = time.time() - start_time
    print(f"Successfully generated and inserted 250,000 rows in {elapsed:.2f} seconds!")

if __name__ == "__main__":
    try:
        create_database()
        run_ddl_schema()
        generate_mock_data()
    except Exception as e:
        print(f"\nError occurred: {e}", file=sys.stderr)
        sys.exit(1)
