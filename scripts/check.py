import sqlite3
import pandas as pd

conn = sqlite3.connect("data/nhs_mental_health.db")

df = pd.read_sql("""
    SELECT analytical_period, measure_id, measure_name, COUNT(*) as rows 
    FROM talking_therapies 
    GROUP BY analytical_period, measure_id, measure_name
    ORDER BY analytical_period, measure_id
""", conn)

print("\nDuplicate check:")
print(pd.read_sql("""
    SELECT period_start, org_code, measure_id, COUNT(*) as cnt
    FROM talking_therapies
    GROUP BY period_start, org_code, measure_id
    HAVING cnt > 1
    ORDER BY cnt DESC
    LIMIT 20
""", conn))

print("\nRecovery period months:")
print(pd.read_sql("""
    SELECT period_start, COUNT(*) as rows
    FROM talking_therapies
    WHERE analytical_period = 'recovery'
    GROUP BY period_start
    ORDER BY period_start
""", conn))
print(df.to_string())
conn.close()