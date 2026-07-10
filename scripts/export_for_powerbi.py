import pandas as pd
import sqlite3
import os

# ── Config ───────────────────────────────────────────────────────────────────
DB_PATH = "data/nhs_mental_health.db"
EXPORT_PATH = "outputs/powerbi"
os.makedirs(EXPORT_PATH, exist_ok=True)

conn = sqlite3.connect(DB_PATH)

# ── Export 1: National trends over time ──────────────────────────────────────
print("Exporting national trends...")
national_trends = pd.read_sql("""
    SELECT 
        period_start,
        analytical_period,
        measure_id,
        measure_name,
        CAST(measure_value AS FLOAT) as measure_value
    FROM talking_therapies
    WHERE group_type = 'England'
    AND measure_value NOT IN ('*', 'NULL', 'nan')
    AND analytical_period IS NOT NULL
    AND measure_id IN ('M001', 'M053', 'M076', 'M192', 'M195')
    ORDER BY period_start, measure_id
""", conn)
national_trends.to_csv(f"{EXPORT_PATH}/national_trends.csv", index=False)
print(f"Rows: {len(national_trends)}")

# ── Export 2: CCG level recovery rates by period ──────────────────────────────
print("Exporting CCG recovery rates...")
ccg_recovery = pd.read_sql("""
    SELECT 
        analytical_period,
        period_start,
        org_code,
        org_name,
        CAST(measure_value AS FLOAT) as recovery_rate
    FROM talking_therapies
    WHERE measure_id = 'M192'
    AND group_type IN ('CCG', 'SubICB')
    AND measure_value NOT IN ('*', 'NULL', 'nan')
    AND analytical_period IS NOT NULL
    AND org_code IS NOT NULL
    ORDER BY period_start, org_code
""", conn)
ccg_recovery.to_csv(f"{EXPORT_PATH}/ccg_recovery.csv", index=False)
print(f"Rows: {len(ccg_recovery)}")

# ── Export 3: Regional recovery rates ─────────────────────────────────────────
print("Exporting regional recovery rates...")
regional = pd.read_sql("""
    SELECT 
        period_start,
        analytical_period,
        org_code,
        org_name,
        CAST(measure_value AS FLOAT) as recovery_rate
    FROM talking_therapies
    WHERE measure_id = 'M192'
    AND group_type = 'CommissioningRegion'
    AND measure_value NOT IN ('*', 'NULL', 'nan')
    AND analytical_period IS NOT NULL
    AND org_code NOT IN ('InvalidRegionCode')
    ORDER BY period_start, org_code
""", conn)
regional.to_csv(f"{EXPORT_PATH}/regional_recovery.csv", index=False)
print(f"Rows: {len(regional)}")

# ── Export 4: Deprivation vs recovery ─────────────────────────────────────────
print("Exporting deprivation analysis...")
deprivation = pd.read_sql("""
    SELECT 
        t.analytical_period,
        t.period_start,
        t.org_code,
        t.org_name,
        CAST(t.measure_value AS FLOAT) as recovery_rate,
        d.imd_average_score,
        d.deprivation_decile
    FROM talking_therapies t
    JOIN ccg_deprivation d ON t.org_code = d.CCG19CDH
    WHERE t.measure_id = 'M192'
    AND t.measure_value NOT IN ('*', 'NULL', 'nan')
    AND t.analytical_period IS NOT NULL
    AND d.deprivation_decile IS NOT NULL
    ORDER BY t.period_start, t.org_code
""", conn)
deprivation.to_csv(f"{EXPORT_PATH}/deprivation_recovery.csv", index=False)
print(f"Rows: {len(deprivation)}")

# ── Export 5: CCG risk scores from model ──────────────────────────────────────
print("Exporting risk scores...")
risk_scores = pd.read_csv("outputs/ccg_risk_scores.csv")
risk_scores.to_csv(f"{EXPORT_PATH}/ccg_risk_scores.csv", index=False)
print(f"Rows: {len(risk_scores)}")

# ── Export 6: Period summary KPIs ─────────────────────────────────────────────
print("Exporting period KPIs...")
kpis = pd.read_sql("""
    SELECT 
        analytical_period,
        measure_id,
        measure_name,
        AVG(CAST(measure_value AS FLOAT)) as avg_value,
        MIN(CAST(measure_value AS FLOAT)) as min_value,
        MAX(CAST(measure_value AS FLOAT)) as max_value,
        COUNT(DISTINCT period_start) as months_covered
    FROM talking_therapies
    WHERE group_type = 'England'
    AND measure_value NOT IN ('*', 'NULL', 'nan')
    AND analytical_period IS NOT NULL
    GROUP BY analytical_period, measure_id, measure_name
    ORDER BY measure_id, analytical_period
""", conn)
kpis.to_csv(f"{EXPORT_PATH}/period_kpis.csv", index=False)
print(f"Rows: {len(kpis)}")

# Export 7: Regional trends across all periods
print("Exporting regional trends all periods...")
regional_all = pd.read_sql("""
    SELECT 
        period_start,
        analytical_period,
        org_code,
        org_name,
        CAST(measure_value AS FLOAT) as recovery_rate
    FROM talking_therapies
    WHERE measure_id = 'M192'
    AND group_type = 'CommissioningRegion'
    AND measure_value NOT IN ('*', 'NULL', 'nan')
    AND analytical_period IS NOT NULL
    AND org_code NOT IN ('InvalidRegionCode')
    ORDER BY period_start, org_code
""", conn)
regional_all.to_csv(f"{EXPORT_PATH}/regional_all_periods.csv", index=False)
print(f"Rows: {len(regional_all)}")

# Export 8: CCG average recovery rates by period for Top/Bottom charts
print("Exporting CCG averages by period...")
ccg_avg = pd.read_sql("""
    SELECT 
        analytical_period,
        org_code,
        org_name,
        AVG(CAST(measure_value AS FLOAT)) as avg_recovery_rate,
        COUNT(DISTINCT period_start) as months
    FROM talking_therapies
    WHERE measure_id = 'M192'
    AND group_type IN ('CCG', 'SubICB')
    AND measure_value NOT IN ('*', 'NULL', 'nan')
    AND analytical_period IS NOT NULL
    AND org_code IS NOT NULL
    AND org_code NOT IN ('InvalidCode')
    GROUP BY analytical_period, org_code, org_name
    HAVING COUNT(DISTINCT period_start) >= 3
    ORDER BY analytical_period, avg_recovery_rate DESC
""", conn)
ccg_avg.to_csv(f"{EXPORT_PATH}/ccg_avg_by_period.csv", index=False)
print(f"Rows: {len(ccg_avg)}")

conn.close()
print("\nAll exports complete. Files saved to outputs/powerbi/")

