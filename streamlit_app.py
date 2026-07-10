import streamlit as st
import sqlite3
import pandas as pd
import anthropic

# ── Config ───────────────────────────────────────────────────────────────────
DB_PATH = "data/nhs_mental_health.db"

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="NHS Mental Health Recovery Agent",
    page_icon="🏥",
    layout="wide"
)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
    <div style='background-color:#003087; padding:20px; border-radius:8px;'>
        <h1 style='color:white; margin:0;'>NHS Mental Health Recovery Agent</h1>
        <p style='color:#00A9CE; margin:0;'>Post-Pandemic Talking Therapies Analysis (2019-2026)</p>
    </div>
""", unsafe_allow_html=True)

st.markdown("---")

# ── Database helper ───────────────────────────────────────────────────────────
def query_db(sql):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql(sql, conn)
    conn.close()
    return df

# ── Data context builder ──────────────────────────────────────────────────────
def build_data_context(user_question):
    context_parts = []

    # Always include national summary
    national = query_db("""
        SELECT analytical_period, measure_id, measure_name,
               ROUND(AVG(CAST(measure_value AS FLOAT)), 2) as avg_value
        FROM talking_therapies
        WHERE group_type = 'England'
        AND measure_value NOT IN ('*', 'NULL', 'nan')
        AND analytical_period IS NOT NULL
        AND measure_id IN ('M001', 'M053', 'M192', 'M195')
        GROUP BY analytical_period, measure_id, measure_name
        ORDER BY measure_id, analytical_period
    """)
    context_parts.append(f"NATIONAL TRENDS:\n{national.to_string(index=False)}")

    # Regional data
    if any(word in user_question.lower() for word in 
           ['region', 'north', 'south', 'london', 'midlands', 'east', 'west', 'yorkshire']):
        regional = query_db("""
            SELECT org_name,
                   ROUND(AVG(CAST(measure_value AS FLOAT)), 2) as avg_recovery_rate
            FROM talking_therapies
            WHERE measure_id = 'M192'
            AND group_type = 'CommissioningRegion'
            AND measure_value NOT IN ('*', 'NULL', 'nan')
            AND analytical_period = 'recovery'
            AND org_code NOT IN ('InvalidRegionCode')
            GROUP BY org_name
            ORDER BY avg_recovery_rate DESC
        """)
        context_parts.append(f"REGIONAL RECOVERY RATES (POST-PANDEMIC):\n{regional.to_string(index=False)}")

    # Deprivation data
    if any(word in user_question.lower() for word in 
           ['depriv', 'poverty', 'inequal', 'decile', 'imd', 'poor', 'wealth']):
        deprivation = query_db("""
            SELECT t.analytical_period, d.deprivation_decile,
                   ROUND(AVG(CAST(t.measure_value AS FLOAT)), 2) as avg_recovery_rate
            FROM talking_therapies t
            JOIN ccg_deprivation d ON t.org_code = d.CCG19CDH
            WHERE t.measure_id = 'M192'
            AND t.measure_value NOT IN ('*', 'NULL', 'nan')
            AND t.analytical_period IN ('pre_pandemic', 'pandemic')
            AND d.deprivation_decile IS NOT NULL
            GROUP BY t.analytical_period, d.deprivation_decile
            ORDER BY t.analytical_period, d.deprivation_decile
        """)
        context_parts.append(f"DEPRIVATION ANALYSIS:\n{deprivation.to_string(index=False)}")

    # Risk scores
    if any(word in user_question.lower() for word in 
           ['risk', 'high risk', 'vulnerable', 'ccg', 'worst', 'struggling']):
        risk = query_db("""
            SELECT org_code, risk_category,
                   ROUND(risk_score, 3) as risk_score,
                   ROUND(pre_pandemic_recovery_rate, 2) as pre_pandemic_rate,
                   ROUND(recovery_period_rate, 2) as post_pandemic_rate,
                   deprivation_decile
            FROM ccg_risk_scores
            WHERE risk_category = 'High Risk'
            ORDER BY risk_score DESC
            LIMIT 20
        """)
        context_parts.append(f"HIGH RISK CCGs:\n{risk.to_string(index=False)}")

    # Executive summary trigger
    if any(word in user_question.lower() for word in 
           ['summary', 'executive', 'overview', 'summarise', 'summarize']):
        risk_counts = query_db("""
            SELECT risk_category, COUNT(*) as count
            FROM ccg_risk_scores
            GROUP BY risk_category
        """)
        context_parts.append(f"RISK DISTRIBUTION:\n{risk_counts.to_string(index=False)}")

    return "\n\n".join(context_parts)


# ── System prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are an NHS mental health data analyst with expertise in public health, 
health inequalities, and the NHS Talking Therapies programme (formerly IAPT).

You are analysing post-pandemic recovery in England's mental health services using data from 
February 2019 to April 2026. The data covers three analytical periods:
- Pre-pandemic: February 2019 to February 2020
- Pandemic: March 2020 to March 2021  
- Recovery: April 2021 to April 2026 (also called post-pandemic)

Key measures in the data:
- M001: Count of referrals received
- M053: Percentage treated within 6 weeks
- M192: Recovery rate (percentage of patients who recover)
- M195: Reliable recovery rate (stricter measure)

Key findings from the analysis:
- National recovery rate dropped from 51.79% pre-pandemic to 50.14% post-pandemic
- North East and Yorkshire leads regional recovery at 51.2%
- North West lags at 48.85%
- Deprivation gap: least deprived areas recover at 54.07% vs 49.88% in most deprived areas (4.19 ppts)
- Pre-pandemic baseline is the strongest predictor of post-pandemic performance

Important limitation: The 2022 NHS restructure (CCGs to ICBs) creates a geographic 
discontinuity that limits deprivation analysis to pre-pandemic and pandemic periods only.

Your responses should be:
- Clear and accessible to both clinical and non-clinical NHS audiences
- Evidence-based, citing specific numbers from the data provided
- Structured with clear headings where appropriate
- Honest about data limitations
- Written in a professional but approachable tone
- Concise but comprehensive

When generating executive summaries, use a Big 4 consulting style with clear assertions 
followed by evidence."""


# ── Chat interface ────────────────────────────────────────────────────────────
if "messages" in st.session_state:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
else:
    st.session_state.messages = []

# ── Suggested questions ───────────────────────────────────────────────────────
st.markdown("**Suggested questions:**")
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("Summarise regional performance"):
        st.session_state.pending_question = "Summarise regional performance"
with col2:
    if st.button("Which high-risk CCGs are also highly deprived?"):
        st.session_state.pending_question = "Which high-risk CCGs are also highly deprived?"
with col3:
    if st.button("Generate an executive summary for this dashboard"):
        st.session_state.pending_question = "Generate an executive summary for this dashboard"

col4, col5 = st.columns(2)
with col4:
    if st.button("Compare the North West with London"):
        st.session_state.pending_question = "Compare the North West with London"
with col5:
    if st.button("What changed after the pandemic?"):
        st.session_state.pending_question = "What changed after the pandemic?"

# ── Chat input ────────────────────────────────────────────────────────────────
user_input = st.chat_input("Ask a question about NHS mental health recovery...")

if "pending_question" in st.session_state:
    user_input = st.session_state.pending_question
    del st.session_state.pending_question

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Analysing data..."):
            data_context = build_data_context(user_input)

            client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])

            messages_for_api = []
            for msg in st.session_state.messages[:-1]:
                messages_for_api.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })

            messages_for_api.append({
                "role": "user",
                "content": f"""User question: {user_input}

Here is the relevant data from the database:

{data_context}

Please answer the question based on this data."""
            })

            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2000,
                system=SYSTEM_PROMPT,
                messages=messages_for_api
            )

            answer = next(block.text for block in response.content if hasattr(block, "text"))
            st.markdown(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})