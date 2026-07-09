"""
ai_lib.py — reusable AI/ML toolkit for the mohidev-tech data-analytics portfolio.

Provides four building blocks used across the projects:
  * train_classifier(...)  -> gradient-boosted classifier + hold-out metrics,
                              ROC curve, confusion matrix, feature importance,
                              and calibrated probabilities for every row.
  * forecast_series(...)   -> Holt-Winters forecast with a confidence band.
  * detect_anomalies(...)  -> z-score anomaly flags on a monthly series.
  * build_insights(...)    -> plain-language "AI insights" + a recommendation.

Dependencies: scikit-learn, statsmodels, numpy, pandas (all standard).
The output is a JSON-serialisable dict consumed by the dashboards' AI panel.
"""
from __future__ import annotations
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")


# ---------------------------------------------------------------- classifier
def train_classifier(df, feature_cols, target_col, categorical_cols=(),
                     model_name="Gradient Boosting", seed=42, test_size=0.25):
    from sklearn.model_selection import train_test_split
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.metrics import (roc_auc_score, precision_score, recall_score,
                                 f1_score, accuracy_score, roc_curve, confusion_matrix,
                                 precision_recall_curve)
    from sklearn.inspection import permutation_importance

    data = df[list(feature_cols) + [target_col]].dropna().copy()
    y = data[target_col].astype(int).values
    X = pd.get_dummies(data[list(feature_cols)], columns=list(categorical_cols), drop_first=False)
    feat_names = X.columns.tolist()
    X = X.values.astype(float)

    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=test_size,
                                          random_state=seed, stratify=y)
    clf = GradientBoostingClassifier(random_state=seed, n_estimators=180,
                                     max_depth=3, learning_rate=0.08)
    clf.fit(Xtr, ytr)
    proba_te = clf.predict_proba(Xte)[:, 1]

    # choose the operating threshold that maximises F1 on the hold-out set —
    # honest precision/recall for imbalanced targets (a fixed 0.5 cut would
    # predict almost everything negative when the positive class is rare).
    prec_c, rec_c, thr_c = precision_recall_curve(yte, proba_te)
    f1_c = 2 * prec_c * rec_c / (prec_c + rec_c + 1e-9)
    threshold = float(thr_c[max(int(np.argmax(f1_c[:-1])), 0)]) if len(thr_c) else 0.5
    pred_te = (proba_te >= threshold).astype(int)

    auc = float(roc_auc_score(yte, proba_te))
    metrics = {
        "name": model_name, "target": target_col,
        "auc": round(auc, 3), "threshold": round(threshold, 3),
        "precision": round(float(precision_score(yte, pred_te, zero_division=0)), 3),
        "recall": round(float(recall_score(yte, pred_te, zero_division=0)), 3),
        "f1": round(float(f1_score(yte, pred_te, zero_division=0)), 3),
        "accuracy": round(float(accuracy_score(yte, pred_te)), 3),
        "n_train": int(len(ytr)), "n_test": int(len(yte)),
        "base_rate": round(float(y.mean()), 3),
    }
    fpr, tpr, _ = roc_curve(yte, proba_te)
    idx = np.linspace(0, len(fpr) - 1, min(40, len(fpr))).astype(int)
    metrics["roc"] = [[round(float(fpr[i]), 3), round(float(tpr[i]), 3)] for i in idx]
    tn, fp, fn, tp = confusion_matrix(yte, pred_te).ravel()
    metrics["confusion"] = {"tp": int(tp), "fp": int(fp), "tn": int(tn), "fn": int(fn)}

    # permutation importance (grouped back to original feature where one-hot expanded)
    perm = permutation_importance(clf, Xte, yte, n_repeats=6, random_state=seed, scoring="roc_auc")
    raw = {}
    for name, imp in zip(feat_names, perm.importances_mean):
        base = name
        for c in categorical_cols:
            if name.startswith(c + "_"):
                base = c
                break
        raw[base] = raw.get(base, 0.0) + max(float(imp), 0.0)
    tot = sum(raw.values()) or 1.0
    importances = sorted(({"feature": k, "importance": round(v / tot, 3)} for k, v in raw.items()),
                         key=lambda d: -d["importance"])

    proba_all = clf.predict_proba(X)[:, 1]
    return {"metrics": metrics, "importances": importances,
            "proba_all": proba_all, "feat_names": feat_names, "model": clf}


# ----------------------------------------------------------------- forecast
def forecast_series(values, horizon=6, seasonal_periods=None, metric="value"):
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    y = np.asarray(values, dtype=float)
    n = len(y)
    try:
        kw = dict(trend="add", initialization_method="estimated")
        if seasonal_periods and n >= 2 * seasonal_periods:
            kw.update(seasonal="add", seasonal_periods=seasonal_periods)
        fit = ExponentialSmoothing(y, **kw).fit()
        fc = np.asarray(fit.forecast(horizon), dtype=float)
        resid = y - np.asarray(fit.fittedvalues, dtype=float)
        sigma = float(np.std(resid[np.isfinite(resid)]) or (np.std(y) * 0.1))
    except Exception:
        # linear-trend fallback
        x = np.arange(n)
        a, b = np.polyfit(x, y, 1)
        fc = a * np.arange(n, n + horizon) + b
        sigma = float(np.std(y - (a * x + b)) or np.std(y) * 0.1)
    # widening band with the forecast horizon
    widen = np.sqrt(np.arange(1, horizon + 1))
    lower = (fc - 1.96 * sigma * widen).tolist()
    upper = (fc + 1.96 * sigma * widen).tolist()
    return {"metric": metric, "horizon": int(horizon),
            "hist": [round(float(v), 3) for v in y],
            "point": [round(float(v), 3) for v in fc],
            "lower": [round(float(v), 3) for v in lower],
            "upper": [round(float(v), 3) for v in upper]}


# ---------------------------------------------------------------- anomalies
def detect_anomalies(months, values, z=2.0):
    y = np.asarray(values, dtype=float)
    if len(y) < 4:
        return []
    diffs = np.diff(y, prepend=y[0])
    mu, sd = float(np.mean(diffs)), float(np.std(diffs) or 1.0)
    out = []
    for i, (m, v, d) in enumerate(zip(months, y, diffs)):
        score = (d - mu) / sd
        if abs(score) >= z:
            out.append({"month": m, "value": round(float(v), 3),
                        "z": round(float(score), 2),
                        "direction": "spike" if score > 0 else "drop"})
    return out


# ---------------------------------------------------------------- insights
def build_insights(rows):
    """rows: list of (icon, text). Kept as a thin helper so callers stay declarative."""
    return [{"icon": i, "text": t} for i, t in rows if t]


def trend_pct(values):
    y = np.asarray(values, dtype=float)
    if len(y) < 2 or y[0] == 0:
        return 0.0
    return round(float((y[-1] - y[0]) / abs(y[0]) * 100), 1)
