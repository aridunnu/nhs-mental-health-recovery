import pandas as pd
import sqlite3
import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, roc_auc_score, confusion_matrix
import matplotlib.pyplot as plt
import seaborn as sns
import os

# ── Config ───────────────────────────────────────────────────────────────────
DB_PATH = "data/nhs_mental_health.db"
OUTPUT_PATH = "outputs/charts"
os.makedirs(OUTPUT_PATH, exist_ok=True)

conn = sqlite3.connect(DB_PATH)

# ── Step 1: Build feature set ─────────────────────────────────────────────────
print("Building feature set...")

# Pre-pandemic baseline recovery rate per CCG
pre_pandemic = pd.read_sql("""
    SELECT 
        org_code,
        AVG(CAST(measure_value AS FLOAT)) as pre_pandemic_recovery_rate,
        COUNT(*) as pre_pandemic_months
    FROM talking_therapies
    WHERE measure_id = 'M192'
    AND group_type = 'CCG'
    AND analytical_period = 'pre_pandemic'
    AND measure_value NOT IN ('*', 'NULL', 'nan')
    AND org_code IS NOT NULL
    GROUP BY org_code
    HAVING COUNT(*) >= 6
""", conn)

# Pre-pandemic referral volume per CCG
pre_pandemic_referrals = pd.read_sql("""
    SELECT 
        org_code,
        AVG(CAST(measure_value AS FLOAT)) as pre_pandemic_avg_referrals
    FROM talking_therapies
    WHERE measure_id = 'M001'
    AND group_type = 'CCG'
    AND analytical_period = 'pre_pandemic'
    AND measure_value NOT IN ('*', 'NULL', 'nan')
    AND org_code IS NOT NULL
    GROUP BY org_code
""", conn)

# Pre-pandemic waiting time performance per CCG
pre_pandemic_waiting = pd.read_sql("""
    SELECT 
        org_code,
        AVG(CAST(measure_value AS FLOAT)) as pre_pandemic_waiting_6wks
    FROM talking_therapies
    WHERE measure_id = 'M053'
    AND group_type = 'CCG'
    AND analytical_period = 'pre_pandemic'
    AND measure_value NOT IN ('*', 'NULL', 'nan')
    AND org_code IS NOT NULL
    GROUP BY org_code
""", conn)

# Recovery period average recovery rate per CCG (target variable)
recovery_period = pd.read_sql("""
    SELECT 
        org_code,
        AVG(CAST(measure_value AS FLOAT)) as recovery_period_rate
    FROM talking_therapies
    WHERE measure_id = 'M192'
    AND group_type = 'CCG'
    AND analytical_period = 'recovery'
    AND measure_value NOT IN ('*', 'NULL', 'nan')
    AND org_code IS NOT NULL
    GROUP BY org_code
    HAVING COUNT(*) >= 6
""", conn)

# Deprivation scores
deprivation = pd.read_sql("""
    SELECT CCG19CDH as org_code, imd_average_score, deprivation_decile
    FROM ccg_deprivation
""", conn)

conn.close()

# ── Step 2: Merge features ────────────────────────────────────────────────────
print("Merging features...")
df = pre_pandemic.merge(pre_pandemic_referrals, on="org_code", how="left")
df = df.merge(pre_pandemic_waiting, on="org_code", how="left")
df = df.merge(deprivation, on="org_code", how="left")
df = df.merge(recovery_period, on="org_code", how="inner")

print(f"CCGs with full feature set: {len(df)}")

# ── Step 3: Create target variable ────────────────────────────────────────────
# Binary: 1 = below national average recovery rate in recovery period, 0 = at or above
national_avg = df["recovery_period_rate"].mean()
print(f"National average recovery rate in recovery period: {national_avg:.2f}%")
df["below_average"] = (df["recovery_period_rate"] < national_avg).astype(int)
print(f"CCGs below average: {df['below_average'].sum()}")
print(f"CCGs at or above average: {(df['below_average'] == 0).sum()}")

# ── Step 4: Prepare features ──────────────────────────────────────────────────
features = [
    "pre_pandemic_recovery_rate",
    "pre_pandemic_avg_referrals",
    "pre_pandemic_waiting_6wks",
    "imd_average_score",
    "deprivation_decile"
]

df_model = df[features + ["below_average", "org_code"]].dropna()
print(f"CCGs after dropping nulls: {len(df_model)}")

X = df_model[features]
y = df_model["below_average"]

# ── Step 5: Scale features ────────────────────────────────────────────────────
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# ── Step 6: Train test split ──────────────────────────────────────────────────
X_train, X_test, y_train, y_test = train_test_split(
    X_scaled, y, test_size=0.2, random_state=42, stratify=y
)

# ── Step 7: Train models ──────────────────────────────────────────────────────
models = {
    "Logistic Regression": LogisticRegression(random_state=42, max_iter=1000),
    "Random Forest": RandomForestClassifier(n_estimators=100, random_state=42),
    "Gradient Boosting": GradientBoostingClassifier(n_estimators=100, random_state=42)
}

results = {}
for name, model in models.items():
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]
    roc_auc = roc_auc_score(y_test, y_prob)
    cv_scores = cross_val_score(model, X_scaled, y, cv=5, scoring="roc_auc")
    results[name] = {
        "model": model,
        "roc_auc": roc_auc,
        "cv_mean": cv_scores.mean(),
        "cv_std": cv_scores.std(),
        "y_pred": y_pred,
        "y_prob": y_prob
    }
    print(f"\n{name}")
    print(f"ROC-AUC: {roc_auc:.3f}")
    print(f"CV ROC-AUC: {cv_scores.mean():.3f} (+/- {cv_scores.std():.3f})")
    print(classification_report(y_test, y_pred))

# ── Step 8: Best model feature importance ────────────────────────────────────
best_model_name = max(results, key=lambda x: results[x]["cv_mean"])
print(f"\nBest model: {best_model_name}")
best_model = results[best_model_name]["model"]

if hasattr(best_model, "feature_importances_"):
    importances = pd.DataFrame({
        "feature": features,
        "importance": best_model.feature_importances_
    }).sort_values("importance", ascending=False)
    print(importances.to_string())

    plt.figure(figsize=(8, 5))
    sns.barplot(
        data=importances,
        x="importance",
        y="feature",
        hue="feature",
        palette="Blues_r",
        legend=False
    )
    plt.title(f"Feature Importance ({best_model_name})")
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_PATH}/feature_importance.png", dpi=150)
    plt.close()
    print("Saved feature_importance.png")

# ── Step 9: Risk scores for all CCGs ─────────────────────────────────────────
df_model["risk_score"] = best_model.predict_proba(
    scaler.transform(df_model[features])
)[:, 1]

df_model["risk_category"] = pd.cut(
    df_model["risk_score"],
    bins=[0, 0.33, 0.66, 1.0],
    labels=["Low Risk", "Medium Risk", "High Risk"]
)

risk_output = df_model[["org_code", "risk_score", "risk_category",
                          "pre_pandemic_recovery_rate",
                          "deprivation_decile"]].copy()
risk_output = risk_output.merge(
    df[["org_code", "recovery_period_rate"]], on="org_code", how="left"
)
risk_output = risk_output.sort_values("risk_score", ascending=False)

print("\nTop 20 highest risk CCGs:")
print(risk_output.head(20).to_string())

risk_output.to_csv("outputs/ccg_risk_scores.csv", index=False)
print("\nSaved outputs/ccg_risk_scores.csv")
print("\nPhase 3 complete.")