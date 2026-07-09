-- ============================================================================
-- Claims and Appointment Trend Analysis — analytical SQL
-- Dialect: ANSI-ish, runs as-is on SQLite (see sql/load_and_validate.py).
-- Source tables:
--   appointments_fact(month, department, service_category, appointment_status,
--                appointments, avg_lead_time_days)
--       grain: month x department x service_category x appointment_status
--   claims_fact(month, department, claim_type, claim_status, claim_count,
--                claim_amount, avg_processing_days, aging_0_30, aging_31_60,
--                aging_61_90, aging_90_plus)
--       grain: month x department x claim_type x claim_status
-- Note: the four aging_* columns sum to claim_count for every row.
-- ============================================================================

-- 1. Appointment volume trend + month-over-month change -----------------------
--    Feeds the "Appointment volume trend" line chart and the appointments KPI.
WITH monthly AS (
    SELECT month, SUM(appointments) AS appointments
    FROM appointments_fact
    GROUP BY month
)
SELECT month,
       appointments,
       appointments - LAG(appointments) OVER (ORDER BY month)          AS mom_change,
       ROUND(100.0 * (appointments - LAG(appointments) OVER (ORDER BY month))
             / LAG(appointments) OVER (ORDER BY month), 2)             AS mom_pct
FROM monthly
ORDER BY month;

-- 2. Cancellation-rate trend (with completion & no-show rates) ----------------
--    Feeds the "Completed vs Cancelled vs No-Show" chart and cancellation KPI.
SELECT month,
       SUM(appointments)                                               AS total_appointments,
       ROUND(100.0 * SUM(CASE WHEN appointment_status = 'Cancelled' THEN appointments END)
             / SUM(appointments), 2)                                   AS cancellation_rate_pct,
       ROUND(100.0 * SUM(CASE WHEN appointment_status = 'Completed' THEN appointments END)
             / SUM(appointments), 2)                                   AS completion_rate_pct,
       ROUND(100.0 * SUM(CASE WHEN appointment_status = 'No-Show' THEN appointments END)
             / SUM(appointments), 2)                                   AS no_show_rate_pct
FROM appointments_fact
GROUP BY month
ORDER BY month;

-- 3. Department workload (latest month) --------------------------------------
--    Feeds the horizontal "Department workload" bar chart.
SELECT department,
       SUM(appointments) AS appointments,
       ROUND(100.0 * SUM(appointments)
             / (SELECT SUM(appointments) FROM appointments_fact
                WHERE month = (SELECT MAX(month) FROM appointments_fact)), 1) AS pct_of_month
FROM appointments_fact
WHERE month = (SELECT MAX(month) FROM appointments_fact)
GROUP BY department
ORDER BY appointments DESC;

-- 4. Claims status distribution (latest month) -------------------------------
--    Feeds the claims-status donut.
SELECT claim_status,
       SUM(claim_count) AS claims,
       ROUND(100.0 * SUM(claim_count)
             / (SELECT SUM(claim_count) FROM claims_fact
                WHERE month = (SELECT MAX(month) FROM claims_fact)), 1) AS pct_of_month
FROM claims_fact
WHERE month = (SELECT MAX(month) FROM claims_fact)
GROUP BY claim_status
ORDER BY claims DESC;

-- 5. Claims aging distribution by month --------------------------------------
--    Feeds the stacked "Claims aging trend by month" chart.
SELECT month,
       SUM(aging_0_30)                                                 AS b_0_30,
       SUM(aging_31_60)                                                AS b_31_60,
       SUM(aging_61_90)                                                AS b_61_90,
       SUM(aging_90_plus)                                              AS b_90_plus,
       ROUND(100.0 * SUM(aging_90_plus) / SUM(claim_count), 2)         AS pct_aged_90_plus
FROM claims_fact
GROUP BY month
ORDER BY month;

-- 6. Average processing-days trend + MoM (the growing bottleneck) ------------
--    Feeds the "Avg claim processing days" line chart. Claim-count weighted.
WITH monthly AS (
    SELECT month,
           1.0 * SUM(avg_processing_days * claim_count) / SUM(claim_count) AS avg_processing_days
    FROM claims_fact
    GROUP BY month
)
SELECT month,
       ROUND(avg_processing_days, 2)                                   AS avg_processing_days,
       ROUND(avg_processing_days - LAG(avg_processing_days) OVER (ORDER BY month), 2) AS mom_change,
       ROUND(AVG(avg_processing_days) OVER (
             ORDER BY month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 2) AS rolling_3m
FROM monthly
ORDER BY month;

-- 7. Approval rate by department (latest month) ------------------------------
--    Approval = (Approved + Paid) / total claims. Feeds the scorecard.
SELECT department,
       SUM(claim_count) AS claims,
       ROUND(100.0 * SUM(CASE WHEN claim_status IN ('Approved', 'Paid') THEN claim_count END)
             / SUM(claim_count), 2)                                    AS approval_rate_pct,
       ROUND(1.0 * SUM(avg_processing_days * claim_count) / SUM(claim_count), 1) AS avg_processing_days,
       ROUND(100.0 * SUM(aging_90_plus) / SUM(claim_count), 2)         AS pct_aged_90_plus
FROM claims_fact
WHERE month = (SELECT MAX(month) FROM claims_fact)
GROUP BY department
ORDER BY approval_rate_pct DESC;

-- 8. Seasonality — cancellation rate by calendar month-of-year ---------------
--    Confirms the winter (Dec-Feb) cancellation spike across all years.
SELECT SUBSTR(month, 6, 2)                                             AS month_of_year,
       ROUND(AVG(cancellation_rate_pct), 2)                            AS avg_cancellation_rate_pct
FROM (
    SELECT month,
           100.0 * SUM(CASE WHEN appointment_status = 'Cancelled' THEN appointments END)
                 / SUM(appointments) AS cancellation_rate_pct
    FROM appointments_fact
    GROUP BY month
)
GROUP BY month_of_year
ORDER BY month_of_year;
