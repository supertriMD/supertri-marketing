"""Marketing (external) data layer — REGISTRATIONS ONLY, strictly non-financial.

Every accessor reads ONLY the `supertri_marketing.*` revenue-free views (chat 1, commit 6177876) so
the marketing dashboard can run behind a read-only service account scoped to that dataset alone — the
data-layer wall. NO revenue, ATV, ledger, forecast-revenue, LTV or currency-value is queried or
returned. The demographic accessors are reimplemented here (not reused from data.py) precisely so they
hit `v_registration_attributes` rather than the revenue-bearing `supertri_enrich` source.

Views:
  supertri_marketing.v_registration_attributes  — v_active_registration_wide minus revenue_usd/currency
  supertri_marketing.v_reg_year_book            — reg-only per event×edition (target/act/landing)
  supertri_marketing.v_reg_pacing               — reg-only weekly pacing (available; not yet used here)

Format-share still reads supertri_raw.cycle_registrations (a marketing projection of it is pending from
chat 1); that section degrades gracefully until the scoped view lands.
"""
import numpy as np
import pandas as pd

import data as D

# shared constants
CODE_DISP, CCY = D.CODE_DISP, D.CCY
LIVE_CYCLE, BASELINE_YEAR, AS_OF = D.LIVE_CYCLE, D.BASELINE_YEAR, D.AS_OF
RECENT_YEARS, FMT_ORDER, AGE_ORDER = D.RECENT_YEARS, D.FMT_ORDER, D.AGE_ORDER
MIX_QUESTIONS = D.MIX_QUESTIONS
PROJECT, LOCATION = D.PROJECT, D.LOCATION
SEASONS = [BASELINE_YEAR, LIVE_CYCLE]

_ATTR = "`$P.supertri_marketing.v_registration_attributes`"   # revenue-free enrichment attributes
_FMT = "`$P.supertri_marketing.v_format_mix`"                  # revenue-free format grain (cycle_registrations projection)
_ELIG_SQL = D._ELIG_SQL                                        # lineage IN (...) filter (real BQ labels)
_YRS = ",".join(str(y) for y in RECENT_YEARS)


# ── Registrations vs plan (year-book, reg-only) ──
def year_book_reg(year: int) -> pd.DataFrame:
    """Per-event REGISTRATIONS picture for a season, from supertri_marketing.v_reg_year_book: race day,
    status, days-to-race, reg target, reg to-date, % of target, projected landing. NO revenue.
    reg_act = COALESCE(ACTIVE reg-date actuals, ledger COUNT for LDT editions) in the view, so Blenheim
    2026 matches the board (5,631) — no app-side fallback needed."""
    df = D._q(f"""SELECT event_code, CAST(race_date AS DATE) AS race_date,
                    CAST(reg_target AS FLOAT64) AS reg_target,
                    CAST(reg_act AS FLOAT64) AS reg_act,
                    CAST(reg_landing_fcst AS FLOAT64) AS landing_reg
                  FROM `$P.supertri_marketing.v_reg_year_book` WHERE edition_year={year}""")
    if not len(df):
        return df.assign(event=[], edition_year=[], status=[], days_to_race=[], reg_pct=[], ccy=[])
    df["event"] = df.event_code.map(CODE_DISP)
    df["ccy"] = df.event.map(CCY)
    df["edition_year"] = year
    df["status"] = np.where(pd.to_datetime(df.race_date) < AS_OF, "completed", "selling")
    df["days_to_race"] = (pd.to_datetime(df.race_date) - AS_OF).dt.days
    df["reg_pct"] = df.reg_act / df.reg_target
    df["landing_reg"] = np.maximum(pd.to_numeric(df.landing_reg, errors="coerce").fillna(df.reg_act),
                                   df.reg_act.fillna(0))
    return D._order_events(df[["event", "event_code", "edition_year", "race_date", "status",
                               "days_to_race", "reg_act", "reg_target", "reg_pct", "landing_reg", "ccy"]])


# ── Board-parity helpers: presale actuals + last-year-this-month (revenue-free) ──
def presale_benchmarks() -> pd.DataFrame:
    """2027 presale editions (LB/NJ/TOR/TOR_10K) from supertri_marketing.v_presale_benchmarks — reg counts
    only (forecast + actuals-to-date + last-year). Empty until chat 1 mirrors the view."""
    cols = ["event_code", "reg_target", "reg_eolm_fcst", "reg_eotm_fcst", "reg_actual_to_date"]
    try:
        df = D._q("""SELECT event_code, CAST(reg_target AS FLOAT64) reg_target,
                       CAST(reg_eolm_fcst AS FLOAT64) reg_eolm_fcst, CAST(reg_eotm_fcst AS FLOAT64) reg_eotm_fcst,
                       CAST(reg_actual_to_date AS FLOAT64) reg_actual_to_date
                     FROM `$P.supertri_marketing.v_presale_benchmarks`""")
    except Exception:
        return pd.DataFrame(columns=cols)
    return df if len(df) else pd.DataFrame(columns=cols)


def prior_year_thismonth(season: int) -> dict:
    """{event → last-year this-month registrations} for a season, from supertri_marketing.v_prior_year_thismonth
    (prior_regs_eotm at the same months-to-race) + a PORTFOLIO sum. Empty until chat 1 mirrors the view."""
    try:
        df = D._q(f"SELECT event_code, prior_regs_eotm FROM `$P.supertri_marketing.v_prior_year_thismonth` "
                  f"WHERE edition_year={season}")
    except Exception:
        return {}
    m = {CODE_DISP.get(r.event_code, r.event_code): (float(r.prior_regs_eotm) if pd.notna(r.prior_regs_eotm)
         else np.nan) for r in df.itertuples()}
    vals = [v for v in m.values() if pd.notna(v)]
    if vals:
        m["PORTFOLIO"] = float(sum(vals))
    return m


def _merge_presale(reg, pb):
    """Fill the just-opened presale editions' actuals into the weekly reg frame (board parity): EOLM act 0,
    EOTM act = actual-to-date; keep their forecast/target from the benchmark. Others untouched."""
    reg = reg.copy()
    m = {CODE_DISP.get(r.event_code, r.event_code): r for r in pb.itertuples()}
    for i in reg.index:
        r = m.get(reg.at[i, "event"])
        if r is None:
            continue
        reg.at[i, "total_target"] = pd.to_numeric(r.reg_target, errors="coerce")
        reg.at[i, "eolm_fcst"] = pd.to_numeric(r.reg_eolm_fcst, errors="coerce")
        reg.at[i, "eotm_fcst"] = pd.to_numeric(r.reg_eotm_fcst, errors="coerce")
        reg.at[i, "eolm_act"] = 0.0
        reg.at[i, "eotm_act"] = pd.to_numeric(r.reg_actual_to_date, errors="coerce")
        reg.at[i, "trend"], reg.at[i, "wow_pct"] = None, np.nan
    return reg


# ── Registrations Actuals-vs-Forecast weekly grid (tracker format, reg-only) ──
def weekly_reg(season: int):
    """(reg_frame, meta) for the original-tracker EOLM/Current/EOTM registrations grid, from the
    revenue-free supertri_marketing.v_reg_pacing (all editions of the season). Returns a reg frame
    (event, total_target, eolm/eotm forecast+actual, trend/wow_pct) + a PORTFOLIO total, and
    meta = {event: (status, days_to_race)} from v_reg_year_book. NO revenue. Trend = v_reg_pacing's
    reg_trend (UP/DOWN/FLAT) + reg_wow_pct (WoW momentum, 3wk vs prior-3wk) — both non-financial."""
    p = D._q(f"""SELECT event_code,
                   CAST(reg_target AS FLOAT64) AS reg_target,
                   CAST(reg_eolm_fcst AS FLOAT64) AS reg_eolm_fcst,
                   CAST(reg_eolm_act AS FLOAT64) AS reg_eolm_act,
                   CAST(reg_thismonth_fcst AS FLOAT64) AS reg_thismonth_fcst,
                   CAST(reg_thismonth_act AS FLOAT64) AS reg_thismonth_act,
                   reg_trend, CAST(reg_wow_pct AS FLOAT64) AS reg_wow_pct
                 FROM `$P.supertri_marketing.v_reg_pacing` WHERE edition_year={season}""")
    yb = year_book_reg(season)
    meta = {r.event: (r.status, r.days_to_race) for r in yb.itertuples()}
    if not len(p):
        return pd.DataFrame(columns=["event", "total_target", "eolm_fcst", "eolm_act",
                                     "eotm_fcst", "eotm_act", "trend", "wow_pct"]), meta
    reg = pd.DataFrame({
        "event": p.event_code.map(CODE_DISP),
        "total_target": p.reg_target,
        "eolm_fcst": p.reg_eolm_fcst,
        "eolm_act": p.reg_eolm_act,
        "eotm_fcst": p.reg_eolm_fcst + p.reg_thismonth_fcst,
        "eotm_act": p.reg_eolm_act + p.reg_thismonth_act,
        "trend": p.reg_trend,
        "wow_pct": pd.to_numeric(p.reg_wow_pct, errors="coerce") * 100})   # fraction → percent for display
    reg = D._order_events(reg)
    # board parity: fill the just-opened 2027 presale editions' actuals (LB/NJ/TOR/TOR_10K)
    if season == LIVE_CYCLE:
        pb = presale_benchmarks()
        if len(pb):
            reg = _merge_presale(reg, pb)
    port = {"event": "PORTFOLIO", "trend": None, "wow_pct": np.nan}
    for c in ("total_target", "eolm_fcst", "eolm_act", "eotm_fcst", "eotm_act"):
        port[c] = pd.to_numeric(reg[c], errors="coerce").sum(min_count=1)
    return pd.concat([reg, pd.DataFrame([port])], ignore_index=True), meta


# ── Registration ramp (per event: plan vs last year vs actual) ──
def ramp_trajectory():
    """Per-event registration ramp from the revenue-free supertri_marketing.v_ramp_trajectory: one series
    per event's current live edition — prior_cum (last year at same mtr) / plan_cum (v3 plan) / act_cum
    (this edition's actuals). NO revenue."""
    cols = ["event", "event_code", "mtr", "calendar_month", "prior_cum", "plan_cum", "act_cum"]
    try:
        df = D._q("""SELECT event_code, mtr, CAST(calendar_month AS DATE) AS calendar_month,
                       prior_cum, plan_cum, act_cum
                     FROM `$P.supertri_marketing.v_ramp_trajectory`""")
    except Exception:
        return pd.DataFrame(columns=cols)
    if not len(df):
        return pd.DataFrame(columns=cols)
    df["event"] = df.event_code.map(CODE_DISP)
    for c in ("mtr", "prior_cum", "plan_cum", "act_cum"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df[cols]


# ── Participant profile (gender / age) ──
def profile_v2():
    """(gender, age, avg_age) frames — PORTFOLIO + per event, recent years — from v_registration_attributes."""
    def _portfolio(df):
        p = df.groupby(["year", "answer"], as_index=False).n.sum(); p["scope"] = "PORTFOLIO"
        return pd.concat([df, p], ignore_index=True)

    gender = _portfolio(D._q(f"""SELECT lineage scope, year, gender AS answer, COUNT(*) n FROM {_ATTR}
                    WHERE gender IS NOT NULL AND gender!='' AND year IN ({_YRS})
                      AND lineage IN {_ELIG_SQL} GROUP BY 1,2,3"""))
    age = _portfolio(D._q(f"""SELECT scope, year, {D._AGE_CASE} AS answer, COUNT(*) n FROM (
                   SELECT lineage scope, year, (year - birth_year) a FROM {_ATTR}
                   WHERE birth_year IS NOT NULL AND year IN ({_YRS}) AND lineage IN {_ELIG_SQL}
                     AND (year - birth_year) BETWEEN 10 AND 90)
                 GROUP BY 1,2,3"""))
    av = D._q(f"""SELECT lineage scope, year, SUM(year - birth_year) s, COUNT(*) n FROM {_ATTR}
                WHERE birth_year IS NOT NULL AND year IN ({_YRS}) AND lineage IN {_ELIG_SQL}
                  AND (year - birth_year) BETWEEN 10 AND 90 GROUP BY 1,2""")
    avp = av.groupby("year", as_index=False).agg(s=("s", "sum"), n=("n", "sum")); avp["scope"] = "PORTFOLIO"
    av = pd.concat([av, avp], ignore_index=True); av["avg_age"] = av.s / av.n
    return gender, age, av[["scope", "year", "avg_age"]]


# ── Athlete mix (journey / goal / fitness) ──
def athlete_mix_v2() -> pd.DataFrame:
    """Long frame [question, scope, year, answer, n] for journey/goal/fitness — from v_registration_attributes."""
    parts = []
    for field, label in MIX_QUESTIONS:
        d = D._q(f"""SELECT lineage AS scope, year, {field} AS answer, COUNT(*) n FROM {_ATTR}
                     WHERE {field} IS NOT NULL AND {field}!='' AND year IN ({_YRS})
                       AND lineage IN {_ELIG_SQL} GROUP BY 1,2,3""")
        d["question"] = label
        parts.append(d)
    long = pd.concat(parts, ignore_index=True)
    port = long.groupby(["question", "year", "answer"], as_index=False).n.sum(); port["scope"] = "PORTFOLIO"
    return pd.concat([long, port], ignore_index=True)[["question", "scope", "year", "answer", "n"]]


# ── Returning rate (email-exact FLOOR) ──
def returning_breakdown() -> pd.DataFrame:
    """Per (event, year) four-way split — new / yoy_ret / earlier_ret / diff_event — + PORTFOLIO row.
    Email-exact FLOOR, from v_registration_attributes history windows."""
    cols = ["event_display", "year", "total", "new", "yoy_ret", "earlier_ret", "diff_event"]
    elig = "(" + ",".join(f"'{l}'" for l in D._ELIG_LINEAGE) + ")"
    ev = D._q(f"""
      WITH py AS (SELECT DISTINCT person_key, lineage, year FROM {_ATTR}
                  WHERE person_key IS NOT NULL AND year IS NOT NULL AND lineage IN {elig}),
      flags AS (SELECT a.person_key, a.lineage, a.year,
          MAX(IF(b.lineage=a.lineage AND b.year<a.year,1,0)) sb,
          MAX(IF(b.lineage=a.lineage AND b.year=a.year-1,1,0)) sl,
          MAX(IF(b.lineage!=a.lineage AND b.year<a.year,1,0)) db
        FROM py a LEFT JOIN py b ON a.person_key=b.person_key AND b.year<a.year GROUP BY 1,2,3)
      SELECT lineage AS event_display, year, COUNT(*) total,
        COUNTIF(sb=0 AND db=0) AS `new`, COUNTIF(sl=1) yoy_ret,
        COUNTIF(sb=1 AND sl=0) earlier_ret, COUNTIF(sb=0 AND db=1) diff_event
      FROM flags GROUP BY 1,2""")
    port = D._q(f"""
      WITH py AS (SELECT DISTINCT person_key, year FROM {_ATTR}
                  WHERE person_key IS NOT NULL AND year IS NOT NULL AND lineage IN {elig}),
      flags AS (SELECT a.person_key, a.year,
          MAX(IF(b.year<a.year,1,0)) ab, MAX(IF(b.year=a.year-1,1,0)) al
        FROM py a LEFT JOIN py b ON a.person_key=b.person_key AND b.year<a.year GROUP BY 1,2)
      SELECT 'PORTFOLIO' AS event_display, year, COUNT(*) total,
        COUNTIF(ab=0) AS `new`, COUNTIF(al=1) yoy_ret, COUNTIF(ab=1 AND al=0) earlier_ret, 0 diff_event
      FROM flags GROUP BY 2""")
    return pd.concat([ev, port], ignore_index=True)[cols]


# ── Event format mix (registration counts only) ──
def yield_share():
    """Format-share by event/year — REGISTRATION COUNTS ONLY (no ATV/revenue), from the revenue-free
    supertri_marketing.v_format_mix. Returns [scope, year, fmt, regs]. Canonical 5-bucket grain."""
    core = "(" + ",".join(f"'{c}'" for c in D._CORE_CANON) + ")"
    try:
        g = D._q(f"""SELECT event_canonical, CAST(event_year AS INT64) year, {D._FMT_CASE} fmt, COUNT(*) regs
                     FROM {_FMT}
                     WHERE event_canonical IN {core} AND CAST(event_year AS INT64) IN ({_YRS})
                       AND format_type IN ('race','corporate','youth') AND distance_normalized IS NOT NULL
                     GROUP BY 1,2,3""")
    except Exception:
        return pd.DataFrame(columns=["scope", "year", "fmt", "regs"])
    if not len(g):
        return pd.DataFrame(columns=["scope", "year", "fmt", "regs"])
    g["scope"] = g.event_canonical.map(D._disp)
    port = g.groupby(["year", "fmt"], as_index=False).regs.sum(); port["scope"] = "PORTFOLIO"
    return pd.concat([g[["scope", "year", "fmt", "regs"]], port], ignore_index=True)
