import pandas as pd
import sqlite3
import os
import glob

# ── Config ───────────────────────────────────────────────────────────────────
RAW_DATA_PATH = "data/raw"
DB_PATH = "data/nhs_mental_health.db"

TARGET_MEASURES = ["M001", "M053", "M055", "M076", "M186", "M192", "M195"]

# ── Date parser ───────────────────────────────────────────────────────────────
def parse_date(val):
    if pd.isnull(val):
        return None
    val = str(val).strip()
    for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S", "%b-%y", "%B-%y"]:
        try:
            return pd.to_datetime(val, format=fmt).strftime("%Y-%m-%d")
        except:
            continue
    return None

# ── Format B: Long format reader ─────────────────────────────────────────────
def read_long_format(filepath):
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".xlsx":
        df = pd.read_excel(filepath)
    else:
        df = pd.read_csv(filepath, low_memory=False)

    df = df[df["MEASURE_ID"].isin(TARGET_MEASURES)]

    if "ORG_CODE1" in df.columns:
        df = df.rename(columns={
            "REPORTING_PERIOD_START": "period_start",
            "REPORTING_PERIOD_END": "period_end",
            "GROUP_TYPE": "group_type",
            "ORG_CODE1": "org_code",
            "ORG_NAME1": "org_name",
            "MEASURE_ID": "measure_id",
            "MEASURE_NAME": "measure_name",
            "MEASURE_VALUE": "measure_value"
        })
    else:
        df = df.rename(columns={
            "REPORTING_PERIOD_START": "period_start",
            "REPORTING_PERIOD_END": "period_end",
            "GROUP_TYPE": "group_type",
            "ORG_CODE": "org_code",
            "ORG_NAME": "org_name",
            "MEASURE_ID": "measure_id",
            "MEASURE_NAME": "measure_name",
            "MEASURE_VALUE": "measure_value"
        })

    df["period_start"] = df["period_start"].apply(parse_date)

    cols = ["period_start", "period_end", "group_type",
            "org_code", "org_name", "measure_id",
            "measure_name", "measure_value"]

    return df[[c for c in cols if c in df.columns]]


# ── Format A: Wide format reader ─────────────────────────────────────────────
def read_wide_format(filepath):
    df = pd.read_excel(filepath, sheet_name="Table 1", header=7)
    df.columns = df.columns.str.strip()

    measure_map = {
        "Referrals Received": ("M001", "Count_ReferralsReceived"),
        "First Treatment within 6 weeks Finished a Course of Treatment": ("M053", "Percentage_FirstTreatment6WeeksFinishedCourseTreatment"),
        "First Treatment within 18 weeks Finished a Course of Treatment": ("M055", "Percentage_FirstTreatment18WeeksFinishedCourseTreatment"),
        "Finished a Course of Treatment": ("M076", "Count_FinishedCourseTreatment"),
        "Improvement rate": ("M186", "Percentage_Improvement"),
        "Recovery rate": ("M192", "Percentage_Recovery"),
        "Reliable Recovery rate": ("M195", "Percentage_ReliableRecovery"),
    }

    rows = []
    for col, (measure_id, measure_name) in measure_map.items():
        if col in df.columns:
            temp = df[["CCG Code", "CCG Name", "Group Type", "Month / Year"]].copy()
            temp["measure_id"] = measure_id
            temp["measure_name"] = measure_name
            temp["measure_value"] = df[col]
            temp = temp.rename(columns={
                "CCG Code": "org_code",
                "CCG Name": "org_name",
                "Group Type": "group_type",
                "Month / Year": "period_start"
            })
            temp["period_end"] = None
            temp["period_start"] = temp["period_start"].apply(parse_date)
            rows.append(temp)

    return pd.concat(rows, ignore_index=True)


# ── Analytical period labeller ────────────────────────────────────────────────
def assign_period(date):
    if pd.isnull(date):
        return None
    date = pd.to_datetime(date, format="%Y-%m-%d", errors="coerce")
    if pd.isnull(date):
        return None
    if date < pd.Timestamp("2020-03-01"):
        return "pre_pandemic"
    elif date <= pd.Timestamp("2021-03-31"):
        return "pandemic"
    else:
        return "recovery"


# ── Main ingestion ────────────────────────────────────────────────────────────
def ingest_all():
    all_dfs = []

    # Wide format file
    wide_file = os.path.join(RAW_DATA_PATH, "feb2019_feb2020.xlsx")
    if os.path.exists(wide_file):
        print(f"Reading wide format: {wide_file}")
        df = read_wide_format(wide_file)
        df["source_file"] = "feb2019_feb2020.xlsx"
        all_dfs.append(df)
    else:
        print(f"Wide file not found: {wide_file}")

    # Explicit date ranges per file to avoid overlaps
    file_date_ranges = {
        "mar2020_mar2021": ("2020-03-01", "2021-03-31"),
        "apr2021_apr2022": ("2021-04-01", "2022-04-30"),
        "may2022_may2023": ("2022-05-01", "2023-05-31"),
        "jun2023-jun2024": ("2023-06-01", "2024-06-30"),
        "jul2024-jul2025": ("2024-07-01", "2025-07-31"),
        "apr2025-apr2026": ("2025-08-01", "2026-04-30"),
    }

    # Long format files
    patterns = ["**/*.csv", "**/*.xlsx"]
    for pattern in patterns:
        for filepath in glob.glob(os.path.join(RAW_DATA_PATH, pattern), recursive=True):
            if "feb2019_feb2020" in filepath:
                continue
            print(f"Reading long format: {filepath}")
            try:
                df = read_long_format(filepath)
                df["source_file"] = os.path.basename(filepath)

                # Apply explicit date range filter
                basename = os.path.splitext(os.path.basename(filepath))[0]
                if basename in file_date_ranges:
                    start, end = file_date_ranges[basename]
                    df["period_start_dt"] = pd.to_datetime(
                        df["period_start"], format="%Y-%m-%d", errors="coerce"
                    )
                    df = df[
                        (df["period_start_dt"] >= pd.Timestamp(start)) &
                        (df["period_start_dt"] <= pd.Timestamp(end))
                    ]
                    df = df.drop(columns=["period_start_dt"])

                all_dfs.append(df)
            except Exception as e:
                print(f"Error reading {filepath}: {e}")

    # Combine all
    combined = pd.concat(all_dfs, ignore_index=True)

    # Assign analytical period
    combined["analytical_period"] = combined["period_start"].apply(assign_period)

    # Standardise measure names
    name_map = {
        "Percentage_AccessingServices6WeeksFinishedCourseTreatment": "Percentage_FirstTreatment6WeeksFinishedCourseTreatment",
        "Percentage_AccessingServices18WeeksFinishedCourseTreatment": "Percentage_FirstTreatment18WeeksFinishedCourseTreatment"
    }
    combined["measure_name"] = combined["measure_name"].replace(name_map)

    # Remove duplicates
    combined = combined.drop_duplicates()
    combined["period_start"] = combined["period_start"].astype(str)
    combined["period_end"] = combined["period_end"].astype(str)

    # Load into SQLite
    conn = sqlite3.connect(DB_PATH)
    combined.to_sql("talking_therapies", conn, if_exists="replace", index=False)
    conn.close()

    print(f"\nIngestion complete. {len(combined)} rows loaded into {DB_PATH}")
    print(combined["analytical_period"].value_counts())


if __name__ == "__main__":
    ingest_all()