import pandas as pd
import sqlite3
import os

# ── Config ───────────────────────────────────────────────────────────────────
DB_PATH = "data/nhs_mental_health.db"
LOOKUP_PATH = "data/reference/lsoa_ccg_lad_lookup.csv"  
IMD_PATH = "data/reference/imd2019_lad.xlsx"             

def integrate_imd():

    # ── Step 1: Load LSOA to CCG to LAD lookup ───────────────────────────────
    print("Loading CCG to LAD lookup...")
    lookup = pd.read_csv(LOOKUP_PATH, low_memory=False)

    # Keep only CCG and LAD columns, drop LSOA level detail
    ccg_lad = lookup[["CCG19CD", "CCG19CDH", "LAD19CD", "LAD19NM"]].drop_duplicates()
    print(f"Unique CCG to LAD mappings: {len(ccg_lad)}")

    # ── Step 2: Load IMD 2019 ─────────────────────────────────────────────────
    print("Loading IMD 2019...")
    imd = pd.read_excel(IMD_PATH, sheet_name="IMD")
    imd.columns = imd.columns.str.strip()
    

    # Keep only what we need
    imd = imd[[
        "Local Authority District code (2019)",
        "Local Authority District name (2019)",
        "IMD - Average score",
        "IMD - Rank of average score"
    ]].copy()

    imd = imd.rename(columns={
        "Local Authority District code (2019)": "LAD19CD",
        "Local Authority District name (2019)": "LAD19NM_imd",
        "IMD - Average score": "imd_average_score",
        "IMD - Rank of average score": "imd_rank"
    })

    print(f"LADs in IMD file: {len(imd)}")

    # ── Step 3: Join lookup to IMD ────────────────────────────────────────────
    print("Joining CCG lookup to IMD scores...")
    ccg_imd = ccg_lad.merge(imd, on="LAD19CD", how="left")

    # ── Step 4: Aggregate to CCG level ───────────────────────────────────────
    # A CCG can span multiple LADs so we average the IMD score across LADs
    ccg_imd_agg = ccg_imd.groupby(["CCG19CD", "CCG19CDH"]).agg(
        imd_average_score=("imd_average_score", "mean"),
        imd_rank=("imd_rank", "mean"),
        lad_count=("LAD19CD", "count")
    ).reset_index()

    # ── Step 5: Assign deprivation decile ─────────────────────────────────────
    ccg_imd_agg["deprivation_decile"] = pd.qcut(
        ccg_imd_agg["imd_average_score"],
        q=10,
        labels=False
    ) + 1  # 1 = least deprived, 10 = most deprived

    print(f"CCGs with deprivation scores: {len(ccg_imd_agg)}")
    print(ccg_imd_agg["deprivation_decile"].value_counts().sort_index())

    # ── Step 6: Save to SQLite ────────────────────────────────────────────────
    conn = sqlite3.connect(DB_PATH)
    ccg_imd_agg.to_sql("ccg_deprivation", conn, if_exists="replace", index=False)
    conn.close()

    print("\nIMD integration complete. ccg_deprivation table saved to database.")
    print(ccg_imd_agg.head(10).to_string())

if __name__ == "__main__":
    integrate_imd()