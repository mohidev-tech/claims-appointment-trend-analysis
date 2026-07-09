"""
generate_data.py — Synthetic healthcare claims & appointment trend dataset.

Produces a reproducible, realistic dataset for the Claims and Appointment
Trend Analysis dashboard:

  data/appointments_fact.csv  month x department x service_category x appointment_status
  data/claims_fact.csv        month x department x claim_type x claim_status
  dashboard/data.js           pre-aggregated JSON consumed by the dashboard

All randomness is seeded (SEED=42) so the numbers are identical on every run,
which is what makes dashboard totals reconcile exactly to the SQL outputs.
"""
import json
import os
import numpy as np
import pandas as pd

SEED = 42
rng = np.random.default_rng(SEED)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
DASH = os.path.join(ROOT, "dashboard")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DASH, exist_ok=True)

# ---- dimensions -------------------------------------------------------------
MONTHS = pd.period_range("2024-01", "2025-06", freq="M").astype(str).tolist()
DEPARTMENTS = ["Cardiology", "Orthopedics", "Pediatrics", "Radiology",
               "Oncology", "General Surgery", "Neurology"]
SERVICE_CATEGORIES = ["Outpatient", "Inpatient", "Diagnostic", "Emergency", "Elective"]
CLAIM_TYPES = ["Professional", "Facility", "Pharmacy", "Lab", "Imaging"]
CLAIM_STATUSES = ["Submitted", "In Review", "Approved", "Denied", "Paid"]
APPOINTMENT_STATUSES = ["Completed", "Cancelled", "No-Show"]
AGING_BUCKETS = ["0-30", "31-60", "61-90", "90+"]

# relative appointment volume weight per department (latest-month scale)
DEPT_SCALE = {
    "Cardiology": 1.00, "Orthopedics": 0.92, "Pediatrics": 1.18,
    "Radiology": 1.05, "Oncology": 0.66, "General Surgery": 0.58,
    "Neurology": 0.71,
}
# appointment volume mix across service categories (sums to 1)
SVC_MIX = {"Outpatient": 0.40, "Inpatient": 0.14, "Diagnostic": 0.24,
           "Emergency": 0.10, "Elective": 0.12}
# base appointment-status split
STATUS_BASE = {"Completed": 0.78, "Cancelled": 0.15, "No-Show": 0.07}

# claim-type mix and average billed amount per claim type ($)
CLAIM_TYPE_MIX = {"Professional": 0.34, "Facility": 0.24, "Pharmacy": 0.16,
                  "Lab": 0.14, "Imaging": 0.12}
CLAIM_TYPE_AMT = {"Professional": 480, "Facility": 3200, "Pharmacy": 210,
                  "Lab": 145, "Imaging": 720}
# claim-status distribution (sums to 1) — most claims end Paid/Approved
CLAIM_STATUS_MIX = {"Submitted": 0.10, "In Review": 0.14, "Approved": 0.18,
                    "Denied": 0.11, "Paid": 0.47}
# base processing days by claim status
STATUS_PROC_DAYS = {"Submitted": 6, "In Review": 24, "Approved": 18,
                    "Denied": 41, "Paid": 22}
# aging-bucket weighting per claim status (older buckets for Denied/In Review)
AGING_BY_STATUS = {
    "Submitted":  [0.82, 0.13, 0.04, 0.01],
    "In Review":  [0.34, 0.31, 0.22, 0.13],
    "Approved":   [0.68, 0.21, 0.08, 0.03],
    "Denied":     [0.18, 0.27, 0.29, 0.26],
    "Paid":       [0.86, 0.10, 0.03, 0.01],
}


def winter_boost(m_idx):
    """More cancellations in winter months (Dec-Feb) — cancellation seasonality."""
    month_of_year = int(MONTHS[m_idx][5:7])
    if month_of_year in (12, 1, 2):
        return 1.35
    if month_of_year in (11, 3):
        return 1.15
    if month_of_year in (6, 7, 8):
        return 0.90
    return 1.0


def volume_trend(m_idx):
    """Slow upward appointment-volume trend across the 18 months."""
    return 1.0 + 0.14 * (m_idx / 17)


def processing_trend(m_idx):
    """Processing days drift upward slightly over time (a growing bottleneck)."""
    return 1.0 + 0.22 * (m_idx / 17)


# ---- appointments fact ------------------------------------------------------
appt_rows = []
for mi, month in enumerate(MONTHS):
    vtrend = volume_trend(mi)
    wboost = winter_boost(mi)
    for dept in DEPARTMENTS:
        for svc in SERVICE_CATEGORIES:
            base = 640 * DEPT_SCALE[dept] * SVC_MIX[svc] * vtrend
            base *= rng.uniform(0.93, 1.07)
            # seasonal shift toward cancellations in winter
            cancel = STATUS_BASE["Cancelled"] * wboost * rng.uniform(0.92, 1.08)
            noshow = STATUS_BASE["No-Show"] * (1.0 + 0.4 * (wboost - 1.0)) * rng.uniform(0.9, 1.1)
            cancel = min(cancel, 0.32)
            noshow = min(noshow, 0.16)
            completed = max(1.0 - cancel - noshow, 0.4)
            split = {"Completed": completed, "Cancelled": cancel, "No-Show": noshow}
            for status in APPOINTMENT_STATUSES:
                n = int(round(base * split[status]))
                if n <= 0:
                    continue
                # lead time: longer for elective/completed, short for emergency
                lead = 12.0
                if svc == "Emergency":
                    lead = 1.5
                elif svc == "Elective":
                    lead = 28.0
                elif svc == "Diagnostic":
                    lead = 9.0
                if status == "Cancelled":
                    lead *= 1.18
                elif status == "No-Show":
                    lead *= 1.30
                lead *= rng.uniform(0.85, 1.15)
                appt_rows.append({
                    "month": month, "department": dept, "service_category": svc,
                    "appointment_status": status,
                    "appointments": n,
                    "avg_lead_time_days": round(float(lead), 1),
                })

appts = pd.DataFrame(appt_rows)
appts.to_csv(os.path.join(DATA, "appointments_fact.csv"), index=False)
print(f"appointments_fact.csv -> {len(appts):,} rows")

# ---- claims fact ------------------------------------------------------------
claim_rows = []
for mi, month in enumerate(MONTHS):
    vtrend = volume_trend(mi)
    ptrend = processing_trend(mi)
    for dept in DEPARTMENTS:
        for ctype in CLAIM_TYPES:
            base = 300 * DEPT_SCALE[dept] * CLAIM_TYPE_MIX[ctype] * vtrend
            base *= rng.uniform(0.92, 1.08)
            for status in CLAIM_STATUSES:
                n = int(round(base * CLAIM_STATUS_MIX[status] * rng.uniform(0.9, 1.1)))
                if n <= 0:
                    continue
                amt = n * CLAIM_TYPE_AMT[ctype] * rng.uniform(0.85, 1.15)
                proc = STATUS_PROC_DAYS[status] * ptrend * rng.uniform(0.88, 1.12)
                # split n across aging buckets by status weighting
                w = np.array(AGING_BY_STATUS[status], dtype=float)
                w = w / w.sum()
                counts = np.floor(w * n).astype(int)
                # distribute the rounding remainder to the largest-weight buckets
                rem = n - int(counts.sum())
                for j in np.argsort(-w)[:rem]:
                    counts[j] += 1
                claim_rows.append({
                    "month": month, "department": dept, "claim_type": ctype,
                    "claim_status": status,
                    "claim_count": int(n),
                    "claim_amount": round(float(amt), 2),
                    "avg_processing_days": round(float(proc), 1),
                    "aging_0_30": int(counts[0]),
                    "aging_31_60": int(counts[1]),
                    "aging_61_90": int(counts[2]),
                    "aging_90_plus": int(counts[3]),
                })

claims = pd.DataFrame(claim_rows)
claims.to_csv(os.path.join(DATA, "claims_fact.csv"), index=False)
print(f"claims_fact.csv       -> {len(claims):,} rows")

# ---- pre-aggregated dashboard payload --------------------------------------
latest = MONTHS[-1]
payload = {
    "meta": {
        "generated_seed": SEED, "latest_month": latest,
        "months": MONTHS, "departments": DEPARTMENTS,
        "service_categories": SERVICE_CATEGORIES, "claim_types": CLAIM_TYPES,
        "claim_statuses": CLAIM_STATUSES, "appointment_statuses": APPOINTMENT_STATUSES,
        "aging_buckets": AGING_BUCKETS,
    },
    "appts": appts.to_dict(orient="records"),
    "claims": claims.to_dict(orient="records"),
}
with open(os.path.join(DASH, "data.js"), "w", encoding="utf-8") as f:
    f.write("/* auto-generated by data/generate_data.py — do not edit by hand */\n")
    f.write("window.DATA = ")
    json.dump(payload, f, separators=(",", ":"))
    f.write(";\n")
print(f"dashboard/data.js -> appts={len(appts):,}, claims={len(claims):,}")
print("done.")
