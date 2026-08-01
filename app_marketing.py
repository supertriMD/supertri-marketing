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
    "Reg vs Plan",
    "Landing forecast",
    "Gender / Age",
    "Where from",
    "Motivation",
    "Format mix",
    "Retention",
    "Cross-event Migration",
    "Corporate Challenge",
]
sec = st.sidebar.radio("View", SECTIONS, label_visibility="collapsed")
st.sidebar.divider()
st.sidebar.caption(f"Updated **{data.DATA_UPDATED:%d %b %Y}** · seasons **{md.BASELINE_YEAR}** & **{md.LIVE_CYCLE}**")
st.sidebar.caption("**Registrations only** — this view carries no revenue or financial data.")

# ───────────────────────── brand header band — names the active view (MARKETING VIEW = revenue-free)
_band = sec   # band mirrors the sidebar label
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
if "Reg vs Plan" in sec:

    def block(season):
        yb = md.year_book_reg(season)
        reg, meta = md.weekly_reg(season)
        if not len(yb):
            R.season_title(f"{season} season"); st.info("No editions for this season yet."); return
        sell = int((yb.sell_state == "selling").sum())
        R.season_title(f"{season} season", f"{sell} of {len(yb)} selling")
        tot_t = pd.to_numeric(yb.reg_target, errors="coerce").sum()
        tot_a = pd.to_numeric(yb.reg_act, errors="coerce").sum()
        # Portfolio EOLM vs Forecast — board parity (owner, 27 Jul): a COMPLETED edition is measured vs its
        # PLAN (reg_target), NOT final-as-forecast (which zeroed its own variance and hid the shortfall); a
        # still-selling edition vs its EOLM forecast. So target = Σ(completed plan) + Σ(selling EOLM fcst),
        # against the same actual (completed final + selling EOLM actual). Matches the board's AvF KPI exactly.
        done_ev = set(yb[yb.sell_state == "passed"].event) if "sell_state" in yb.columns else set(yb[yb.status == "completed"].event)
        ybd = yb[yb.event.isin(done_ev)]
        _sell = reg[~reg.event.str.upper().str.startswith("PORTFOLIO") & ~reg.event.isin(done_ev)]
        _ea = (pd.to_numeric(ybd.reg_act, errors="coerce").sum()
               + pd.to_numeric(_sell.eolm_act, errors="coerce").sum())
        _ef = (pd.to_numeric(ybd.reg_target, errors="coerce").sum()
               + pd.to_numeric(_sell.eolm_fcst, errors="coerce").sum())
        reg_gap = (_ea / _ef - 1) if _ef else np.nan
        R.cards_row([   # 2 cards, matching the board's Actuals-vs-Forecast layout (Editions-settled dropped)
            R.kpi("Registrations · EOLM", f"{_ea:,.0f}",
                  f"{reg_gap:+.0%} vs Forecast" if pd.notna(reg_gap) else ""),
            R.kpi("Registrations to date", f"{tot_a:,.0f}", f"{tot_a/tot_t:.0%} of target" if tot_t else ""),
        ])
        yb_done = yb[yb.event.isin(done_ev)]   # same set as the KPI (sell_state='passed'), board-consistent
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

# ═════════════════════════════════════════════════════ 1b. LANDING FORECAST
elif "Landing forecast" in sec:
    lf = md.landing_forecast()
    if not len(lf):
        st.info("No landing forecast available.")
    else:
        _today = pd.Timestamp.today().normalize()
        _bnd = lf[lf.expected.notna()]
        p_exp, p_lo, p_hi = int(_bnd.expected.sum()), int(_bnd.low.sum()), int(_bnd.high.sum())
        _np_n = int(lf.no_prior.sum())
        cards = [R.kpi("All selling editions · expected on race day", f"{p_exp:,}", "",
                       f"order range {p_lo:,} – {p_hi:,}"),
                 R.kpi("Ordering-ready now (≤90 days)",
                       f"{int((pd.to_datetime(lf.race_date) - _today).dt.days.le(90).sum())} of {len(lf)}",
                       "", "the rest tighten as they approach")]
        if _np_n:
            cards.append(R.kpi("No prior curve", f"{_np_n}", "", "first-year event — plan-only"))
        R.cards_row(cards)
        R.insight("Projected race-day participants for <b>ordering</b> — every currently-selling edition, next race "
                  "first. Data-driven (registration curve + prior-year shape), <b>not</b> the plan. Reliable ~3–6 "
                  "months out; directional before that. Expected = central; band = low–high.")

        _sc = max(9500.0, float(lf.high.max()) * 1.05) if lf.high.notna().any() else 9500.0
        _pct = lambda v: max(0.0, min(100.0, 100.0 * float(v) / _sc))
        def _out(rd):
            if pd.isna(rd): return "—"
            d = (pd.Timestamp(rd) - _today).days
            return "raced" if d < 0 else (f"{round(d/7)} wk" if d < 70 else f"{round(d/30.4)} mo")
        _cc = {"HIGH": "g", "MED": "a", "LOW": "m", "NO PRIOR": "np"}
        LF_CSS = f"""<style>
        table.lf{{border-collapse:collapse;width:100%;font-size:12.5px;font-variant-numeric:tabular-nums;background:#fff;margin:2px 0 6px;border:1px solid {theme.HAIRLINE};border-radius:12px;overflow:hidden}}
        table.lf th,table.lf td{{padding:7px 9px;text-align:right;white-space:nowrap;border-bottom:1px solid {theme.HAIRLINE}}}
        table.lf th{{font-size:9px;text-transform:uppercase;letter-spacing:.03em;color:{theme.MUTED};font-weight:700;background:{theme.OFF_WHITE}}}
        table.lf th.l,table.lf td.l{{text-align:left}}
        table.lf td.ev{{font-weight:700;color:{theme.INK}}}
        table.lf td.exp{{font-weight:800;color:{theme.INK};font-size:13.5px}}
        table.lf tr.soon td{{background:rgba(255,244,0,.09)}}
        .cf{{display:inline-block;font-size:9px;font-weight:800;border-radius:20px;padding:2px 7px}}
        .cf.g{{background:#d8f5e0;color:#12703a}}.cf.a{{background:#fff2c2;color:#7a5b00}}.cf.m{{background:#ececec;color:#777}}.cf.np{{background:#ffe0e0;color:#a33}}
        .lbar{{position:relative;height:16px;width:150px;background:{theme.HAIRLINE};border-radius:3px;display:inline-block;vertical-align:middle}}
        .lbar .sg{{position:absolute;top:0;height:100%;background:{theme.GOLD};opacity:.85;border-radius:3px}}
        .lbar .dt{{position:absolute;top:-3px;width:3px;height:22px;background:{theme.INK};border-radius:2px}}
        .lbar .tk{{position:absolute;top:1px;width:2px;height:14px}}
        </style>"""
        rws = []
        for r in lf.itertuples():
            soon = (not pd.isna(r.race_date)) and (pd.Timestamp(r.race_date) - _today).days <= 90
            conf = f'<span class="cf {_cc.get(r.confidence,"m")}">{r.confidence}</span>'
            ly = f"{int(r.last_year):,}" if pd.notna(r.last_year) else "—"
            pl = f"{int(r.plan):,}" if pd.notna(r.plan) else "—"
            if r.no_prior or pd.isna(r.expected):
                cells = f'<td class="l" colspan="3" style="color:{theme.MUTED};font-style:italic;text-align:center">{r.note}</td>'
                bar = (f'<div class="lbar"><div class="tk" style="left:{_pct(r.plan)}%;background:{theme.ACCENT2}"></div>'
                       f'<div class="dt" style="left:{_pct(r.actual_now)}%;background:{theme.MUTED}"></div></div>') if pd.notna(r.plan) else ""
            else:
                cells = f'<td>{int(r.low):,}</td><td class="exp">{int(r.expected):,}</td><td>{int(r.high):,}</td>'
                bar = (f'<div class="lbar"><div class="sg" style="left:{_pct(r.low)}%;width:{_pct(r.high)-_pct(r.low)}%"></div>'
                       f'<div class="dt" style="left:{_pct(r.expected)}%"></div>'
                       f'<div class="tk" style="left:{_pct(r.last_year)}%;background:#9B6BDF"></div>'
                       f'<div class="tk" style="left:{_pct(r.plan)}%;background:{theme.ACCENT2}"></div></div>')
            rws.append(f'<tr class="{"soon" if soon else ""}"><td class="ev l">{r.event}</td>'
                       f'<td class="l">{"" if pd.isna(r.race_date) else pd.Timestamp(r.race_date).strftime("%-d %b %y")}</td>'
                       f'<td>{_out(r.race_date)}</td><td class="l">{conf}</td><td>{ly}</td><td>{pl}</td>'
                       f'{cells}<td class="l">{bar}</td></tr>')
        st.markdown(LF_CSS + '<table class="lf"><thead><tr>'
                    '<th class="l">Event</th><th class="l">Race day</th><th>Out</th><th class="l">Conf.</th>'
                    '<th>Last yr</th><th>Plan</th><th>Low</th><th>Expected</th><th>High</th>'
                    f'<th class="l">Range · <span style="color:#9B6BDF">LY</span> <span style="color:{theme.ACCENT2}">Plan</span></th>'
                    '</tr></thead><tbody>' + "".join(rws) + '</tbody></table>', unsafe_allow_html=True)
        st.caption("Highlighted rows race within ~90 days (tight bands — order now). **Expected** = central; the "
                   "**band** widens with distance to race. Band on a monthly cadence; the projection curves below run "
                   "**weekly** (finer through the final 10 weeks). Registrations only · **no revenue data**.")

        st.subheader("Projection curves — next 3 races")
        _top3 = lf.head(3)
        _cur = md.landing_curves(list(_top3.event_code))
        for _col, (_, _r) in zip(st.columns(len(_top3)), _top3.iterrows()):
            with _col:
                st.plotly_chart(R.landing_fig(_r.event, _cur[_cur.event_code == _r.event_code], _r),
                                use_container_width=True)
        st.caption("Solid = registrations to date · dashed ink = expected path to race day · gold band = low–high · "
                   "dotted purple = last year (dotted teal = plan where there's no prior). x = months to race.")

# ═════════════════════════════════════════════════════ 2. PARTICIPANT PROFILE
elif "Gender" in sec:
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

# ═════════════════════════════════════════════════ 2b. WHERE FROM
elif "Where from" in sec:
    ot = md.origin_tiers()

    def block(scope):
        sub = ot[ot.scope == scope][["year", "tier", "n"]].rename(columns={"tier": "answer"})
        R.stacked_100_by_year(sub, "Home location relative to the race venue",
                              colors=R.ORIGIN_COLORS, order=md.ORIGIN_TIERS)
        tot = sub.groupby("year").n.sum()
        unk = sub[sub.answer == "Unknown"].groupby("year").n.sum()
        cov = " · ".join(f"{int(y)} {100*(1 - unk.get(y, 0)/tot[y]):.0f}%" for y in sorted(tot.index) if tot[y])
        st.caption(f"Geo coverage (rows with a matched home location): {cov}. "
                   "🎯 Local ≤15 mi is a city-name proxy.")

    if not len(ot):
        st.info("No origin data available.")
    else:
        st.subheader("Portfolio — all events"); block("PORTFOLIO")
        st.subheader("By event")
        ev = _event_pick(ot.scope.unique())
        if ev:
            block(ev)

# ═════════════════════════════════════════════════════ 3. ATHLETE MIX
elif "Motivation" in sec:
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
elif "Format mix" in sec:
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
elif "Retention" in sec:
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

# ═════════════════════════════════════════════════════ 7. CORPORATE CHALLENGE
elif "Corporate" in sec:
    be, em = md.corporate_challenge()
    if not len(be):
        st.info("No corporate challenge data yet.")
    else:
        _yr = md.CORP_YEARS[-1]
        _bl = be[be.year == _yr]
        _tot = int(_bl.corp.sum())
        _lb = _bl[_bl.event == "Long Beach"]
        _lb_pct = float(_lb.corp_pct.iloc[0]) if len(_lb) else np.nan
        _lb_n = int(_lb.corp.iloc[0]) if len(_lb) else 0
        _nev = int((_bl.corp > 0).sum())
        _e = lambda a: int(em[(em.year == _yr) & (em.answer == a)].n.sum())
        R.cards_row([
            R.kpi("Corporate athletes", f"{_tot:,}", "", f"across {_nev} events · {_yr}"),
            R.kpi("Long Beach — corporate share", f"{_lb_pct:.0f}%" if pd.notna(_lb_pct) else "—",
                  "", f"{_lb_n:,} of its field · the flagship"),
            R.kpi("Individual vs Relay", f"{_e('Individual'):,} / {_e('Relay'):,}", "", "corporate entries"),
        ])
        _chi = {int(r.year): int(r.corp) for r in be[be.event == "Chicago"].itertuples()}
        R.insight(f"<b>Corporate Challenge is a cross-cutting entry, not a distance</b> — these athletes race their "
                  f"real distance and are counted here as well. <b>Long Beach is the engine</b> "
                  f"(~{_lb_pct:.0f}% of its field, {_lb_n:,} athletes), while <b>Chicago is scaling</b> "
                  f"({_chi.get(2024, 0)}→{_chi.get(2025, 0)}→{_chi.get(2026, 0)} across 2024–26). Clear headroom to "
                  f"grow it at the other events.")
        CC_CSS = f"""<style>
        table.cc{{border-collapse:collapse;width:100%;font-size:12.5px;font-variant-numeric:tabular-nums;background:#fff;margin:2px 0 6px;border:1px solid {theme.HAIRLINE};border-radius:12px;overflow:hidden}}
        table.cc th,table.cc td{{padding:7px 12px;text-align:right;white-space:nowrap;border-bottom:1px solid {theme.HAIRLINE}}}
        table.cc th{{font-size:9.5px;text-transform:uppercase;letter-spacing:.04em;color:{theme.MUTED};font-weight:700;background:{theme.OFF_WHITE}}}
        table.cc th.l,table.cc td.ev{{text-align:left}}
        table.cc td.ev{{font-weight:700;color:{theme.INK}}}
        table.cc tr.top td{{background:rgba(255,244,0,.12)}}
        </style>"""
        st.subheader("Corporate participation by event")
        st.caption("Registrations in the Corporate Challenge and their share of each event's field · **Long Beach "
                   "highlighted** (the flagship) · Supertri staff excluded.")
        piv = be.pivot_table(index="event", columns="year", values="corp", fill_value=0).astype(int)
        pivp = be.pivot_table(index="event", columns="year", values="corp_pct", fill_value=0.0)
        _oc = _yr if _yr in piv.columns else piv.columns[-1]
        piv = piv.sort_values(_oc, ascending=False)
        yrs = list(piv.columns)

        def _cc(ev, y):
            if y not in piv.columns or piv.loc[ev, y] == 0:
                return "—"
            return f'{int(piv.loc[ev, y]):,} <span style="color:{theme.MUTED}">({pivp.loc[ev, y]:.1f}%)</span>'
        rws = "".join(f'<tr class="{"top" if ev == "Long Beach" else ""}"><td class="ev">{ev}</td>'
                      + "".join(f"<td>{_cc(ev, y)}</td>" for y in yrs) + "</tr>" for ev in piv.index)
        st.markdown(CC_CSS + '<table class="cc"><thead><tr><th class="l">Event</th>'
                    + "".join(f"<th>{int(y)}</th>" for y in yrs) + "</tr></thead><tbody>" + rws + "</tbody></table>",
                    unsafe_allow_html=True)

        st.subheader("Entry type — Individual vs Relay")
        R.stacked_100_by_year(em[["year", "answer", "n"]], "Corporate entry type",
                              colors=R.CORP_ENTRY_COLORS, order=["Individual", "Relay", "Unspecified"],
                              years=md.CORP_YEARS)
