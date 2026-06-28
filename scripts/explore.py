import pandas as pd
import sqlite3
import matplotlib.pyplot as plt
import seaborn as sns
import os

# ── Config ───────────────────────────────────────────────────────────────────
DB_PATH = "data/nhs_mental_health.db"
OUTPUT_PATH = "outputs/charts"
os.makedirs(OUTPUT_PATH, exist_ok=True)

conn = sqlite3.connect(DB_PATH)

# ── Query 1: National trends across three periods ─────────────────────────────
print("Query 1: National trends by analytical period...")
q1 = """
    SELECT 
        analytical_period,
        measure_id,
        measure_name,
        AVG(CAST(measure_value AS FLOAT)) as avg_value,
        COUNT(*) as row_count
    FROM talking_therapies
    WHERE group_type = 'England'
    AND measure_value NOT IN ('*', 'NULL', 'nan')
    AND analytical_period IS NOT NULL
    GROUP BY analytical_period, measure_id, measure_name
    ORDER BY measure_id, analytical_period
"""
df_q1 = pd.read_sql(q1, conn)
print(df_q1.to_string())
print()

# ── Query 2: Recovery rate by CCG/SubICB and analytical period ────────────────
print("Query 2: Recovery rate by region and analytical period...")
q2 = """
    SELECT 
        analytical_period,
        org_code,
        org_name,
        AVG(CAST(measure_value AS FLOAT)) as avg_recovery_rate
    FROM talking_therapies
    WHERE measure_id = 'M192'
    AND group_type IN ('CCG', 'SubICB')
    AND measure_value NOT IN ('*', 'NULL', 'nan')
    AND org_code IS NOT NULL
    AND analytical_period IS NOT NULL
    GROUP BY analytical_period, org_code, org_name
    ORDER BY analytical_period, avg_recovery_rate DESC
"""
df_q2 = pd.read_sql(q2, conn)
print(df_q2.to_string())
print()

# ── Query 3: Deprivation vs recovery rate (pre_pandemic and pandemic) ─────────
print("Query 3: Deprivation decile vs recovery rate...")
q3 = """
    SELECT 
        t.analytical_period,
        d.deprivation_decile,
        AVG(CAST(t.measure_value AS FLOAT)) as avg_recovery_rate,
        COUNT(*) as row_count
    FROM talking_therapies t
    JOIN ccg_deprivation d ON t.org_code = d.CCG19CDH
    WHERE t.measure_id = 'M192'
    AND t.measure_value NOT IN ('*', 'NULL', 'nan')
    AND t.analytical_period IN ('pre_pandemic', 'pandemic')
    AND d.deprivation_decile IS NOT NULL
    GROUP BY t.analytical_period, d.deprivation_decile
    ORDER BY t.analytical_period, d.deprivation_decile
"""
df_q3 = pd.read_sql(q3, conn)
print(df_q3.to_string())
print()

# ── Query 4: Recovery rate by region during recovery period ───────────────────
print("Query 4: Recovery rate by region during recovery period...")
q4 = """
    SELECT 
        org_code,
        org_name,
        AVG(CAST(measure_value AS FLOAT)) as avg_recovery_rate,
        COUNT(*) as row_count
    FROM talking_therapies
    WHERE measure_id = 'M192'
    AND group_type = 'CommissioningRegion'
    AND measure_value NOT IN ('*', 'NULL', 'nan')
    AND analytical_period = 'recovery'
    AND org_code IS NOT NULL
    GROUP BY org_code, org_name
    ORDER BY avg_recovery_rate DESC
"""
df_q4 = pd.read_sql(q4, conn)
print(df_q4.to_string())

# ── Chart 1: National recovery rate across periods ────────────────────────────
print("\nGenerating charts...")
recovery_national = df_q1[df_q1["measure_id"] == "M192"].copy()
period_order = ["pre_pandemic", "pandemic", "recovery"]
recovery_national["analytical_period"] = pd.Categorical(
    recovery_national["analytical_period"], categories=period_order, ordered=True
)
recovery_national = recovery_national.sort_values("analytical_period")

plt.figure(figsize=(8, 5))
sns.barplot(
    data=recovery_national,
    x="analytical_period",
    y="avg_value",
    hue="analytical_period",
    palette="Blues_d",
    legend=False
)
plt.title("Average National Recovery Rate by Analytical Period")
plt.xlabel("Period")
plt.ylabel("Average Recovery Rate (%)")
plt.ylim(0, 100)
plt.tight_layout()
plt.savefig(f"{OUTPUT_PATH}/national_recovery_rate.png", dpi=150)
plt.close()
print("Saved national_recovery_rate.png")

# ── Chart 2: Deprivation decile vs recovery rate (pandemic period) ────────────
df_q3_pandemic = df_q3[df_q3["analytical_period"] == "pandemic"].copy()

plt.figure(figsize=(10, 5))
sns.barplot(
    data=df_q3_pandemic,
    x="deprivation_decile",
    y="avg_recovery_rate",
    hue="deprivation_decile",
    palette="RdYlGn_r",
    legend=False
)
plt.title("Recovery Rate by Deprivation Decile (Pandemic Period)")
plt.xlabel("Deprivation Decile (1 = Least Deprived, 10 = Most Deprived)")
plt.ylabel("Average Recovery Rate (%)")
plt.ylim(0, 100)
plt.tight_layout()
plt.savefig(f"{OUTPUT_PATH}/deprivation_vs_recovery.png", dpi=150)
plt.close()
print("Saved deprivation_vs_recovery.png")

conn.close()
print("\nExploratory analysis complete.")