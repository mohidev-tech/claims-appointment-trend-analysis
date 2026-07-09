# AI-generated executive narrative

_Source: deterministic insight engine over the model metrics in `ml/model_metrics.json`._

- The denial classifier separates denied from paid claims with an <b>AUC of 0.761</b> on a held-out 2,250-claim test set (precision 0.648, recall 0.259).
- The strongest denial drivers are <b>provider prior denials, submission lag days, coding complexity</b> — high claim amounts, long submission lags and prior-denial history dominate the risk.
- Average processing days is on a <b>rising +22.2% trend</b> (21.9 → 26.7 d) and the 6-month forecast extends it to <b>28.5 d</b> (+6.8% further) — the growing bottleneck.
- A z-score scan of month-over-month processing time finds <b>no abrupt anomalies</b> — the deterioration is a steady structural drift, not a one-off spike, which makes it a planning problem.
- Denials run at a <b>25.2% base rate</b>; scoring every submission lets billing scrub the high-risk tail before it is filed.

**Recommended action:** Stand up pre-submission scrubbing for the highest-scoring claims (high amount, long lag, High-complexity coding, prior-denial providers) to cut first-pass denials, and add processing capacity / triage to arrest the +6.8% projected drift toward 28.5-day claim processing; re-score weekly.
