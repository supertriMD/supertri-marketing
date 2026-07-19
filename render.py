"""Shared, side-effect-free render helpers for the marketing (external) dashboard.

A standalone copy of the small set of chart/table helpers `app_marketing.py` needs — kept separate
from `app.py` (which runs top-level Streamlit code on import and can't be imported as a library) so the
live board app is never destabilised by the marketing build. If these two ever drift, reconcile by
extracting a single shared module; for now the marketing surface owns its own copy.
"""
import re as _re

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

import data
import theme

RECENT = data.RECENT_YEARS
BAR_HEIGHT = 173   # plot area 137 (=3 rows @ 25px) + 28px top for the above-bar legend + 8px bottom

# Brand-true category palettes (BRAND.md): off-black + gold + teal + violet + grey; NO RAG, NO bare yellow.
PALETTE_NONRAG = [theme.INK, theme.GOLD, theme.ACCENT2, "#9B6BDF", theme.MUTED, "#8a7000", "#12707a", "#b98b1f"]
JOURNEY_COLORS = {"Brand new to triathlon": theme.ACCENT2,
                  "New to Supertri, but raced before": theme.MUTED,
                  "Returning Supertri participant": theme.GOLD}
FMT_COLORS = {"ENDURO": theme.INK, "Olympic": theme.GOLD, "Sprint": theme.ACCENT2,
              "SuperSprint": theme.MUTED, "other": "#9B6BDF"}
GENDER_COLORS = {"MALE": theme.INK, "FEMALE": theme.GOLD, "NONBINARY": theme.ACCENT2,
                 "Male": theme.INK, "Female": theme.GOLD, "Non-binary": theme.ACCENT2}
AGE_COLORS = {"<25": theme.ACCENT2, "25-34": theme.GOLD, "35-44": theme.INK,
              "45-54": theme.MUTED, "55+": "#9B6BDF"}


def _b(t):
    return _re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)

def caveat(txt):
    st.markdown(f'<div class="caveat">⚠ {_b(txt)}</div>', unsafe_allow_html=True)

def stamp(txt):
    st.markdown(f'<span class="stamp">{txt}</span>', unsafe_allow_html=True)

def decision(txt):
    st.caption(f"**What this shows:** {txt}")

def insight(txt, tone=""):
    st.markdown(f'<div class="msg {tone}">{_b(txt)}</div>', unsafe_allow_html=True)

_f_int = lambda v: "—" if pd.isna(v) else f"{v:,.0f}"
_f_pct = lambda v: "—" if pd.isna(v) else f"{v:+.0%}"
_f_pct0 = lambda v: "—" if pd.isna(v) else f"{v:.0%}"


def stacked_100_by_year(df, title, colors=None, order=None, years=RECENT):
    """100% horizontal stacked bar, one row per recent year, coloured by `answer`. df: [year, answer, n].
    Every year in `years` is forced to render (empty = not-yet-collected) so bar thickness is constant;
    the legend sits above the bars."""
    st.markdown(f"**{title}**")
    d = df.copy()
    if not len(d):
        st.caption("— no data —"); return
    d["pct"] = 100 * d.n / d.groupby("year").n.transform("sum")
    d["yr"] = d.year.astype(int).astype(str)
    ans = order or sorted(d.answer.unique())
    cmap = colors or {a: PALETTE_NONRAG[i % len(PALETTE_NONRAG)] for i, a in enumerate(ans)}
    for _y in [str(y) for y in years if str(y) not in set(d.yr)]:
        d = pd.concat([d, pd.DataFrame([{"yr": _y, "answer": ans[0], "pct": 0.0}])], ignore_index=True)
    fig = px.bar(d, x="pct", y="yr", color="answer", orientation="h", color_discrete_map=cmap,
                 category_orders={"yr": [str(y) for y in reversed(years)], "answer": ans})
    fig.update_layout(title_text="", xaxis_title=None, yaxis_title=None, barmode="stack",
                      xaxis=dict(ticksuffix="%", range=[0, 100]), legend_title=None,
                      legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0),
                      height=BAR_HEIGHT, margin=dict(l=8, r=8, t=28, b=8))
    fig.update_traces(hovertemplate="%{y} · %{fullData.name}: %{x:.0f}%<extra></extra>")
    st.plotly_chart(fig, use_container_width=True)


def _np(n, p):
    return "—" if pd.isna(n) else f"{n:,.0f} ({p:.0f}%)"


def returning_table(rb, scope, through_live=False):
    """Per-scope returning breakdown (Year·Total·New·Retention·YoY·Earlier·Different) with a three-tier
    visual hierarchy on header + body. through_live extends past BASELINE_YEAR to the in-progress
    LIVE_CYCLE where that scope has data (used for the by-event table)."""
    d = rb[rb.event_display == scope].sort_values("year")
    if not len(d):
        st.caption("— no data —"); return
    d = d[d.year <= (data.LIVE_CYCLE if through_live else data.BASELINE_YEAR)]
    T = d.total.replace(0, np.nan)
    is_port = scope == "PORTFOLIO"
    disp = pd.DataFrame({
        "Year": d.year.astype(int).astype(str),
        "Total": d.total.map(lambda v: f"{v:,.0f}"),
        "New": [_np(n, 100*n/t) for n, t in zip(d.new, T)],
        "Retention": [_np(t - n, 100*(t - n)/t) for n, t in zip(d.new, T)],
        "YoY Retention": [_np(n, 100*n/t) for n, t in zip(d.yoy_ret, T)],
        "Earlier Retention": [_np(n, 100*n/t) for n, t in zip(d.earlier_ret, T)],
        "Different Event": (["—"] * len(d) if is_port else [_np(n, 100*n/t) for n, t in zip(d.diff_event, T)]),
    })
    LEAD = ["Year", "Total"]; SPLIT = ["New", "Retention"]
    def _tier(c): return "lead" if c in LEAD else ("split" if c in SPLIT else "detail")
    HEAD = {"lead":   f"font-weight:800;color:{theme.INK};background:#E7ECF3;border-bottom:2px solid #c3ccd8",
            "split":  f"font-weight:700;color:{theme.INK};background:#F1F4F8;border-bottom:2px solid #d9e0e9",
            "detail": f"font-weight:500;color:{theme.MUTED};background:transparent;border-bottom:1px solid #ececec"}
    BODY = {"lead":   f"font-weight:700;color:{theme.INK};background:#F4F6F9",
            "split":  f"font-weight:600;color:{theme.INK}",
            "detail": f"font-weight:400;color:{theme.MUTED}"}
    cols = list(disp.columns)
    _al = lambda c: "left" if c == "Year" else "right"
    th = "".join(f'<th style="{HEAD[_tier(c)]};padding:6px 12px;text-align:{_al(c)};white-space:nowrap;'
                 f'font-size:0.86rem">{c}</th>' for c in cols)
    trs = "".join("<tr>" + "".join(
        f'<td style="{BODY[_tier(c)]};padding:5px 12px;text-align:{_al(c)};white-space:nowrap;'
        f'font-size:0.9rem;border-bottom:1px solid #f2f2f2">{row[c]}</td>' for c in cols) + "</tr>"
        for _, row in disp.iterrows())
    st.markdown(f'<table style="width:100%;border-collapse:collapse;margin:2px 0 6px">'
                f'<thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>', unsafe_allow_html=True)


def _avf_pctcls(a, f):
    """Attainment (act/fcst) → (css-class, '104%'). green ≥105% · red ≤95% · muted between."""
    if not f or pd.isna(a) or pd.isna(f):
        return "m", "—"
    r = a / f
    return ("g" if r >= 1.05 else "r" if r <= 0.95 else "m"), f"{r*100:.0f}%"


def _trend_html(trend, wow):
    ar = {"UP": "▲", "DOWN": "▼", "FLAT": "▬"}.get(trend)
    if not ar:
        return '<span class="m">—</span>'
    cls = "g" if trend == "UP" else ("r" if trend == "DOWN" else "m")
    return f'<span class="{cls}">{ar}{"" if pd.isna(wow) else f" {wow:+.0f}%"}</span>'


_AVF_CSS = f"""<style>
.avf-scroll{{overflow-x:auto;border:1px solid {theme.HAIRLINE};border-radius:12px;margin:6px 0 4px}}
table.avf{{border-collapse:collapse;width:100%;font-size:12px;min-width:1120px;font-variant-numeric:tabular-nums;background:#fff}}
table.avf th,table.avf td{{padding:6px 9px;text-align:right;white-space:nowrap;border-bottom:1px solid {theme.HAIRLINE}}}
table.avf th:first-child,table.avf td:first-child{{text-align:left}}
table.avf .grp th{{font-size:10.5px;text-transform:uppercase;letter-spacing:.05em;font-weight:800;border-bottom:2px solid {theme.HAIRLINE};text-align:center;color:{theme.INK};padding-top:9px}}
table.avf .grp th.ih{{text-align:left;color:{theme.MUTED}}}
table.avf .grp .eolmh{{background:rgba(31,182,193,.10)}}
table.avf .grp .curh{{background:rgba(155,107,223,.12)}}
table.avf .grp .eotmh{{background:rgba(201,162,39,.14)}}
table.avf .grp .lyh{{background:rgba(107,107,107,.10);color:{theme.MUTED}}}
table.avf td.lyc{{background:rgba(107,107,107,.05);color:{theme.MUTED}}}
table.avf .sub th{{font-size:9.5px;text-transform:uppercase;letter-spacing:.03em;color:{theme.MUTED};font-weight:700}}
table.avf td.intro{{background:{theme.OFF_WHITE};color:{theme.MUTED}}}
table.avf td.intro.ev{{color:{theme.INK};font-weight:700}}
table.avf td.eolmc{{background:rgba(31,182,193,.05)}}
table.avf td.curc{{background:rgba(155,107,223,.05)}}
table.avf td.eotmc{{background:rgba(201,162,39,.06)}}
table.avf td.num{{font-weight:700;color:{theme.INK}}}
table.avf .g{{color:{theme.GREEN};font-weight:700}}table.avf .r{{color:{theme.RED};font-weight:700}}table.avf .m{{color:{theme.MUTED}}}
table.avf .wpass{{font-weight:700;color:{theme.AMBER};text-transform:uppercase;font-size:10px;letter-spacing:.05em}}
table.avf tr.tot td{{border-top:2px solid {theme.HAIRLINE};font-weight:800;background:rgba(255,244,0,.08)}}
table.avf .grp .ih,table.avf .sub th:first-child,table.avf tbody td:first-child{{border-left:2px solid {theme.MUTED}}}
</style>"""

_AVF_THEAD = ('<thead><tr class="grp"><th class="ih" colspan="4">Edition</th>'
              '<th class="eolmh" colspan="3">EOLM</th><th class="curh" colspan="3">Current</th>'
              '<th class="eotmh" colspan="3">EOTM</th><th class="lyh">Last&nbsp;yr</th><th>Trend</th></tr>'
              '<tr class="sub"><th>Event</th><th>Race&nbsp;day</th><th>Wks</th><th>Target</th>'
              '<th>Forecast</th><th>Actual</th><th>%</th><th>Forecast</th><th>Actual</th><th>GAP</th>'
              '<th>Forecast</th><th>Actual</th><th>%</th><th>This&nbsp;mo</th><th>Trend</th></tr></thead>')


def avf_reg_table(df, meta, prior_map=None):
    """Registrations Actuals-vs-Forecast grid in the original tracker format: WKS · EOLM (Forecast/
    Actual/%) · Current (Forecast/Actual/GAP, derived EOTM−EOLM) · EOTM (Forecast/Actual/%) · Last-yr
    this-month (from prior_map = {event → last-year this-month regs}) · Trend. Reg-only. Passed editions
    collapse to Race day + Target + EOTM Actual; PORTFOLIO is the total."""
    prior_map = prior_map or {}
    rows = []
    for r in df.itertuples():
        is_port = str(r.event).upper().startswith("PORTFOLIO")
        st_, dtr = meta.get(r.event, ("selling", float("nan")))
        passed = (not is_port) and st_ == "completed"
        race_s = "—" if is_port else ((data.AS_OF + pd.to_timedelta(dtr, unit="D")).strftime("%-d %b")
                                      if pd.notna(dtr) else "—")
        wks_s = "—" if is_port else ('<span class="wpass">passed</span>' if passed
                                     else (f"{dtr/7:.1f}" if pd.notna(dtr) else "—"))
        ef, ea, tf, ta = r.eolm_fcst, r.eolm_act, r.eotm_fcst, r.eotm_act
        trend_td = ('<td class="m">—</td>' if (passed or is_port)
                    else f'<td>{_trend_html(getattr(r, "trend", None), getattr(r, "wow_pct", float("nan")))}</td>')
        if passed:
            block = ('<td class="eolmc">—</td><td class="eolmc">—</td><td class="eolmc">—</td>'
                     '<td class="curc">—</td><td class="curc">—</td><td class="curc">—</td>'
                     f'<td class="eotmc">—</td><td class="eotmc num">{_f_int(ta)}</td><td class="eotmc">—</td>')
        else:
            mf, ma = (tf - ef), (ta - ea)
            gap = ma - mf
            gap_s = "—" if pd.isna(gap) else f"{gap:+,.0f}"
            ec, es = _avf_pctcls(ea, ef); tc, ts = _avf_pctcls(ta, tf)
            block = (f'<td class="eolmc">{_f_int(ef)}</td><td class="eolmc num">{_f_int(ea)}</td><td class="eolmc {ec}">{es}</td>'
                     f'<td class="curc">{_f_int(mf)}</td><td class="curc">{_f_int(ma)}</td><td class="curc m">{gap_s}</td>'
                     f'<td class="eotmc">{_f_int(tf)}</td><td class="eotmc num">{_f_int(ta)}</td><td class="eotmc {tc}">{ts}</td>')
        _ly = prior_map.get(r.event)
        lastyr_td = f'<td class="lyc">{_f_int(_ly) if (_isnum(_ly) and _ly > 0) else "—"}</td>'
        tr_cls = ' class="tot"' if is_port else ''
        rows.append(f'<tr{tr_cls}><td class="intro ev">{r.event}</td><td class="intro">{race_s}</td>'
                    f'<td class="intro">{wks_s}</td><td class="intro">{_f_int(getattr(r, "total_target"))}</td>'
                    f'{block}{lastyr_td}{trend_td}</tr>')
    st.markdown(_AVF_CSS + '<div class="avf-scroll"><table class="avf">' + _AVF_THEAD
                + "<tbody>" + "".join(rows) + "</tbody></table></div>", unsafe_allow_html=True)


def reg_pacing_table(yb):
    """Registrations-only per-event pacing table for one season (marketing Actuals-vs-plan). Columns:
    Event · Race day · Status · Wks · Target · To date · % of target · Projected landing. NO revenue.
    Appends a recomputed PORTFOLIO row. `yb` = market_data.year_book_reg(year)."""
    d = yb.copy()
    port = pd.Series({
        "event": "PORTFOLIO", "status": "—", "days_to_race": np.nan,
        "reg_target": pd.to_numeric(d.reg_target, errors="coerce").sum(min_count=1),
        "reg_act": pd.to_numeric(d.reg_act, errors="coerce").sum(min_count=1),
        "landing_reg": pd.to_numeric(d.landing_reg, errors="coerce").sum(min_count=1)})
    port["reg_pct"] = (port.reg_act / port.reg_target) if port.reg_target else np.nan
    rows = pd.concat([d, pd.DataFrame([port])], ignore_index=True)

    def _wks(v):
        return "—" if pd.isna(v) else ("raced" if v < 0 else f"{int(round(v/7))}w")
    disp = pd.DataFrame({
        "Event": rows.event,
        "Race day": rows.get("race_date", pd.Series([pd.NaT]*len(rows))).apply(
            lambda x: "—" if pd.isna(x) else pd.to_datetime(x).strftime("%d %b")),
        "Status": rows.status,
        "To race": rows.days_to_race.apply(_wks),
        "Reg target": rows.reg_target.map(_f_int),
        "Reg to date": rows.reg_act.map(_f_int),
        "% of target": rows.reg_pct.map(_f_pct0),
        "Projected landing": rows.landing_reg.map(_f_int)})

    def _row_css(r):
        port = str(r.iloc[0]).upper().startswith("PORTFOLIO")
        return ["font-weight:700;background-color:#FAFBFC" if port else "" for _ in r]
    st.dataframe(disp.style.apply(_row_css, axis=1), use_container_width=True, hide_index=True)


def _isnum(v):
    return isinstance(v, (int, float, np.integer, np.floating)) and not (isinstance(v, float) and pd.isna(v))


RAMP_COLORS = {"Last year": "#cfcfcf", "Plan": theme.GOLD, "Actual": theme.INK}   # faint / medium / bright
RAMP_STYLE = {"Last year": (1.6, "dot", 4), "Plan": (2.6, "solid", 5), "Actual": (4.2, "solid", 8)}


def ramp_event_chart(edf, as_of, key, ytitle="Cumulative registrations"):
    """Single-event ramp: last year (faint grey, dotted) · plan (gold, medium) · actual (ink, bright/thick)."""
    t = edf.copy()
    t["calendar_month"] = pd.to_datetime(t.calendar_month)
    cur = pd.Timestamp(as_of).to_period("M").to_timestamp()
    t["act_cum"] = t.act_cum.where(t.calendar_month <= cur)
    has_prior = pd.to_numeric(t.prior_cum, errors="coerce").fillna(0).abs().sum() > 0
    vals = (["prior_cum"] if has_prior else []) + ["plan_cum", "act_cum"]
    long = t.melt(id_vars=["calendar_month"], value_vars=vals, var_name="series", value_name="v")
    long["series"] = long.series.map({"prior_cum": "Last year", "plan_cum": "Plan", "act_cum": "Actual"})
    fig = px.line(long, x="calendar_month", y="v", color="series", markers=True,
                  category_orders={"series": ["Last year", "Plan", "Actual"]}, color_discrete_map=RAMP_COLORS)
    for tr in fig.data:
        w, d, ms = RAMP_STYLE.get(tr.name, (2, "solid", 5))
        tr.line.width = w; tr.line.dash = d; tr.marker.size = ms
    fig.update_traces(connectgaps=False)
    fig.update_layout(height=250, legend_title=None, xaxis_title=None, yaxis_title=ytitle,
                      margin=dict(l=6, r=6, t=28, b=6),
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0))
    st.plotly_chart(fig, use_container_width=True, key=key)


def ramp_status(edf, as_of):
    """Status + action + EOLM absolutes for one event, evaluated at EOLM (end of last closed month). Returns
    a dict: label, color, action, vs_plan, vs_last, ly, plan, act. Registrations-only for the marketing app."""
    t = edf.copy()
    t["calendar_month"] = pd.to_datetime(t.calendar_month)
    eolm = (pd.Timestamp(as_of).to_period("M") - 1).to_timestamp()
    at = t[t.calendar_month <= eolm].sort_values("calendar_month")
    if not len(at):
        if len(t):     # trajectory starts after EOLM → cycle opened THIS month
            return dict(label="Launch phase", color=theme.ACCENT2, vs_plan=np.nan, vs_last=np.nan,
                        ly=np.nan, plan=np.nan, act=np.nan,
                        action="Cycle opened this month — no end-of-last-month registrations yet; drive launch "
                               "awareness + early-bird and track the ramp.")
        return dict(label="Not selling", color=theme.MUTED, action="No live selling cycle for this event.",
                    vs_plan=np.nan, vs_last=np.nan, ly=np.nan, plan=np.nan, act=np.nan)
    r = at.iloc[-1]
    a, p, pr, mtr = r.act_cum, r.plan_cum, r.prior_cum, r.mtr
    vs_plan = (a / p) if (_isnum(p) and p > 0) else np.nan
    vs_last = (a / pr) if (_isnum(pr) and pr > 0) else np.nan
    ly = ("" if pd.isna(vs_last) else
          (f" · ahead of last year (+{vs_last-1:.0%})" if vs_last >= 1 else f" · behind last year ({vs_last-1:.0%})"))
    base = dict(vs_plan=vs_plan, vs_last=vs_last, ly=pr, plan=p, act=a)
    if _isnum(mtr) and mtr >= 9 and (pd.isna(vs_plan) or vs_plan < 0.10):
        return dict(label="Launch phase", color=theme.ACCENT2, **base,
                    action="Presale just opened — drive launch awareness + early-bird; too early for a plan or "
                           "prior-year read, so track the ramp, not the level.")
    if pd.isna(vs_plan):
        return dict(label="Early", color=theme.MUTED, **base,
                    action="Too early to read against plan — keep the launch cadence.")
    if vs_plan >= 1.05:
        return dict(label="Ahead", color=theme.GREEN, **base,
                    action=f"Ahead of plan (+{vs_plan-1:.0%}){ly}. Sustain demand; ease discounting and protect "
                           f"yield.")
    if vs_plan >= 0.95:
        return dict(label="On track", color=theme.AMBER, **base,
                    action=f"On plan ({vs_plan-1:+.0%}){ly}. Hold the cadence; line up the next price-tier step "
                           f"and a mid-cycle nudge.")
    return dict(label="Behind", color=theme.RED, **base,
                action=f"Behind plan ({vs_plan-1:.0%}){ly}. Accelerate now: paid push + email re-engagement of "
                       f"last year's field; consider an early-bird extension before the next tier.")


def ramp_panel(s):
    """EOLM absolutes panel (Actual bright · Plan medium · Last year faint) + vs% + action. Registrations."""
    st.markdown(
        f'<div style="font-size:.7rem;text-transform:uppercase;letter-spacing:.04em;color:{theme.MUTED};'
        f'font-weight:700;margin-bottom:3px">EOLM · registrations</div>'
        f'<div style="font-variant-numeric:tabular-nums;line-height:1.5">'
        f'<div><span style="display:inline-block;width:74px;color:{theme.INK};font-weight:700">Actual</span>'
        f'<b style="font-size:1.1rem;color:{theme.INK}">{_f_int(s["act"])}</b></div>'
        f'<div><span style="display:inline-block;width:74px;color:{theme.GOLD};font-weight:700">Plan</span>'
        f'<span style="font-weight:700;color:{theme.INK}">{_f_int(s["plan"])}</span></div>'
        f'<div><span style="display:inline-block;width:74px;color:#b9b9b9;font-weight:600">Last year</span>'
        f'<span style="color:{theme.MUTED}">{_f_int(s["ly"])}</span></div></div>'
        f'<div style="margin-top:4px;font-size:.8rem;color:{theme.MUTED}">vs plan '
        f'<b>{"—" if pd.isna(s["vs_plan"]) else f"{s["vs_plan"]-1:+.0%}"}</b> · vs last year '
        f'<b>{"—" if pd.isna(s["vs_last"]) else f"{s["vs_last"]-1:+.0%}"}</b></div>', unsafe_allow_html=True)
    insight(f"<b>Action —</b> {s['action']}",
            "good" if s["label"] == "Ahead" else ("warn" if s["label"] in ("Behind", "On track") else ""))


def render_ramp_tab(traj, as_of):
    """Per-event registration ramp tab body for the marketing app: badge + chart + EOLM panel + action."""
    if not len(traj):
        st.info("No ramp data available yet."); return
    ev_order = data._order_events(pd.DataFrame({"event": traj.event.unique()})).event.tolist()
    for i, ev in enumerate(ev_order):
        edf = traj[traj.event == ev].sort_values("mtr", ascending=False)
        if not len(edf):
            continue
        s = ramp_status(edf, as_of)
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:10px;margin:16px 0 2px">'
            f'<span style="font-weight:800;font-size:1.05rem;color:{theme.INK}">{ev}</span>'
            f'<span style="background:{s["color"]};color:#fff;font-weight:700;font-size:.72rem;'
            f'padding:2px 10px;border-radius:12px;text-transform:uppercase;letter-spacing:.04em">{s["label"]}</span>'
            f'</div>', unsafe_allow_html=True)
        c1, c2 = st.columns([3, 2])
        with c1:
            ramp_event_chart(edf, as_of, key=f"mkt_ramp_{i}")
        with c2:
            ramp_panel(s)
