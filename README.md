# Post-Pandemic Mental Health Recovery in England
## A Deprivation-Stratified Analysis of NHS Talking Therapies (2019-2026)

### Project Overview
This project investigates whether NHS Talking Therapies (formerly IAPT) recovery rates recovered post-COVID-19, and whether recovery was equitable across deprivation levels and regions in England.

---

### Key Findings
- National recovery rates dropped from **51.8% pre-pandemic** to **50.2% in the recovery period**, suggesting the service has not fully returned to baseline five years after the pandemic began
- **North West England** shows the weakest post-pandemic recovery at 48.9%, while **North East and Yorkshire** leads at 51.2%
- Pre-pandemic recovery rate is the **strongest predictor** of post-pandemic performance (34% feature importance), followed by waiting time performance (32%)
- Deprivation contributes meaningfully to the model (15% feature importance), with more deprived areas showing slightly lower recovery rates during the pandemic period

---

### Tech Stack
- **Python** (Pandas, Scikit-learn, Matplotlib, Seaborn)
- **SQLite** for structured data storage
- **Power BI** for interactive dashboard
- **Streamlit + Claude API** for agentic AI layer
- **NHS England** open data (Talking Therapies monthly publications 2019-2026)
- **IMD 2019** deprivation data (DLUHC)

---

### Project Structure

nhs_mental_health/  
├── data/  
│   ├── raw/          # NHS Talking Therapies source files (not tracked)  
│   └── reference/    # IMD and geography lookup files (not tracked)  
├── scripts/  
│   ├── ingest.py         # Data ingestion pipeline  
│   ├── integrate_imd.py  # Deprivation data integration  
│   ├── explore.py        # Exploratory analysis and charts  
│   ├── model.py          # Predictive model (Gradient Boosting, ROC-AUC 0.69)  
│   └── check.py          # Data quality checks  
├── outputs/  
│   ├── charts/           # Generated visualisations  
│   └── ccg_risk_scores.csv  # CCG-level risk predictions  
└── README.md

---

### Methodology

**Data**
Seven annual NHS Talking Therapies publication files covering February 2019 to April 2026, ingested and unified into a SQLite database. Deprivation scores joined via LSOA-to-CCG lookup using IMD 2019.

**Analytical Periods**
- Pre-pandemic: February 2019 to February 2020
- Pandemic: March 2020 to March 2021
- Recovery: April 2021 to April 2026

**Model**
Gradient Boosting classifier predicting which CCGs are at risk of below-average recovery rates in the post-pandemic period. Features include pre-pandemic recovery baseline, waiting time performance, referral volume, and IMD deprivation score.

**Limitation**
The 2022 NHS restructure (CCGs to ICBs) creates a geographic discontinuity that prevents direct deprivation linkage for post-2022 recovery period data. National and regional trends are unaffected.

---

### Data Sources
- [NHS Talking Therapies Statistics](https://www.england.nhs.uk/mental-health/resources/talking-therapies-monthly-statistics/)
- [English Indices of Deprivation 2019](https://www.gov.uk/government/statistics/english-indices-of-deprivation-2019)
- [LSOA to CCG Lookup 2019](https://geoportal.statistics.gov.uk)

---

### Author
Kehinde Fakeye | MSc Data Science, University of Salford  
[GitHub](https://github.com/aridunnu) | [LinkedIn](https://www.linkedin.com/in/kehindefakeye)
