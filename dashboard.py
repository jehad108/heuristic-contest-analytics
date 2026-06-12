import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import create_engine
import re

# Set page configuration with a premium dark/clean look
st.set_page_config(
    page_title="Algorithmic Judge Analytics Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for polished typography, padding, and layout
st.markdown("""
<style>
    .main-title {
        font-size: 2.8rem;
        font-weight: 800;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    .sub-title {
        font-size: 1.1rem;
        color: #718096;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f7fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 1.5rem;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #f7fafc;
        border-radius: 4px 4px 0px 0px;
        padding: 10px 20px;
        font-size: 16px;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: #edf2f7 !important;
        border-bottom: 3px solid #667eea !important;
    }
</style>
""", unsafe_allow_html=True)

# Database Connection Details
DB_HOST = "localhost"
DB_PORT = 5432
DB_USER = "postgres"
DB_PASS = "123"
DB_NAME = "algo_contest"

@st.cache_resource
def get_db_engine():
    """Create a persistent SQLAlchemy engine with connection pooling."""
    conn_str = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    return create_engine(conn_str)

engine = get_db_engine()

# Helper Functions to load and manipulate queries dynamically
def get_contests():
    """Load contests from the database."""
    query = "SELECT id, title, start_time, end_time FROM contests ORDER BY start_time DESC;"
    return pd.read_sql(query, engine)

def get_active_users():
    """Load users with accepted submissions."""
    query = """
        SELECT DISTINCT u.id, u.username 
        FROM users u 
        JOIN submissions s ON u.id = s.user_id 
        WHERE s.status = 'Accepted' 
        ORDER BY u.username;
    """
    return pd.read_sql(query, engine)

def execute_leaderboard_query(contest_id):
    """Load dynamic_leaderboard.sql and replace the target contest_id dynamically."""
    with open('queries/dynamic_leaderboard.sql', 'r', encoding='utf-8') as f:
        query = f.read()
    # Replace the default SELECT 4 AS contest_id
    query_modified = re.sub(r'SELECT\s+\d+\s+AS\s+contest_id', f'SELECT {contest_id} AS contest_id', query)
    # Remove LIMIT 100 constraint from SQL to fetch full rankings, Streamlit can handle client-side limit
    query_modified = re.sub(r'LIMIT\s+\d+;', ';', query_modified)
    return pd.read_sql(query_modified, engine)

def execute_difficulty_query():
    """Load and execute problem_difficulty_analyzer.sql."""
    with open('queries/problem_difficulty_analyzer.sql', 'r', encoding='utf-8') as f:
        query = f.read()
    # Remove LIMIT 50 constraint to analyze all problems in Python
    query_modified = re.sub(r'LIMIT\s+\d+;', ';', query)
    return pd.read_sql(query_modified, engine)

def execute_progression_query(user_id):
    """Load user_progression.sql and replace the target user_id dynamically."""
    with open('queries/user_progression.sql', 'r', encoding='utf-8') as f:
        query = f.read()
    # Replace the default SELECT 1 AS user_id
    query_modified = re.sub(r'SELECT\s+\d+\s+AS\s+user_id', f'SELECT {user_id} AS user_id', query)
    return pd.read_sql(query_modified, engine)

# Header
st.markdown("<div class='main-title'>Algorithmic Judge Analytics</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-title'>Real-time performance profiling, problem complexity metrics, and user cognitive growth tracking</div>", unsafe_allow_html=True)

# Main Tab Section
tab_leaderboard, tab_difficulty, tab_progression = st.tabs([
    "🏆 Dynamic Leaderboard", 
    "📊 Problem Difficulty Analyzer", 
    "📈 User Memory Progression"
])

# ==========================================
# 1. LEADERBOARD TAB
# ==========================================
with tab_leaderboard:
    st.header("Real-Time Contest Standings")
    st.write("Calculates real-time ranks using ACM-ICPC penalty scoring rules (solved count, first-accept timestamp, and wrong submissions penalty).")
    
    # Load contests dynamically
    contests_df = get_contests()
    
    if contests_df.empty:
        st.warning("No contests found in the database.")
    else:
        # Create a select box for the contest
        contest_options = {row['title']: row['id'] for idx, row in contests_df.iterrows()}
        selected_contest_name = st.selectbox(
            "Select Contest to View Leaderboard:", 
            list(contest_options.keys())
        )
        selected_contest_id = contest_options[selected_contest_name]
        
        # Load and run query
        with st.spinner("Computing real-time leaderboard..."):
            leaderboard_df = execute_leaderboard_query(selected_contest_id)
            
        if leaderboard_df.empty:
            st.info("No submissions recorded during this contest.")
        else:
            # Layout: Visual Plot and Table side-by-side
            col_chart, col_table = st.columns([1, 1])
            
            with col_chart:
                st.subheader("Top 15 Standings Visualized")
                # Sort dataframe for horizontal bar chart display (Rank 1 at the top)
                chart_df = leaderboard_df.head(15).iloc[::-1]
                
                fig = px.bar(
                    chart_df,
                    x='problems_solved',
                    y='username',
                    orientation='h',
                    color='total_penalty_minutes',
                    color_continuous_scale='Bluered_r',
                    labels={
                        'problems_solved': 'Problems Solved',
                        'username': 'Competitor',
                        'total_penalty_minutes': 'Total Penalty (Mins)'
                    },
                    text='problems_solved',
                    title=f"Standings for: {selected_contest_name}"
                )
                fig.update_layout(
                    height=500,
                    margin=dict(l=150, r=20, t=40, b=40),
                    coloraxis_colorbar=dict(title="Penalty (min)")
                )
                st.plotly_chart(fig, use_container_width=True)
                
            with col_table:
                st.subheader("Leaderboard Rankings")
                st.dataframe(
                    leaderboard_df[['rank', 'username', 'problems_solved', 'total_penalty_minutes', 'total_submissions']],
                    column_config={
                        "rank": st.column_config.NumberColumn("Rank", format="%d"),
                        "username": "Username",
                        "problems_solved": st.column_config.NumberColumn("Solved", format="%d"),
                        "total_penalty_minutes": st.column_config.NumberColumn("Penalty (min)", format="%.2f"),
                        "total_submissions": st.column_config.NumberColumn("Total Submissions", format="%d")
                    },
                    use_container_width=True,
                    hide_index=True,
                    height=500
                )

# ==========================================
# 2. ANALYTICS (DIFFICULTY) TAB
# ==========================================
with tab_difficulty:
    st.header("Algorithmic Complexity & Problem Difficulty")
    st.write("Correlates problem acceptance rates (empirical pass rates) with actual resource consumption (execution time and memory) to highlight structural complexity.")
    
    with st.spinner("Analyzing submissions and problem statistics..."):
        difficulty_df = execute_difficulty_query()
        
    if difficulty_df.empty:
        st.warning("No submission statistics available.")
    else:
        # Scatter Plot Analysis
        st.subheader("Empirical Complexity Scatter Map")
        
        # Color discrete map for difficulties
        color_map = {'Easy': '#2ecc71', 'Medium': '#f1c40f', 'Hard': '#e74c3c'}
        
        fig_scatter = px.scatter(
            difficulty_df,
            x='avg_execution_time_ms',
            y='avg_memory_used_kb',
            size='total_submissions',
            color='metadata_difficulty',
            color_discrete_map=color_map,
            hover_name='problem_title',
            hover_data={
                'problem_id': True,
                'acceptance_rate_pct': ':.2f',
                'analytical_difficulty_rank': True,
                'composite_difficulty_score': ':.1f'
            },
            labels={
                'avg_execution_time_ms': 'Avg Execution Time (ms)',
                'avg_memory_used_kb': 'Avg Memory Used (KB)',
                'metadata_difficulty': 'Design Difficulty',
                'total_submissions': 'Total Submissions'
            },
            title="Computational Resource Profiles vs Design Class"
        )
        
        fig_scatter.update_layout(
            height=600,
            xaxis_title="Avg Execution Time (ms)",
            yaxis_title="Avg Memory Used (KB)",
            legend_title="Metadata Difficulty"
        )
        st.plotly_chart(fig_scatter, use_container_width=True)
        
        # Detailed stats table below
        st.subheader("Empirical Hardest Problems Index")
        st.write("Identifies the hardest problems sorted by their composite difficulty score (low pass rates and high execution time).")
        st.dataframe(
            difficulty_df[['analytical_difficulty_rank', 'problem_id', 'problem_title', 'metadata_difficulty', 'acceptance_rate_pct', 'avg_execution_time_ms', 'avg_memory_used_kb', 'composite_difficulty_score']],
            column_config={
                "analytical_difficulty_rank": st.column_config.NumberColumn("Empirical Rank", format="%d"),
                "problem_id": st.column_config.NumberColumn("ID", format="%d"),
                "problem_title": "Title",
                "metadata_difficulty": "Design Difficulty",
                "acceptance_rate_pct": st.column_config.NumberColumn("Pass Rate (%)", format="%.2f%%"),
                "avg_execution_time_ms": st.column_config.NumberColumn("Avg Time (ms)", format="%.2f"),
                "avg_memory_used_kb": st.column_config.NumberColumn("Avg Memory (KB)", format="%.2f"),
                "composite_difficulty_score": st.column_config.NumberColumn("Composite Score", format="%.1f")
            },
            use_container_width=True,
            hide_index=True,
            height=400
        )

# ==========================================
# 3. USER PROGRESSION TAB
# ==========================================
with tab_progression:
    st.header("Competitor Growth & Memory Optimization History")
    st.write("Tracks month-over-month memory usage trends on accepted solutions. A downward trend represents structural code optimization.")
    
    # Load users dropdown
    users_df = get_active_users()
    
    if users_df.empty:
        st.warning("No active users with accepted submissions found in the database.")
    else:
        user_options = {row['username']: row['id'] for idx, row in users_df.iterrows()}
        selected_username = st.selectbox(
            "Select User to Analyze Progress:", 
            list(user_options.keys())
        )
        selected_user_id = user_options[selected_username]
        
        with st.spinner("Generating growth statistics..."):
            progression_df = execute_progression_query(selected_user_id)
            
        if progression_df.empty:
            st.info(f"User '{selected_username}' does not have accepted submissions across multiple months to map growth.")
        else:
            # Layout
            col_chart_prog, col_metrics = st.columns([2, 1])
            
            with col_chart_prog:
                st.subheader("Memory Usage Trend Line")
                # Line chart showing avg memory used
                fig_line = go.Figure()
                
                # Plot average memory usage
                fig_line.add_trace(go.Scatter(
                    x=progression_df['current_month'],
                    y=progression_df['avg_memory_used_kb'],
                    mode='lines+markers',
                    name='Avg Memory (KB)',
                    line=dict(color='#667eea', width=3),
                    marker=dict(size=8, symbol='circle')
                ))
                
                fig_line.update_layout(
                    title=f"Month-over-Month Memory Profile for {selected_username}",
                    xaxis_title="Month",
                    yaxis_title="Average Memory Used (KB)",
                    height=450,
                    margin=dict(l=40, r=40, t=40, b=40)
                )
                st.plotly_chart(fig_line, use_container_width=True)
                
            with col_metrics:
                st.subheader("Performance Metrics Summarized")
                
                # Get latest month stats
                latest_row = progression_df.iloc[-1]
                latest_mem = latest_row['avg_memory_used_kb']
                latest_month = latest_row['current_month']
                latest_count = latest_row['accepted_submissions_count']
                
                # Get total change from baseline
                baseline_mem = progression_df.iloc[0]['avg_memory_used_kb']
                overall_improvement = ((baseline_mem - latest_mem) / baseline_mem) * 100.0
                
                # Display metrics
                st.metric(
                    label=f"Avg Memory in {latest_month} (KB)",
                    value=f"{latest_mem:,.1f} KB"
                )
                
                st.metric(
                    label="Active Month Count",
                    value=len(progression_df)
                )
                
                st.metric(
                    label="Cumulative Optimization Improvement from Baseline",
                    value=f"{overall_improvement:+.2f}%",
                    delta=f"{overall_improvement:.2f}%" if overall_improvement >= 0 else f"{overall_improvement:.2f}%"
                )
                
            st.subheader("Tabular Progression Logs")
            st.dataframe(
                progression_df[['current_month', 'avg_memory_used_kb', 'accepted_submissions_count', 'previous_month', 'prev_avg_memory_used_kb', 'mom_efficiency_improvement_pct']],
                column_config={
                    "current_month": "Month",
                    "avg_memory_used_kb": st.column_config.NumberColumn("Avg Memory (KB)", format="%.2f"),
                    "accepted_submissions_count": st.column_config.NumberColumn("Accepted Submissions", format="%d"),
                    "previous_month": "Prior Month",
                    "prev_avg_memory_used_kb": st.column_config.NumberColumn("Prior Month Avg Memory (KB)", format="%.2f"),
                    "mom_efficiency_improvement_pct": st.column_config.NumberColumn("MoM Efficiency Change (%)", format="%+.2f%%")
                },
                use_container_width=True,
                hide_index=True,
                height=300
            )
