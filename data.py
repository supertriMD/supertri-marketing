"""Supertri MARKETING dashboard — slim data-access layer (registrations-only, revenue-free).

A minimal subset of the board's data layer: ONLY the shared constants + the BigQuery query helper the
marketing app (app_marketing.py / market_data.py / render.py) needs. It reads only the revenue-free
`supertri_marketing.*` views via a service account scoped to that dataset. NO board revenue / ledger /
forecast logic and no financial view names live here — so this file is safe in a public repo.
"""
from __future__ import annotations
import os  # noqa: F401  (kept for parity; not required)

import numpy as np  # noqa: F401  (imported by callers via this module's namespace expectations)
import pandas as pd

USE_LIVE = True
PROJECT, LOCATION = "supertri-reg-analytics", "EU"

# event code → display name, currency, canonical key, and board ordering
CODE_DISP = {"AUS": "Austin", "BLE": "Blenheim", "LB": "Long Beach", "NJ": "New Jersey",
             "TOR": "Toronto", "TOR_10K": "Toronto 10K", "CHI": "Chicago",
             "KER": "Kerrville", "TOU": "Toulouse"}
CCY = {"Austin": "USD", "Blenheim": "GBP", "Long Beach": "USD", "New Jersey": "USD",
       "Toronto": "CAD", "Toronto 10K": "CAD", "Chicago": "USD", "Kerrville": "USD",
       "Toulouse": "EUR"}
_CANON = {"Austin": "austin", "Blenheim": "blenheim", "Long Beach": "long_beach",
          "New Jersey": "new_jersey", "Toronto": "toronto", "Toronto 10K": "toronto_10k",
          "Chicago": "chicago", "Kerrville": "kerrville", "Toulouse": "toulouse", "PORTFOLIO": "ALL_EVENTS"}
_EVENT_ORDER = ["Austin", "Blenheim", "Long Beach", "New Jersey", "Toronto", "Toronto 10K",
                "Chicago", "Kerrville", "Toulouse"]

# ── BigQuery access ──────────────────────────────────────────────────────────
_CLIENT = None
def _bq():
    """BigQuery client. On Streamlit Cloud, auth from st.secrets['gcp_service_account']; locally, ADC."""
    global _CLIENT
    if _CLIENT is None:
        from google.cloud import bigquery
        creds = None
        try:
            import streamlit as st
            if "gcp_service_account" in st.secrets:
                from google.oauth2 import service_account
                creds = service_account.Credentials.from_service_account_info(
                    dict(st.secrets["gcp_service_account"]))
        except Exception:
            creds = None   # no secrets context (local ADC) — fine
        _CLIENT = bigquery.Client(project=PROJECT, location=LOCATION, credentials=creds)
    return _CLIENT

# Cache BQ results for 6h (snappier warm app; still surfaces the daily refresh). No-op if streamlit absent.
try:
    import streamlit as _st
    _bq_cache = _st.cache_data(ttl="6h", show_spinner=False)
except Exception:                                           # pragma: no cover
    def _bq_cache(fn):
        return fn


@_bq_cache
def _q(sql: str) -> pd.DataFrame:
    """Run a query against live BigQuery, return a DataFrame. create_bqstorage_client=False keeps the
    scoped SA to Data Viewer + Job User. Normalises the Chicago lineage label for display."""
    df = _bq().query(sql.replace("$P", PROJECT)).result().to_dataframe(create_bqstorage_client=False)
    return df.replace(r"Chicago Triathlon", "Chicago", regex=True)


def _disp(canon: str) -> str:
    for d, c in _CANON.items():
        if c == canon:
            return d
    return str(canon).replace("_", " ").title()


def _order_events(df, col="event"):
    """Stable ordering: events first (as listed), portfolios last."""
    order = {e: i for i, e in enumerate(_EVENT_ORDER + ["PORTFOLIO", "PORTFOLIO -NJ"])}
    return (df.assign(_o=df[col].map(lambda e: order.get(e, 50)))
              .sort_values("_o").drop(columns="_o").reset_index(drop=True))


def _reporting_week():
    """Live 'as-of' = the config-driven reporting week. Under the scoped marketing SA the direct
    supertri_config read is denied, so it falls back to the literal below — keep that current, or add a
    supertri_marketing.v_settings view exposing reporting_week and point this there."""
    if USE_LIVE:
        try:
            df = _q("SELECT CAST(reporting_week AS DATE) AS d FROM `$P.supertri_config.settings` LIMIT 1")
            if len(df) and pd.notna(df.d.iloc[0]):
                return pd.Timestamp(df.d.iloc[0])
        except Exception:
            pass
    return pd.Timestamp("2026-07-16")


AS_OF = _reporting_week()
LIVE_CYCLE = 2027
BASELINE_YEAR = 2026
RECENT_YEARS = [2025, 2026, 2027]

# enrichment lineage filter (real BQ labels), canonical grains, and demographic SQL fragments
_ELIG_LINEAGE = ["Austin", "Blenheim", "Toronto", "Toronto 10K", "Long Beach", "New Jersey",
                 "Chicago Triathlon", "Toulouse", "Kerrville"]
_CORE_CANON = ["austin", "blenheim", "toronto", "toronto_10k", "long_beach", "new_jersey",
               "chicago", "toulouse", "kerrville"]
_ELIG_SQL = "(" + ",".join(f"'{l}'" for l in _ELIG_LINEAGE) + ")"
FMT_ORDER = ["ENDURO", "Olympic", "Sprint", "SuperSprint", "other"]
AGE_ORDER = ["<25", "25-34", "35-44", "45-54", "55+"]
MIX_QUESTIONS = [("tri_journey", "Triathlon journey"), ("race_day_goal", "Race-day goal"),
                 ("fitness_activity", "How do you keep fit?")]
_FMT_CASE = """CASE
  WHEN distance_normalized IN ('Enduro','Triple Challenge') THEN 'ENDURO'
  WHEN distance_normalized='Olympic' THEN 'Olympic'
  WHEN distance_normalized IN ('Sprint','Para Series') THEN 'Sprint'
  WHEN distance_normalized='Super Sprint' THEN 'SuperSprint'
  ELSE 'other' END"""
_AGE_CASE = """CASE WHEN a<25 THEN '<25' WHEN a<35 THEN '25-34' WHEN a<45 THEN '35-44'
                    WHEN a<55 THEN '45-54' ELSE '55+' END"""
