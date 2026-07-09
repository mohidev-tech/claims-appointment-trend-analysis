"""
load_and_validate.py — load the CSVs into SQLite and reconcile key metrics
against the values shown on the dashboard.

Run:  python sql/load_and_validate.py
Creates claims.db and prints the latest-month KPI summary plus the processing-
days trend so the numbers can be compared directly to the dashboard KPI cards.
"""
import os
import sqlite3
import csv

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DB = os.path.join(HERE, "claims.db")

TEXT_COLS = {"month", "department", "service_category", "appointment_status",
             "claim_type", "claim_status"}


def load_csv(cur, table, path):
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.reader(f)
        cols = next(r)
        cur.execute(f"DROP TABLE IF EXISTS {table}")
        coldefs = ",".join(c + (" TEXT" if c in TEXT_COLS else " NUMERIC") for c in cols)
        cur.execute(f"CREATE TABLE {table} ({coldefs})")
        rows = [tuple(v if v != "" else None for v in row) for row in r]
        cur.executemany(f"INSERT INTO {table} VALUES ({','.join('?' * len(cols))})", rows)
    return len(rows)


def main():
    con = sqlite3.connect(DB)
    cur = con.cursor()
    n1 = load_csv(cur, "appointments_fact", os.path.join(ROOT, "data", "appointments_fact.csv"))
    n2 = load_csv(cur, "claims_fact", os.path.join(ROOT, "data", "claims_fact.csv"))
    con.commit()
    print(f"loaded appointments_fact={n1:,}  claims_fact={n2:,}\n")

    print("== KPI SUMMARY (latest month) — should match dashboard cards ==")
    (month,) = cur.execute("SELECT MAX(month) FROM appointments_fact").fetchone()
    print(f"  month = {month}")

    for row in cur.execute("""
        SELECT SUM(appointments),
            ROUND(100.0*SUM(CASE WHEN appointment_status='Cancelled' THEN appointments END)/SUM(appointments),2),
            ROUND(100.0*SUM(CASE WHEN appointment_status='Completed' THEN appointments END)/SUM(appointments),2)
        FROM appointments_fact WHERE month=(SELECT MAX(month) FROM appointments_fact)"""):
        print(f"  total_appointments = {int(row[0]):,}")
        print(f"  cancellation_rate  = {row[1]}%")
        print(f"  completion_rate    = {row[2]}%")

    for row in cur.execute("""
        SELECT SUM(claim_count),
            ROUND(100.0*SUM(CASE WHEN claim_status IN ('Approved','Paid') THEN claim_count END)/SUM(claim_count),2),
            ROUND(1.0*SUM(avg_processing_days*claim_count)/SUM(claim_count),1),
            ROUND(100.0*SUM(aging_90_plus)/SUM(claim_count),2),
            SUM(claim_amount)
        FROM claims_fact WHERE month=(SELECT MAX(month) FROM claims_fact)"""):
        print(f"  total_claims       = {int(row[0]):,}")
        print(f"  approval_rate      = {row[1]}%")
        print(f"  avg_processing_days= {row[2]}")
        print(f"  pct_aged_90_plus   = {row[3]}%")
        print(f"  total_billed       = ${row[4]:,.0f}")

    print("\n== AVG PROCESSING DAYS TREND (claim-count weighted) ==")
    for m, d in cur.execute("""
        SELECT month, ROUND(1.0*SUM(avg_processing_days*claim_count)/SUM(claim_count),1)
        FROM claims_fact GROUP BY month ORDER BY month"""):
        print(f"  {m}: {d} days")

    print("\n== CANCELLATION-RATE SEASONALITY (avg by month-of-year) ==")
    for moy, r in cur.execute("""
        SELECT SUBSTR(month,6,2), ROUND(AVG(rate),2) FROM (
            SELECT month, 100.0*SUM(CASE WHEN appointment_status='Cancelled' THEN appointments END)
                   /SUM(appointments) AS rate
            FROM appointments_fact GROUP BY month)
        GROUP BY SUBSTR(month,6,2) ORDER BY SUBSTR(month,6,2)"""):
        print(f"  month {moy}: {r}%")

    con.close()
    print("\nOK — SQLite reconciliation complete.")


if __name__ == "__main__":
    main()
