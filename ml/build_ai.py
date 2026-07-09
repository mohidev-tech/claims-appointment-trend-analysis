"""
build_ai.py — trains the claim-denial model and produces the AI layer for the dashboard.

Outputs:
  data/claims_detail.csv         seeded row-level training data for the denial model
  ml/model_metrics.json          hold-out metrics (AUC, precision, recall, ...)
  ml/figures/roc_curve.png       ROC curve
  ml/figures/feature_importance.png
  ml/figures/confusion_matrix.png
  dashboard/ai.js                window.AI payload consumed by the dashboard

The classifier is a gradient-boosted model predicting whether a claim is denied
from its amount, submission lag, provider history, coding complexity and
categorical context. A Holt-Winters forecast projects the rising average
processing-days series (the project's known bottleneck), a z-score detector
flags anomalous months, and the whole thing feeds the "AI insights" panel.

Run: python ml/build_ai.py
"""
import json
import os
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import ai_lib

ACCENT = "#0369a1"
FIG = os.path.join(HERE, "figures")
os.makedirs(FIG, exist_ok=True)

DEPARTMENTS = ["Cardiology", "Orthopedics", "Pediatrics", "Radiology",
               "Oncology", "General Surgery", "Neurology"]
CLAIM_TYPES = ["Professional", "Facility", "Pharmacy", "Lab", "Imaging"]
SERVICE_CATEGORIES = ["Outpatient", "Inpatient", "Diagnostic", "Emergency", "Elective"]
COMPLEXITY = ["Low", "Med", "High"]
MONTHS = [f"2024-{m:02d}" for m in range(1, 13)] + [f"2025-{m:02d}" for m in range(1, 7)]

# ---------------------------------------------------------------------------
# The dashboard's claims_fact.csv is AGGREGATED (month × dept × type × status),
# so we synthesise a seeded ROW-LEVEL dataset here to train the denial model on.
# ---------------------------------------------------------------------------
def build_claims_detail(n=9000, seed=42):
    rng = np.random.default_rng(seed)
    dept = rng.choice(DEPARTMENTS, n)
    ctype = rng.choice(CLAIM_TYPES, n, p=[0.30, 0.24, 0.16, 0.16, 0.14])
    svc = rng.choice(SERVICE_CATEGORIES, n, p=[0.42, 0.18, 0.20, 0.10, 0.10])
    complexity = rng.choice(COMPLEXITY, n, p=[0.45, 0.35, 0.20])
    claim_amount = np.round(rng.lognormal(mean=7.6, sigma=0.7, size=n), 2)
    submission_lag = rng.integers(0, 46, n)                       # 0-45 days
    prior_denials = rng.integers(0, 9, n)                         # 0-8
    month = rng.choice(MONTHS, n)

    # ---- denial probability: realistic risk drivers --------------------------
    z = -4.30
    z = z + 0.55 * (claim_amount > 4000)                         # expensive claims
    z = z + 0.65 * (claim_amount > 9000)
    z = z + 0.045 * submission_lag                                # late submission
    z = z + 0.28 * prior_denials                                  # provider history
    complexity_w = {"Low": 0.0, "Med": 0.45, "High": 1.05}
    z = z + np.array([complexity_w[c] for c in complexity])       # coding complexity
    ctype_w = {"Professional": 0.0, "Facility": 0.35, "Pharmacy": 0.75,
               "Lab": -0.15, "Imaging": 0.55}
    z = z + np.array([ctype_w[c] for c in ctype])                 # certain claim types
    svc_w = {"Outpatient": 0.0, "Inpatient": 0.30, "Diagnostic": 0.10,
             "Emergency": 0.45, "Elective": -0.10}
    z = z + np.array([svc_w[s] for s in svc])
    z = z + rng.normal(0, 0.35, n)                                # idiosyncratic noise
    prob = 1.0 / (1.0 + np.exp(-z))
    denied = (rng.random(n) < prob).astype(int)

    df = pd.DataFrame({
        "department": dept, "claim_type": ctype, "service_category": svc,
        "claim_amount": claim_amount, "submission_lag_days": submission_lag,
        "provider_prior_denials": prior_denials, "coding_complexity": complexity,
        "month": month, "denied": denied,
    })
    return df


detail = build_claims_detail()
detail.to_csv(os.path.join(ROOT, "data", "claims_detail.csv"), index=False)
print(f"claims_detail.csv: {len(detail):,} rows, denial base rate {detail['denied'].mean():.3f}")

# ---- classifier ------------------------------------------------------------
FEATURES = ["claim_amount", "submission_lag_days", "provider_prior_denials",
            "coding_complexity", "department", "claim_type", "service_category"]
CATS = ["coding_complexity", "department", "claim_type", "service_category"]

res = ai_lib.train_classifier(detail, FEATURES, "denied", categorical_cols=CATS,
                              model_name="Claim denial — Gradient Boosting")
M = res["metrics"]
print(f"Denial model AUC={M['auc']}  precision={M['precision']}  recall={M['recall']}  "
      f"F1={M['f1']}  (n_test={M['n_test']})")

# ---- forecast: monthly claim-count-weighted avg processing days ------------
fact = pd.read_csv(os.path.join(ROOT, "data", "claims_fact.csv"))
proc = (fact.groupby("month")
        .apply(lambda x: (x["avg_processing_days"] * x["claim_count"]).sum() / x["claim_count"].sum())
        .reindex(MONTHS))
hist_labels = proc.index.tolist()
proc_series = [round(float(v), 3) for v in proc.values]

fc = ai_lib.forecast_series(proc_series, horizon=6, metric="avg processing days")


def next_months(last_ym, k):
    y, m = map(int, last_ym.split("-"))
    out = []
    for _ in range(k):
        m += 1
        if m > 12:
            m = 1; y += 1
        out.append(f"{y:04d}-{m:02d}")
    return out


future_labels = next_months(hist_labels[-1], 6)
forecast = {
    "metric": fc["metric"], "histLabels": hist_labels, "hist": fc["hist"],
    "futureLabels": future_labels, "point": fc["point"],
    "lower": fc["lower"], "upper": fc["upper"],
}

# ---- anomaly detection on the processing-days series -----------------------
anomalies = ai_lib.detect_anomalies(hist_labels, proc_series)

# ---- figures ---------------------------------------------------------------
plt.rcParams.update({"figure.dpi": 150, "font.size": 10, "axes.spines.top": False, "axes.spines.right": False})

roc = np.array(M["roc"])
plt.figure(figsize=(5, 4))
plt.plot(roc[:, 0], roc[:, 1], color=ACCENT, lw=2.4, label=f"Model (AUC={M['auc']})")
plt.plot([0, 1], [0, 1], "--", color="#9ca3af", lw=1.2, label="Random")
plt.xlabel("False positive rate"); plt.ylabel("True positive rate")
plt.title("Claim-denial model — ROC curve"); plt.legend(loc="lower right")
plt.tight_layout(); plt.savefig(os.path.join(FIG, "roc_curve.png"), bbox_inches="tight"); plt.close()

imp = res["importances"][:10][::-1]
plt.figure(figsize=(6, 4))
plt.barh([d["feature"].replace("_", " ") for d in imp], [d["importance"] for d in imp], color=ACCENT)
plt.xlabel("Permutation importance (share)"); plt.title("Denial drivers — model feature importance")
plt.tight_layout(); plt.savefig(os.path.join(FIG, "feature_importance.png"), bbox_inches="tight"); plt.close()

cm = M["confusion"]
mat = np.array([[cm["tn"], cm["fp"]], [cm["fn"], cm["tp"]]])
plt.figure(figsize=(4.2, 3.8))
plt.imshow(mat, cmap="Blues")
for (i, j), v in np.ndenumerate(mat):
    plt.text(j, i, f"{v:,}", ha="center", va="center",
             color="white" if v > mat.max() * 0.5 else "#333", fontweight="bold")
plt.xticks([0, 1], ["Pred: paid", "Pred: denied"]); plt.yticks([0, 1], ["Actual: paid", "Actual: denied"])
plt.title("Confusion matrix (hold-out)")
plt.tight_layout(); plt.savefig(os.path.join(FIG, "confusion_matrix.png"), bbox_inches="tight"); plt.close()

# ---- insights + recommendation ---------------------------------------------
top_drivers = ", ".join(d["feature"].replace("_", " ") for d in res["importances"][:3])
drift = ai_lib.trend_pct(proc_series)          # % change across the history
proj_drift = ai_lib.trend_pct([proc_series[-1]] + fc["point"])   # forecast slope from last actual
last_proc = proc_series[-1]
end_fc = fc["point"][-1]
if anomalies:
    a = anomalies[0]
    anom_txt = (f"A z-score scan flags <b>{len(anomalies)} anomalous month(s)</b> in processing time — "
                f"notably a {a['direction']} at <b>{a['month']}</b> ({a['value']:.1f} d, z={a['z']}).")
else:
    anom_txt = ("A z-score scan of month-over-month processing time finds <b>no abrupt anomalies</b> — "
                "the deterioration is a steady structural drift, not a one-off spike, which makes it a planning problem.")

insights = ai_lib.build_insights([
    ("🎯", f"The denial classifier separates denied from paid claims with an <b>AUC of {M['auc']}</b> on a held-out {M['n_test']:,}-claim test set (precision {M['precision']}, recall {M['recall']})."),
    ("🔑", f"The strongest denial drivers are <b>{top_drivers}</b> — high claim amounts, long submission lags and prior-denial history dominate the risk."),
    ("📈", f"Average processing days is on a <b>rising {drift:+.1f}% trend</b> ({proc_series[0]:.1f} → {last_proc:.1f} d) and the 6-month forecast extends it to <b>{end_fc:.1f} d</b> ({proj_drift:+.1f}% further) — the growing bottleneck."),
    ("⚠️", anom_txt),
    ("📃", f"Denials run at a <b>{M['base_rate']*100:.1f}% base rate</b>; scoring every submission lets billing scrub the high-risk tail before it is filed."),
])
recommendation = (
    "Stand up pre-submission scrubbing for the highest-scoring claims (high amount, long lag, "
    "High-complexity coding, prior-denial providers) to cut first-pass denials, and add processing "
    "capacity / triage to arrest the "
    f"{proj_drift:+.1f}% projected drift toward {end_fc:.1f}-day claim processing; re-score weekly."
)

AI = {
    "model": M, "importances": res["importances"],
    "forecast": forecast, "anomalies": anomalies,
    "insights": insights, "recommendation": recommendation,
    "accent": ACCENT,
}
with open(os.path.join(HERE, "model_metrics.json"), "w", encoding="utf-8") as f:
    json.dump(M, f, indent=2)
with open(os.path.join(ROOT, "dashboard", "ai.js"), "w", encoding="utf-8") as f:
    f.write("/* auto-generated by ml/build_ai.py — claim-denial model + forecast + AI insights */\n")
    f.write("window.AI = ")
    json.dump(AI, f, separators=(",", ":"))
    f.write(";\n")

print(f"forecast: {last_proc:.1f} d -> {end_fc:.1f} d over 6 months ({proj_drift:+.1f}%); anomalies={len(anomalies)}")
print("wrote data/claims_detail.csv, dashboard/ai.js, ml/model_metrics.json, and 3 figures.")
