"""Supertri — MARKETING dashboard (external / agency-shareable).

A registrations-only cut of the board: NO revenue, ATV, forecast-revenue or any financial data. All
data access goes through market_data.py, which selects only non-financial columns. Intended for a
SEPARATE deployment behind a read-only service account scoped to revenue-free views. Deployed as a
PUBLIC Streamlit Community Cloud app (the board holds the one free private slot), so a shared-password
gate (`_password_gate`, secret `app_password`) restricts access — it fails closed on the cloud and is
skipped for local dev.
    streamlit run supertri_registration_tracker/app_marketing.py
"""
import base64
import os

import pandas as pd
import streamlit as st
from PIL import Image

import data
import market_data as md
import render as R
import theme

_ASSETS = os.path.join(os.path.dirname(__file__), "assets")


def _asset_uri(name):
    with open(os.path.join(_ASSETS, name), "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()


def _password_gate():
    """Shared-password login for the public marketing deploy. Runs BEFORE any data query. Fail-closed on
    the cloud: if the app is deployed (a service-account secret is present) but no `app_password` secret is
    set, access is blocked rather than opened. Skipped entirely for local dev (ADC, no secrets)."""
    if st.session_state.get("mkt_auth"):
        return
    try:
        is_cloud = "gcp_service_account" in st.secrets
        configured = st.secrets.get("app_password")
    except Exception:
        is_cloud, configured = False, None
    if not is_cloud:
        return   # local dev — no gate
    st.markdown(
        f'<div class="brandbar"><img class="wm" src="{_asset_uri("wordmark_yellow.png")}" alt="supertri"/>'
        f'<span class="title">Registrations</span><span class="tag">MARKETING VIEW</span></div>',
        unsafe_allow_html=True)
    if not configured:
        st.error("Access isn't configured yet — please contact the Supertri team.")
        st.stop()
    st.markdown("#### This dashboard is private")
    st.caption("Enter the access password shared with you by the Supertri team.")
    with st.form("login"):
        pw = st.text_input("Access password", type="password", label_visibility="collapsed",
                           placeholder="Access password")
        if st.form_submit_button("Enter", type="primary"):
            if pw == configured:
                st.session_state["mkt_auth"] = True
                st.rerun()
            else:
                st.error("Incorrect password.")
    st.stop()


st.set_page_config(page_title="Supertri Registrations — Marketing",
                   page_icon=Image.open(os.path.join(_ASSETS, "favicon.png")), layout="wide")
theme.install()
st.markdown(theme.CSS, unsafe_allow_html=True)
_password_gate()

# ───────────────────────────────────────────────────────── sidebar
st.sidebar.caption("Registration insights · **marketing view**")
SECTIONS = [
    "1 · Registrations vs plan (by season)",
    "◆ Registration ramps (plan vs last year)",
    "2 · Participant profile",
    "3 · Athlete mix (journey / goal)",
    "4 · Event format mix",
    "5 · Returning rate",
]
sec = st.sidebar.radio("View", SECTIONS, label_visibility="collapsed")
st.sidebar.divider()
st.sidebar.caption(f"As-of **{data.AS_OF:%d %b %Y}** · seasons **{md.BASELINE_YEAR}** & **{md.LIVE_CYCLE}**")
st.sidebar.caption("**Registrations only** — this view carries no revenue or financial data.")

# ───────────────────────────────────────────────────────── brand header band
st.markdown(
    f'<div class="brandbar"><img class="wm" src="{_asset_uri("wordmark_yellow.png")}" alt="supertri"/>'
    f'<span class="title">Registrations</span>'
    f'<span class="tag">MARKETING VIEW</span></div>', unsafe_allow_html=True)


def _event_pick(scopes):
    evs = sorted(e for e in scopes if e != "PORTFOLIO")
    return st.selectbox("Event", evs) if evs else None


# ═════════════════════════════════════════════════════ 1. REGISTRATIONS VS PLAN
if "Registrations vs plan" in sec:
    st.header("Registrations vs plan — by season")
    R.decision("How each event's registrations are pacing against the season's plan — by season, never blended.")
    R.caveat("**Registrations only.** This dashboard carries no revenue, pricing or financial data.")

    st.caption("One season at a time. **EOLM** = end of last closed month · **Current** = this month "
               "(Forecast = full month, Actual = to-date, GAP = Actual − Forecast) · **EOTM** = end of "
               "this month · **%** = Actual ÷ Forecast · **Wks** = weeks to race. Passed editions show "
               "only Race day, Target and EOTM Actual.")

    def block(season):
        yb = md.year_book_reg(season)
        reg, meta = md.weekly_reg(season)
        st.markdown(f"## {season} season")
        if not len(yb):
            st.info("No editions for this season yet."); return
        sell = int((yb.status == "selling").sum()); done = int((yb.status == "completed").sum())
        tot_t = pd.to_numeric(yb.reg_target, errors="coerce").sum()
        tot_a = pd.to_numeric(yb.reg_act, errors="coerce").sum()
        k = st.columns(3)
        k[0].metric("Events selling", f"{sell} / {len(yb)}", f"{done} completed", delta_color="off")
        k[1].metric("Registrations to date", f"{tot_a:,.0f}")
        k[2].metric("% of season target", f"{100*tot_a/tot_t:.0f}%" if tot_t else "—")
        R.avf_reg_table(reg, meta, md.prior_year_thismonth(season))

    block(md.BASELINE_YEAR)
    st.divider()
    block(md.LIVE_CYCLE)
    st.caption("Forecast = the modelled registration plan. GAP is neutral — mid-month it is naturally "
               "negative (the month's remaining sell). Trend = registration momentum (this 3 weeks vs the "
               "prior 3) with the WoW %; ▲ rising · ▼ softening · ▬ flat. Passed editions show no trend.")

# ═════════════════════════════════════════════════════ REGISTRATION RAMPS
elif "Registration ramps" in sec:
    st.header("Registration ramps — plan vs last year")
    st.caption("**Registrations.** For each event's live selling cycle: cumulative **registrations** over the "
               "selling calendar — **Last year** (faint dotted grey) · **Plan** (gold) · **Actual so far** "
               "(bright black, to date). The **EOLM** panel gives the absolute registration counts for all three "
               "at end of last closed month; the action is derived from Actual vs Plan and vs Last year at EOLM.")
    R.render_ramp_tab(md.ramp_trajectory(), data.AS_OF)

# ═════════════════════════════════════════════════════ 2. PARTICIPANT PROFILE
elif "Participant profile" in sec:
    st.header("Participant profile")
    R.decision("Who the field is — gender balance and age structure, per event and over recent years.")
    gender, age, avgage = md.profile_v2()

    def block(scope):
        R.stacked_100_by_year(gender[gender.scope == scope][["year", "answer", "n"]],
                              "Gender balance", colors=R.GENDER_COLORS)
        R.stacked_100_by_year(age[age.scope == scope][["year", "answer", "n"]],
                              "Age groups", colors=R.AGE_COLORS, order=md.AGE_ORDER)
        av = avgage[avgage.scope == scope].sort_values("year")
        if len(av):
            st.caption("**Average age** · " + "  ·  ".join(
                f"{int(r.year)} → {r.avg_age:.1f}" for r in av.itertuples() if pd.notna(r.avg_age)))

    st.subheader("Portfolio — all events"); block("PORTFOLIO")
    st.subheader("By event")
    ev = _event_pick(gender.scope.unique())
    if ev:
        block(ev)
    R.caveat("Gender/age are declared demographic fields. Recent cycles; the current cycle is early/partial.")

# ═════════════════════════════════════════════════════ 3. ATHLETE MIX
elif "Athlete mix" in sec:
    st.header("Athlete mix — journey · goal · how they keep fit")
    R.decision("First-timers vs returning athletes, race-day goals, and how the field keeps fit.")
    mx = md.athlete_mix_v2()

    def block(scope):
        for label in [q for _, q in md.MIX_QUESTIONS]:
            sub = mx[(mx.scope == scope) & (mx.question == label)][["year", "answer", "n"]]
            j = label == "Triathlon journey"
            R.stacked_100_by_year(sub, label,
                                  colors=R.JOURNEY_COLORS if j else None,
                                  order=list(R.JOURNEY_COLORS) if j else None)

    st.subheader("Portfolio — all events"); block("PORTFOLIO")
    st.subheader("By event")
    ev = _event_pick(mx.scope.unique())
    if ev:
        block(ev)
    R.caveat("Journey / goal / keep-fit are collected on the current-cycle registration form, so earlier "
             "years read empty by design.")

# ═════════════════════════════════════════════════════ 4. EVENT FORMAT MIX
elif "format mix" in sec:
    st.header("Event format mix")
    R.decision("The share of registrations by race format, per event and over recent years.")
    fs = md.yield_share()

    def block(scope):
        sub = fs[fs.scope == scope][["year", "fmt", "regs"]].rename(columns={"fmt": "answer", "regs": "n"})
        R.stacked_100_by_year(sub, "Format share", colors=R.FMT_COLORS, order=md.FMT_ORDER)

    if not len(fs):
        st.info("No format data yet.")
    else:
        st.subheader("Portfolio — all events"); block("PORTFOLIO")
        st.subheader("By event")
        ev = _event_pick(fs.scope.unique())
        if ev:
            block(ev)
    R.caveat("Share of registrations by format (ENDURO / Olympic / Sprint / SuperSprint / other). "
             "No revenue or per-head yield is shown.")

# ═════════════════════════════════════════════════════ 5. RETURNING RATE
elif "Returning rate" in sec:
    st.header("Returning-participant rate")
    R.decision("How much of each field is returning athletes vs new — a read on loyalty.")
    R.stamp(f"Completed-cohort metric — portfolio + trend through {md.BASELINE_YEAR}; by-event also shows "
            f"the in-progress {md.LIVE_CYCLE} cohort where an edition is already selling.")
    rb = md.returning_breakdown()
    st.subheader("Portfolio — all events"); R.returning_table(rb, "PORTFOLIO")
    st.subheader("By event")
    ev = _event_pick(rb.event_display.unique())
    if ev:
        R.returning_table(rb, ev, through_live=True)
    R.caveat("Returning rate = **FLOOR** (email-exact match, hashed; no name/DOB fallback), so true "
             "retention is at least this. New + YoY + Earlier Retention = Total.")
