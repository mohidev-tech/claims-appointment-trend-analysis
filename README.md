# claims-appointment-trend-analysis 📈

**Where the delays are hiding — appointment demand, cancellation behavior, claims status movement and the aging/processing bottlenecks a hospital operations team needs to see.**

[![dashboard](https://img.shields.io/badge/dashboard-live-0369a1)](https://mohidev-tech.github.io/claims-appointment-trend-analysis/dashboard/)
[![built with](https://img.shields.io/badge/built%20with-SQL%20·%20Python%20·%20JS-0369a1)](#run-it-locally)
[![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

> Built to support hospital operations and reporting teams with better visibility into
> **where delays, bottlenecks or unusual trends are occurring** — service demand,
> appointment completion and cancellation patterns, department workload and claims-status
> movement over time.

![Dashboard overview](screenshots/01-overview-full.png)

## What the trend analysis surfaces

| Area | What it shows |
|---|---|
| **Appointment demand** | Volume trend by month, with seasonality |
| **Cancellation behavior** | Completed vs. cancelled vs. no-show over time |
| **Department workload** | Which departments carry the load |
| **Claims status** | Distribution across submitted → in-review → approved / denied / paid |
| **Claims aging** | 0-30 / 31-60 / 61-90 / 90+ day buckets, trended |
| **Processing bottleneck** | Average processing days — rising over the period |

Two signals the data makes obvious:
- **Processing time is drifting up:** 21.9 → 26.7 days across the 18 months — a growing bottleneck.
- **Cancellations are seasonal:** ~20% in Dec–Feb vs. ~13% mid-year.

Filters: **month range · department · service category · claim status**.

## Data flow

```mermaid
flowchart LR
    G["generate_data.py<br/>seeded synthetic data"] --> AP[("appointments_fact.csv<br/>1,890 rows")]
    G --> CL[("claims_fact.csv<br/>3,150 rows")]
    AP --> SQL["analytics_queries.sql<br/>trend · MoM · seasonality · aging"]
    CL --> SQL
    AP --> AGG["pre-aggregated<br/>dashboard/data.js"]
    CL --> AGG
    AGG --> D["interactive dashboard<br/>trends · aging · scorecard"]
    SQL --> V["load_and_validate.py"]
    V -. "totals match" .-> D
```

## Metric definitions

| Measure | Definition |
|---|---|
| **Cancellation rate** | cancelled ÷ total appointments |
| **Completion rate** | completed ÷ total appointments |
| **Claim approval rate** | (approved + paid) ÷ total claims |
| **Avg processing days** | claim-count-weighted processing time |
| **% aged 90+** | claims in the 90+ day aging bucket ÷ total claims |
| **Aging buckets** | 0-30 / 31-60 / 61-90 / 90+ days; buckets sum exactly to claim count |

## Screenshots

**All departments:**
![Overview](screenshots/01-overview-full.png)

**Drill-down — General Surgery (claims aging & processing):**
![Claims aging drill-down](screenshots/02-claims-aging.png)

## Reconciliation (dashboard ↔ SQL)

`python sql/load_and_validate.py`:

```
== KPI SUMMARY (latest month) ==
  month = 2025-06
  total_appointments = 4,389
  cancellation_rate  = 13.44%
  completion_rate    = 79.81%
  total_claims       = 2,067
  approval_rate      = 65.36%
  avg_processing_days= 26.7
  pct_aged_90_plus   = 3.24%
  total_billed       = $2,157,082
```

## Run it locally

```bash
python data/generate_data.py       # (optional) regenerate the seeded data
python sql/load_and_validate.py     # reconcile metrics against SQL
python -m http.server 8791          # then open http://localhost:8791/dashboard/
```

Or open `dashboard/index.html` directly — self-contained, no build or dependencies.

## Repo layout

```
data/
  generate_data.py         seeded generator (SEED=42), seasonality + bottleneck trend
  appointments_fact.csv    month × department × service_category × status
  claims_fact.csv          month × department × claim_type × status (+ aging buckets)
sql/
  analytics_queries.sql    trend / MoM / seasonality / aging SQL
  load_and_validate.py     loads CSVs → SQLite and reconciles
dashboard/
  index.html               the interactive dashboard
  data.js                  pre-aggregated payload (generated)
  assets/                  dependency-free SVG chart library + theme
screenshots/               rendered proof
```

## Part of Adithya's data-analytics portfolio

| Project | Focus |
|---|---|
| [credit-risk-portfolio-analytics](https://github.com/mohidev-tech/credit-risk-portfolio-analytics) | Banking delinquency, charge-off & risk segmentation |
| [healthcare-operations-dashboard](https://github.com/mohidev-tech/healthcare-operations-dashboard) | Patient volume, utilization & claims ops KPIs |
| [customer-segmentation-churn-analysis](https://github.com/mohidev-tech/customer-segmentation-churn-analysis) | Churn drivers, segmentation & retention watchlist |
| **claims-appointment-trend-analysis** ← *you are here* | Claims aging, cancellation & processing bottlenecks |
| [executive-kpi-reporting-automation](https://github.com/mohidev-tech/executive-kpi-reporting-automation) | Automated multi-team KPI reporting + Excel pipeline |

*Skills: SQL aggregation, healthcare operations & claims analytics, trend/seasonality analysis, data cleaning, dashboard design, business communication.*

*All data is synthetic and reproducible (`SEED = 42`). The dashboard is a self-contained web app that renders anywhere, including live on GitHub Pages.*

## License

MIT — see [LICENSE](LICENSE).
