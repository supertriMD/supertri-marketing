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

import numpy as np
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
    "2 · Participant profile",
    "3 · Athlete mix (journey / goal)",
    "4 · Event format mix",
    "5 · Returning rate",
    "6 · Cross-event migration",
]
sec = st.sidebar.radio("View", SECTIONS, label_visibility="collapsed")
st.sidebar.divider()
st.sidebar.caption(f"As-of **{data.AS_OF:%d %b %Y}** · seasons **{md.BASELINE_YEAR}** & **{md.LIVE_CYCLE}**")
st.sidebar.caption("**Registrations only** — this view carries no revenue or financial data.")

# ───────────────────────── brand header band — names the active view (MARKETING VIEW = revenue-free)
_band = ("Registrations vs Plan" if "Registrations vs plan" in sec
         else "Participant Profile" if "Participant profile" in sec
         else "Athlete Mix" if "Athlete mix" in sec
         else "Format Mix" if "format mix" in sec
         else "Returning Rate" if "Returning rate" in sec
         else "Cross-event Migration" if "Cross-event" in sec
         else "Registrations")
st.markdown(
    f'<div class="brandbar"><img class="wm" src="{_asset_uri("wordmark_yellow.png")}" alt="supertri"/>'
    f'<span class="title">{_band}</span>'
    f'<span class="tag">MARKETING VIEW</span></div>', unsafe_allow_html=True)


def _event_pick(scopes):
    evs = sorted(e for e in scopes if e != "PORTFOLIO")
    return st.selectbox("Event", evs) if evs else None


def _refit_reg(reg, drop_events):
    """Drop completed editions from the weekly reg frame + recompute the PORTFOLIO total over what remains."""
    body = reg[(~reg.event.isin(drop_events)) & (~reg.event.str.upper().str.startswith("PORTFOLIO"))]
    port = {"event": "PORTFOLIO", "trend": None, "wow_pct": np.nan}
    for c in ("total_target", "eolm_fcst", "eolm_act", "eotm_fcst", "eotm_act"):
        port[c] = pd.to_numeric(body[c], errors="coerce").sum(min_count=1)
    return pd.concat([body, pd.DataFrame([port])], ignore_index=True)


# ═════════════════════════════════════════════════════ 1. REGISTRATIONS VS PLAN
if "Registrations vs plan" in sec:

    def block(season):
        yb = md.year_book_reg(season)
        reg, meta = md.weekly_reg(season)
        if not len(yb):
            R.season_title(f"{season} season"); st.info("No editions for this season yet."); return
        sell = int((yb.sell_state == "selling").sum()); done = int((yb.sell_state == "passed").sum())
        future_n = int((yb.sell_state == "future").sum())
        R.season_title(f"{season} season", f"{sell} of {len(yb)} selling")
        tot_t = pd.to_numeric(yb.reg_target, errors="coerce").sum()
        tot_a = pd.to_numeric(yb.reg_act, errors="coerce").sum()
        # Portfolio EOLM vs Forecast — board parity (v_weekly_update_active): selling editions take their
        # end-of-last-closed-month actual/forecast from the pacing view; editions raced BEFORE that month
        # (dropped from the pacing view) contribute their final count as act = fcst, neutral to the gap —
        # so this matches the board's 'Registrations · EOLM' exactly rather than under-counting their actual.
        _yra = yb.set_index("event").reg_act
        _ea = _ef = 0.0
        for r in reg[~reg.event.str.upper().str.startswith("PORTFOLIO")].itertuples():
            if pd.notna(r.eolm_act):
                _ea += r.eolm_act; _ef += (r.eolm_fcst if pd.notna(r.eolm_fcst) else 0.0)
            else:
                _fin = _yra.get(r.event)
                _fin = float(_fin) if (_fin is not None and pd.notna(_fin)) else 0.0
                _ea += _fin; _ef += _fin
        reg_gap = (_ea / _ef - 1) if _ef else np.nan
        R.cards_row([
            R.kpi("Registrations · EOLM", f"{_ea:,.0f}",
                  f"{reg_gap:+.0%} vs Forecast" if pd.notna(reg_gap) else ""),
            R.kpi("Registrations to date", f"{tot_a:,.0f}", f"{tot_a/tot_t:.0%} of target" if tot_t else ""),
            R.kpi("Editions settled", f"{done} of {len(yb)}", "", f"{future_n} not yet open" if future_n else ""),
        ])
        done_ev = set(yb[yb.status == "completed"].event)
        yb_done = yb[yb.event.isin(done_ev)]
        if len(yb_done):
            st.subheader("Events Completed")
            R.completed_reg_table(yb_done)
        reg_sell = _refit_reg(reg, done_ev)
        if len(reg_sell[~reg_sell.event.str.upper().str.startswith("PORTFOLIO")]):
            st.subheader("Events Selling")
            R.avf_reg_table(reg_sell, meta)
        elif len(yb_done):
            st.caption("Every edition this season has completed — see the final results above.")

    block(md.BASELINE_YEAR)
    st.divider()
    block(md.LIVE_CYCLE)
    st.caption("Registrations only · Forecast = the modelled registration plan · GAP = the month's remaining "
               "sell · Trend = 3-week vs prior-3-week momentum · % = Actual ÷ Forecast.")

# ═════════════════════════════════════════════════════ 2. PARTICIPANT PROFILE
elif "Participant profile" in sec:
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

# ═════════════════════════════════════════════════════ 3. ATHLETE MIX
elif "Athlete mix" in sec:
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

# ═════════════════════════════════════════════════════ 4. EVENT FORMAT MIX
elif "format mix" in sec:
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

# ═════════════════════════════════════════════════════ 5. RETURNING RATE
elif "Returning rate" in sec:
    rb = md.returning_breakdown()
    st.subheader("Portfolio — all events"); R.returning_table(rb, "PORTFOLIO")
    st.subheader("By event")
    ev = _event_pick(rb.event_display.unique())
    if ev:
        R.returning_table(rb, ev, through_live=True)

# ═════════════════════════════════════════════════════ 6. CROSS-EVENT MIGRATION
elif "Cross-event" in sec:
    m = md.cross_event_migration()
    be = md.cross_event_by_event()
    pairs = md.cross_event_pairs(limit=8)
    if not len(be):
        st.info("No cross-event data yet.")
    else:
        top_count = be.iloc[0]
        top_rate = be.sort_values("cross_pct", ascending=False).iloc[0]
        top_pair = pairs.iloc[0] if len(pairs) else None
        cards = [
            R.kpi("Most cross-event athletes", f"{int(top_count.cross_athletes):,}", "",
                  f"{top_count.event} · {top_count.cross_pct:.1f}% of its field"),
            R.kpi("Strongest cross-sell rate", f"{top_rate.cross_pct:.0f}%", "",
                  f"{top_rate.event} · {int(top_rate.cross_athletes):,} athletes"),
        ]
        if top_pair is not None:
            cards.append(R.kpi("Biggest migration flow", f"{int(top_pair.shared):,}", "",
                               f"{top_pair.event_a} ↔ {top_pair.event_b}"))
        R.cards_row(cards)

        _mrate = {int(r.year): r.ge2_pct for r in m.itertuples()} if len(m) else {}
        if top_pair is not None:
            R.insight(f"Cross-event participation is <b>climbing as the brand matures</b> — the portfolio ≥2-event "
                      f"rate rose <b>{_mrate.get(2025, 0):.1f}% → {_mrate.get(2026, 0):.1f}%</b> (2025→2026; 2025 was "
                      f"year one, so nobody could be cross-event yet). It stays <b>geographically clustered</b>: the "
                      f"biggest flow is <b>{top_pair.event_a} ↔ {top_pair.event_b}</b> ({int(top_pair.shared)} shared) "
                      f"and <b>{top_rate.event}</b> cross-sells hardest (<b>{top_rate.cross_pct:.0f}%</b>). Focus "
                      f"cross-promotion inside geographic clusters.")

        CE_CSS = f"""<style>
        table.ce{{border-collapse:collapse;width:100%;font-size:12.5px;font-variant-numeric:tabular-nums;background:#fff;margin:2px 0 6px;border:1px solid {theme.HAIRLINE};border-radius:12px;overflow:hidden}}
        table.ce th,table.ce td{{padding:7px 12px;text-align:right;white-space:nowrap;border-bottom:1px solid {theme.HAIRLINE}}}
        table.ce th{{font-size:9.5px;text-transform:uppercase;letter-spacing:.04em;color:{theme.MUTED};font-weight:700;background:{theme.OFF_WHITE}}}
        table.ce th.l,table.ce td.l,table.ce td.ev{{text-align:left}}
        table.ce td.ev{{font-weight:700;color:{theme.INK}}}
        table.ce td.num{{font-weight:800;color:{theme.INK}}}
        table.ce tr.top td{{background:rgba(255,244,0,.12)}}
        table.ce .rank{{display:inline-block;width:19px;height:19px;line-height:19px;text-align:center;border-radius:50%;font-weight:800;font-size:10.5px;background:{theme.INK};color:{theme.YELLOW}}}
        table.ce .rankm{{color:{theme.MUTED};font-weight:700;padding-left:5px}}
        </style>"""

        st.subheader("Migration by event")
        st.caption("Athletes since 2025 and how many also raced ≥1 other Supertri event — **top 3 by count highlighted**.")
        top3 = list(be.head(3).event)
        rws = "".join(
            f'<tr class="{"top" if r.event in top3 else ""}">'
            f'<td class="l">{f"""<span class=rank>{i}</span>""" if r.event in top3 else f"""<span class=rankm>{i}</span>"""}</td>'
            f'<td class="ev">{r.event}</td><td>{int(r.athletes):,}</td>'
            f'<td class="num">{int(r.cross_athletes):,}</td><td>{r.cross_pct:.1f}%</td></tr>'
            for i, r in enumerate(be.itertuples(), 1))
        st.markdown(CE_CSS + '<table class="ce"><thead><tr><th class="l">#</th><th class="l">Event</th>'
                    '<th>Athletes</th><th>Cross-event</th><th>Cross rate</th></tr></thead><tbody>'
                    + rws + '</tbody></table>', unsafe_allow_html=True)

        st.subheader("Top migration pairs")
        prws = "".join(f'<tr><td class="ev">{r.event_a} ↔ {r.event_b}</td>'
                       f'<td class="num">{int(r.shared):,}</td></tr>' for r in pairs.itertuples())
        st.markdown('<table class="ce"><thead><tr><th class="l">Migration pair</th>'
                    '<th>Shared athletes</th></tr></thead><tbody>' + prws + '</tbody></table>',
                    unsafe_allow_html=True)

        st.subheader("Cross-event by year")
        st.caption("Of the athletes racing each event that year, how many are cross-event. **2025** = year one "
                   "(no history yet); **2027** = early presales — small and loyal-base-skewed; events not yet "
                   "raced in 2027 read 0.")
        by = md.cross_event_by_event_year()
        yrs = sorted(int(y) for y in by.yr.unique())
        piv = by.pivot_table(index="event", columns="yr", values="cross_ath", fill_value=0).astype(int)
        pivp = by.pivot_table(index="event", columns="yr", values="cross_pct", fill_value=0)
        _oc = 2026 if 2026 in piv.columns else piv.columns[-1]
        piv = piv.sort_values(_oc, ascending=False)

        def _yc(ev, y):
            if y not in piv.columns:
                return "—"
            return f'{int(piv.loc[ev, y]):,} <span style="color:{theme.MUTED}">({pivp.loc[ev, y]:.1f}%)</span>'
        rws = "".join(f'<tr><td class="ev">{ev}</td>' + "".join(f'<td>{_yc(ev, y)}</td>' for y in yrs) + '</tr>'
                      for ev in piv.index)
        mm = {int(r.year): r for r in m.itertuples()} if len(m) else {}

        def _pc(y):
            r = mm.get(y)
            return f'{int(r.ge2):,} <span style="color:{theme.MUTED}">({r.ge2_pct:.1f}%)</span>' if r is not None else "—"
        prow = ('<tr class="top"><td class="ev">PORTFOLIO · ≥2 events</td>'
                + "".join(f'<td class="num">{_pc(y)}</td>' for y in yrs) + '</tr>')
        thead = '<tr><th class="l">Event</th>' + "".join(f'<th>{y}{" · early" if y >= 2027 else ""}</th>' for y in yrs) + '</tr>'
        st.markdown('<table class="ce"><thead>' + thead + '</thead><tbody>' + rws + prow + '</tbody></table>',
                    unsafe_allow_html=True)
        st.caption("Cumulative distinct Supertri events raced since 2025 · Supertri staff excluded · **no revenue data**.")
