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

# Cancelled editions — AUTHORITATIVE source is the warehouse `v_reg_year_book.sell_state='cancelled'` (chat 1,
# 6 Aug 2026). year_book_reg unifies it into `sell_state`; consumers derive the cancelled set from there.
# CANCELLED_EDITIONS is an EMPTY manual-override hook (kept local to the slim bundle) — populate only to force
# a cancellation the warehouse hasn't caught up to. RETAIN tickets-to-date, DROP plan, no forecast/landing.
# NB: the warehouse also drops cancelled editions from v_reg_pacing/v_ramp_trajectory — weekly_reg pulls them
# back from year_book so they still render badged CANCELLED (revenue-free, tickets only).
CANCELLED_EDITIONS: set = set()

def _is_cancelled(event_code, year) -> bool:
    try:
        return (str(event_code), int(year)) in CANCELLED_EDITIONS
    except Exception:
        return False

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
    df = D._q(f"""SELECT event_code, CAST(race_date AS DATE) AS race_date, sell_state,
                    CAST(opens AS DATE) AS opens,
                    CAST(reg_target AS FLOAT64) AS reg_target,
                    CAST(reg_act AS FLOAT64) AS reg_act,
                    CAST(reg_landing_fcst AS FLOAT64) AS landing_reg
                  FROM `$P.supertri_marketing.v_reg_year_book` WHERE edition_year={year}""")
    if not len(df):
        return df.assign(event=[], edition_year=[], status=[], days_to_race=[], reg_pct=[], ccy=[])
    df["event"] = df.event_code.map(CODE_DISP)
    df["ccy"] = df.event.map(CCY)
    df["edition_year"] = year
    # passed/selling from the date-driven rule (v_reg_year_book.sell_state ← v_edition_sell_state);
    # fall back to race_date<AS_OF if a row lacks it. 'future' folds into 'selling' (2-state display),
    # mirroring the board — LB/NJ flip to passed on the real calendar, no reporting_week nudge.
    _passed = np.where(df.sell_state.notna(), df.sell_state.eq("passed"),
                       pd.to_datetime(df.race_date) < AS_OF)
    df["status"] = np.where(_passed, "completed", "selling")
    # Cancelled editions: retain reg_act, drop plan (target) — status/sell_state='cancelled'. Honour a
    # warehouse sell_state='cancelled' too (chat 1) so the interim registry can be emptied later.
    _canc = df.event_code.map(lambda ec: _is_cancelled(ec, year)) | df.sell_state.eq("cancelled")
    if _canc.any():
        df.loc[_canc, ["sell_state", "status"]] = ["cancelled", "cancelled"]
        df.loc[_canc, "reg_target"] = np.nan
    df["days_to_race"] = (pd.to_datetime(df.race_date) - AS_OF).dt.days
    df["reg_pct"] = df.reg_act / df.reg_target
    df["landing_reg"] = np.maximum(pd.to_numeric(df.landing_reg, errors="coerce").fillna(df.reg_act),
                                   df.reg_act.fillna(0))
    if _canc.any():
        df.loc[_canc, "landing_reg"] = pd.to_numeric(df.loc[_canc, "reg_act"], errors="coerce")   # no projection
    return D._order_events(df[["event", "event_code", "edition_year", "race_date", "status", "sell_state", "opens",
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
                   reg_trend, CAST(reg_wow_pct AS FLOAT64) AS reg_wow_pct, is_launching,
                   CAST(reg_this_week AS FLOAT64) AS reg_this_week,
                   CAST(reg_3wk_total AS FLOAT64) AS reg_3wk_total
                 FROM `$P.supertri_marketing.v_reg_pacing` WHERE edition_year={season}""")
    yb = year_book_reg(season)
    # meta carries sell_state + opens for the future/not-yet-open display ("OPENS <date>"), from v_reg_year_book.
    meta = {r.event: (r.status, r.days_to_race, r.sell_state, r.opens) for r in yb.itertuples()}
    if not len(p):
        return pd.DataFrame(columns=["event", "total_target", "eolm_fcst", "eolm_act", "eotm_fcst",
                                     "eotm_act", "trend", "wow_pct", "is_launching", "last7d", "prev14avg"]), meta
    reg = pd.DataFrame({
        "event": p.event_code.map(CODE_DISP),
        "total_target": p.reg_target,
        "eolm_fcst": p.reg_eolm_fcst,
        "eolm_act": p.reg_eolm_act,
        "eotm_fcst": p.reg_eolm_fcst + p.reg_thismonth_fcst,
        "eotm_act": p.reg_eolm_act + p.reg_thismonth_act,
        "trend": p.reg_trend,
        "wow_pct": pd.to_numeric(p.reg_wow_pct, errors="coerce") * 100,   # fraction → percent for display
        "is_launching": p.is_launching.fillna(False).astype(bool),   # B19: render '🚀 Launching' on these
        # recent run-rate (reg counts, trailing/rolling daily as-of): Last 7d + Prev 14d avg (days 8–21 mean)
        "last7d": p.reg_this_week,
        "prev14avg": (p.reg_3wk_total - p.reg_this_week) / 2.0})
    reg = D._order_events(reg)
    # board parity: fill the just-opened 2027 presale editions' actuals (LB/NJ/TOR/TOR_10K)
    if season == LIVE_CYCLE:
        pb = presale_benchmarks()
        if len(pb):
            reg = _merge_presale(reg, pb)
    # Cancelled editions are dropped from v_reg_pacing by the warehouse (no pacing for a cancelled event) —
    # pull them back from year_book as a to-date-only row so they still render badged CANCELLED (retain the
    # numbers). Actual = reg_act (tickets to date); forecast/plan NaN; 'cancelled' shown via meta in the render.
    if "sell_state" in yb.columns:
        cyb = yb[(yb.sell_state == "cancelled") & (~yb.event.isin(reg.event))]
        if len(cyb):
            ra = pd.to_numeric(cyb.reg_act, errors="coerce")
            reg = D._order_events(pd.concat([reg, pd.DataFrame({
                "event": cyb.event.values, "total_target": np.nan, "eolm_fcst": np.nan,
                "eolm_act": ra.values, "eotm_fcst": np.nan, "eotm_act": ra.values,
                "trend": None, "wow_pct": np.nan, "is_launching": False,
                "last7d": np.nan, "prev14avg": np.nan})], ignore_index=True))
    # Manual-override hook (CANCELLED_EDITIONS, empty by default): if a cancelled edition is STILL in the
    # pacing frame (warehouse not caught up), keep eolm/eotm ACT but NULL forecast + plan so the PORTFOLIO
    # sum drops its plan while retaining actuals.
    _canc = {CODE_DISP.get(ec, ec) for (ec, y) in CANCELLED_EDITIONS if y == season}
    if _canc:
        m = reg.event.isin(_canc)
        for c in ("total_target", "eolm_fcst", "eotm_fcst"):
            reg.loc[m, c] = np.nan
        reg.loc[m, "trend"] = None
        reg.loc[m, "wow_pct"] = np.nan
        reg.loc[m, "is_launching"] = False
    port = {"event": "PORTFOLIO", "trend": None, "wow_pct": np.nan, "is_launching": False}
    for c in ("total_target", "eolm_fcst", "eolm_act", "eotm_fcst", "eotm_act", "last7d", "prev14avg"):
        port[c] = pd.to_numeric(reg[c], errors="coerce").sum(min_count=1)
    return pd.concat([reg, pd.DataFrame([port])], ignore_index=True), meta


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


# home→away order (defined inline, NOT via D — the deployed marketing_public/data.py is slim and lacks it)
ORIGIN_TIERS = ["Local", "Same state", "National", "International", "Unknown"]


def origin_tiers() -> pd.DataFrame:
    """[scope, year, tier, n] from the walled supertri_marketing.v_origin_tiers — a revenue-free passthrough
    of the board's v_origin_tiers. PORTFOLIO rollup is already in the view. Each reg → one nested ring around
    the venue: Local (v1 city-name proxy) / Same state / National / International / Unknown. US/CA render
    4-ring, GB/FR 3-ring (Same state folded → National), same as the board."""
    return D._q("SELECT scope, year, tier, n FROM `$P.supertri_marketing.v_origin_tiers`")[["scope", "year", "tier", "n"]]


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


# ── Cross-event migration (athletes racing ≥2 Supertri events; reg-only, revenue-free) ──
# All from the walled v_registration_attributes (person_key · lineage · year · is_staff) — the same source
# the returning-rate uses. Cumulative since 2025 (pre-2025 can't be attributed to the unified brand); staff
# (@supertri.com) excluded via is_staff. Matches the board's cross-event tab to ~1 athlete (staff-flag source).
_MIG_BASE = f"""WITH base AS (SELECT DISTINCT person_key, lineage, year FROM {_ATTR}
    WHERE person_key IS NOT NULL AND year>=2025 AND lineage IN {_ELIG_SQL} AND is_staff IS NOT TRUE)"""


def cross_event_migration() -> pd.DataFrame:
    """Per asof-year (2025+): distinct athletes racing ≥2 / ≥3 DISTINCT events (cumulative since 2025) + %."""
    cols = ["year", "athletes", "ge2", "ge3", "ge2_pct", "ge3_pct"]
    d = D._q(_MIG_BASE + f""", cum AS (SELECT a.person_key, a.year AS asof, COUNT(DISTINCT b.lineage) n
        FROM (SELECT DISTINCT person_key, year FROM base) a
        JOIN base b ON a.person_key=b.person_key AND b.year<=a.year GROUP BY 1,2)
      SELECT asof AS year, COUNT(DISTINCT person_key) athletes,
        COUNT(DISTINCT IF(n>=2, person_key, NULL)) ge2, COUNT(DISTINCT IF(n>=3, person_key, NULL)) ge3
      FROM cum WHERE asof IN ({_YRS}) GROUP BY 1 ORDER BY 1""")
    if not len(d):
        return pd.DataFrame(columns=cols)
    d["ge2_pct"] = 100 * d.ge2 / d.athletes
    d["ge3_pct"] = 100 * d.ge3 / d.athletes
    return d[cols]


def cross_event_by_event() -> pd.DataFrame:
    """Per event: distinct athletes since 2025 + how many ALSO raced ≥1 other Supertri event (cross share)."""
    return D._q(_MIG_BASE + """, pc AS (SELECT person_key, COUNT(DISTINCT lineage) n FROM base GROUP BY 1)
      SELECT b.lineage AS event, COUNT(DISTINCT b.person_key) AS athletes,
        COUNT(DISTINCT IF(pc.n>=2, b.person_key, NULL)) AS cross_athletes,
        ROUND(100*COUNT(DISTINCT IF(pc.n>=2, b.person_key, NULL))/COUNT(DISTINCT b.person_key), 1) AS cross_pct
      FROM base b JOIN pc USING(person_key) GROUP BY 1 ORDER BY cross_athletes DESC""")


def cross_event_pairs(limit: int = 8) -> pd.DataFrame:
    """Event PAIRS by shared athletes since 2025 (people who raced BOTH) — the actual migration flows."""
    return D._q(_MIG_BASE + f"""
      SELECT b1.lineage AS event_a, b2.lineage AS event_b, COUNT(DISTINCT b1.person_key) AS shared
      FROM base b1 JOIN base b2 ON b1.person_key=b2.person_key AND b1.lineage<b2.lineage
      GROUP BY 1,2 HAVING shared>0 ORDER BY shared DESC LIMIT {int(limit)}""")


def cross_event_by_event_year() -> pd.DataFrame:
    """Per event × cycle-year (2025+): of the athletes racing that event that year, how many are cross-event
    (≥2 distinct Supertri lineages cumulatively by then) — the year-over-year trend."""
    cols = ["event", "yr", "athletes", "cross_ath", "cross_pct"]
    d = D._q(_MIG_BASE + """, cum AS (SELECT a.person_key, a.year AS asof, COUNT(DISTINCT b.lineage) n
        FROM (SELECT DISTINCT person_key, year FROM base) a
        JOIN base b ON a.person_key=b.person_key AND b.year<=a.year GROUP BY 1,2)
      SELECT b.lineage AS event, b.year AS yr, COUNT(DISTINCT b.person_key) AS athletes,
        COUNT(DISTINCT IF(c.n>=2, b.person_key, NULL)) AS cross_ath
      FROM base b JOIN cum c ON c.person_key=b.person_key AND c.asof=b.year GROUP BY 1,2 ORDER BY 1,2""")
    if not len(d):
        return pd.DataFrame(columns=cols)
    d["cross_pct"] = (100 * d.cross_ath / d.athletes).round(1)
    return d[cols]


CORP_YEARS = [2024, 2025, 2026]   # corporate challenge has mature data from 2024 (LB); mirrors the board


def corporate_challenge():
    """Corporate Challenge cut (D18 cross-cutting flag — athletes keep their real distance): (by_event,
    entry_mix) from the walled v_registration_attributes. Staff excluded. Mirrors the board's tab."""
    ce, cm = ["event", "year", "regs", "corp", "corp_pct"], ["year", "answer", "n"]
    yrs = ",".join(str(y) for y in CORP_YEARS)
    be = D._q(f"""SELECT lineage AS event, year, COUNT(*) regs, COUNTIF(corporate_challenge) corp
                  FROM {_ATTR} WHERE is_staff IS NOT TRUE AND year IN ({yrs}) AND lineage IN {_ELIG_SQL}
                  GROUP BY 1,2 HAVING corp > 0""")
    if len(be):
        be["corp_pct"] = (100 * be.corp / be.regs).round(1)
    em = D._q(f"""SELECT year, IF(cc_entry_type IS NULL OR cc_entry_type='', 'Unspecified',
                     INITCAP(cc_entry_type)) answer, COUNT(*) n
                  FROM {_ATTR} WHERE corporate_challenge AND is_staff IS NOT TRUE AND year IN ({yrs})
                    AND lineage IN {_ELIG_SQL} GROUP BY 1,2""")
    return (be[ce] if len(be) else pd.DataFrame(columns=ce),
            em[cm] if len(em) else pd.DataFrame(columns=cm))


def corporate_participation() -> pd.DataFrame:
    """Per event × year corporate participation + Individual/Relay % split (count-only, from the walled
    v_registration_attributes). Mirrors the board — revenue-free. [event, event_code, year, corp, ind_pct, relay_pct]."""
    cols = ["event", "event_code", "year", "corp", "ind_pct", "relay_pct"]
    yrs = ",".join(str(y) for y in CORP_YEARS)
    df = D._q(f"""SELECT lineage AS event, year, COUNT(*) corp,
                    ROUND(100*COUNTIF(LOWER(cc_entry_type)='individual')/NULLIF(COUNT(*),0)) ind_pct,
                    ROUND(100*COUNTIF(LOWER(cc_entry_type)='relay')/NULLIF(COUNT(*),0)) relay_pct
                  FROM {_ATTR} WHERE corporate_challenge AND is_staff IS NOT TRUE AND year IN ({yrs})
                    AND lineage IN {_ELIG_SQL} GROUP BY 1,2 HAVING corp>0""")
    if not len(df):
        return pd.DataFrame(columns=cols)
    df["event_code"] = df.event.map({v: k for k, v in CODE_DISP.items()}).fillna(df.event)
    return df[cols]


# ── Clubs & Teams (walled COUNT-ONLY views — revenue-free) ──────────────────────────────────────
# supertri_marketing.v_club_event omits est_net_revenue + currency; v_club_register has no revenue columns.
# Defensive: return empty until chat 1 lands the walled views, so the tab shows "coming soon" not an error.
_M_CLUB_EVENT = "`$P.supertri_marketing.v_club_event`"
_M_CLUB_REGISTER = "`$P.supertri_marketing.v_club_register`"

def club_kpis() -> dict:
    """Count-only club KPIs (marketing): enrolled clubs · regs-via-codes (headline) · distinct discount codes ·
    editions. NO revenue. Empty dict until the walled views exist."""
    try:
        r = D._q(f"SELECT COUNT(*) AS clubs, SUM(code_redemptions) AS code_regs FROM {_M_CLUB_REGISTER}").iloc[0]
        codes = D._q(f"SELECT COUNT(DISTINCT TRIM(c)) AS n FROM {_M_CLUB_REGISTER}, UNNEST(SPLIT(discount_codes,',')) c "
                     f"WHERE TRIM(c)!=''").iloc[0].n
        ed = D._q(f"SELECT COUNT(DISTINCT event) AS editions FROM {_M_CLUB_EVENT}").iloc[0].editions
        return dict(clubs=int(r.clubs), code_regs=int(r.code_regs or 0), codes=int(codes), editions=int(ed))
    except Exception:
        return {}

def club_by_event() -> pd.DataFrame:
    """Per event: [event, event_code, enrolled, selected, code] — NO revenue/currency."""
    cols = ["event", "event_code", "enrolled", "selected", "code"]
    try:
        return D._q(f"""SELECT event, ANY_VALUE(event_code) AS event_code, COUNT(DISTINCT club_code) AS enrolled,
                          SUM(selected_athletes) AS selected, SUM(code_redemptions) AS code
                        FROM {_M_CLUB_EVENT} GROUP BY event ORDER BY code DESC""")[cols]
    except Exception:
        return pd.DataFrame(columns=cols)

def club_register() -> pd.DataFrame:
    """Per club: [club_code, club_label, entity_type, status_tier, events, members, selected, code]."""
    cols = ["club_code", "club_label", "entity_type", "status_tier", "events", "members", "selected", "code"]
    try:
        return D._q(f"""SELECT club_code, club_label, entity_type, status_tier, events, members,
                          selected_athletes AS selected, code_redemptions AS code
                        FROM {_M_CLUB_REGISTER} ORDER BY code_redemptions DESC, selected_athletes DESC""")[cols]
    except Exception:
        return pd.DataFrame(columns=cols)

def club_top3() -> pd.DataFrame:
    """Top-3 clubs per event by code redemptions."""
    cols = ["event", "event_code", "club_label", "entity_type", "members", "selected", "code", "rk"]
    try:
        return D._q(f"""SELECT event, event_code, club_label, entity_type, members, selected_athletes AS selected,
                          code_redemptions AS code, rk FROM (
                          SELECT *, ROW_NUMBER() OVER (PARTITION BY event ORDER BY code_redemptions DESC) AS rk
                          FROM {_M_CLUB_EVENT})
                        WHERE rk <= 3 AND code_redemptions > 0 ORDER BY event, rk""")[cols]
    except Exception:
        return pd.DataFrame(columns=cols)

def club_participation() -> pd.DataFrame:
    """ALL athlete-declared clubs from the walled supertri_marketing.v_club_participation (count-only,
    revenue-free), aggregated to portfolio club grain. Defensive: empty until the walled view resolves."""
    cols = ["club", "club_code", "in_register", "athletes", "registrations", "events"]
    try:
        return D._q("""SELECT club, ANY_VALUE(club_code) club_code, LOGICAL_OR(in_register) in_register,
                         SUM(athletes) athletes, SUM(registrations) registrations, COUNT(DISTINCT event) events
                       FROM `$P.supertri_marketing.v_club_participation`
                       GROUP BY club ORDER BY athletes DESC, registrations DESC""")[cols]
    except Exception:
        return pd.DataFrame(columns=cols)


# ── Landing forecast (mirror of data.landing_forecast; walled reg-count views) ──────────────────
def _landing_band(cur_mtr, actual_now, prior_at_now, prior_final, plan_final):
    """Race-day landing band from the ramp curve — mirror of data._landing_band. Returns
    (low, expected, high, confidence, note). Ratio central once ≤6mo with a representative prior,
    else remaining-adds; band widens with distance, capped at 1.5× remaining-adds."""
    a = float(actual_now or 0)
    pf = float(prior_final) if (prior_final not in (None, 0) and pd.notna(prior_final)) else None
    pan = float(prior_at_now or 0)
    if pf is None:
        return None, None, None, "NO PRIOR", "first edition — no prior curve to project; plan-only"
    remaining = a + (pf - pan)
    ratio = (a * pf / pan) if pan > 0 else None
    representative = pan >= 0.15 * pf
    reliable = (cur_mtr is not None and cur_mtr <= 6 and representative and ratio is not None)
    if reliable:                                           conf, w, exp = "HIGH", 0.05, (ratio + remaining) / 2
    elif cur_mtr is not None and cur_mtr <= 9 and pan > 0: conf, w, exp = "MED", 0.12, remaining
    else:                                                  conf, w, exp = "LOW", 0.22, remaining
    methods = [remaining] + ([ratio] if ratio is not None else [])
    cap = 1.5 * remaining
    lo = max(min(min(methods), exp * (1 - w)), a)
    hi = min(max(max(methods), exp * (1 + w)), cap)
    exp = max(lo, min(exp, hi))
    note = "prior hadn't started selling this early — directional only" if pan == 0 else ""
    return round(lo), round(exp), round(hi), conf, note


def landing_forecast() -> pd.DataFrame:
    """Race-day landing forecast for ordering — every currently-selling edition, ranked by upcoming race.
    From the walled v_ramp_trajectory (reg counts) + v_reg_year_book (race dates). Revenue-free."""
    cols = ["event", "event_code", "race_date", "cur_mtr", "actual_now", "last_year", "plan",
            "low", "expected", "high", "confidence", "note", "no_prior"]
    t = D._q("SELECT event_code, edition_year, mtr, act_cum, prior_cum, plan_cum, is_current "
             "FROM `$P.supertri_marketing.v_ramp_trajectory`")
    ed = D._q("SELECT event_code, CAST(edition_year AS INT64) edition_year, CAST(race_date AS DATE) race_date "
              "FROM `$P.supertri_marketing.v_reg_year_book`")
    if not len(t):
        return pd.DataFrame(columns=cols)
    rows = []
    for (ec, ey), sub in t.groupby(["event_code", "edition_year"]):
        cur = sub[sub.is_current]
        cur_mtr = int(cur.mtr.iloc[0]) if len(cur) else None
        actual_now = float(cur.act_cum.iloc[0]) if len(cur) else 0.0
        prior_at_now = float(cur.prior_cum.iloc[0]) if len(cur) else 0.0
        m0 = sub[sub.mtr == 0]
        pf = float(m0.prior_cum.iloc[0]) if (len(m0) and pd.notna(m0.prior_cum.iloc[0])) else None
        plan_final = float(m0.plan_cum.iloc[0]) if (len(m0) and pd.notna(m0.plan_cum.iloc[0])) else None
        lo, exp, hi, conf, note = _landing_band(cur_mtr, actual_now, prior_at_now, pf, plan_final)
        rows.append(dict(event_code=ec, race_date=None, cur_mtr=cur_mtr, actual_now=round(actual_now),
                         last_year=(round(pf) if pf else None), plan=(round(plan_final) if plan_final else None),
                         low=lo, expected=exp, high=hi, confidence=conf, note=note, no_prior=(pf is None), _ey=ey))
    df = pd.DataFrame(rows)
    # A cancelled edition has no race day to land on — drop it from the ordering forecast.
    if len(df):
        df = df[[not _is_cancelled(ec, ey) for ec, ey in zip(df.event_code, df._ey)]].reset_index(drop=True)
    if not len(df):
        return pd.DataFrame(columns=cols)
    edm = {(r.event_code, r.edition_year): r.race_date for r in ed.itertuples()} if len(ed) else {}
    df["race_date"] = [edm.get((ec, ey)) for ec, ey in zip(df.event_code, df._ey)]
    df["event"] = df.event_code.map(D.CODE_DISP).fillna(df.event_code)
    return df.sort_values("race_date", na_position="last").reset_index(drop=True)[cols]


def landing_curves(codes) -> pd.DataFrame:
    """WEEKLY curves for the landing-forecast projection charts (v2) — walled v_ramp_trajectory_weekly."""
    cols = ["event_code", "wtr", "act_cum", "prior_cum", "plan_cum", "is_current"]
    if not len(codes):
        return pd.DataFrame(columns=cols)
    inl = "(" + ",".join(f"'{c}'" for c in codes) + ")"
    return D._q(f"SELECT event_code, wtr, act_cum, prior_cum, plan_cum, is_current "
                f"FROM `$P.supertri_marketing.v_ramp_trajectory_weekly` WHERE event_code IN {inl} "
                f"ORDER BY event_code, wtr DESC")[cols]
