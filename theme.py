"""Supertri brand theme — one place to restyle.

Palette + type from the Supertri Brand Guidelines (HQ26_018, p.19 colour, p.33–35 type):
core = Supertri Yellow #fff400 + Off Black #1c1c1c, 80/20 weighted, with off-white/white
neutrals. Yellow is a FILL/HIGHLIGHT colour (invisible as text/thin lines on white); ink
carries text and primary chart series. Brand fonts (Zuume Edge / Gazzetta / Zona Pro) are
Adobe-licensed and can't ship to Streamlit Cloud, so we substitute free Google fonts:
Montserrat (geometric display → evokes Zuume) for headings, Inter (→ Zona Pro) for body.
"""
import plotly.graph_objects as go
import plotly.io as pio

# ── Brand palette (guidelines p.19) ──────────────────────────────────────────
YELLOW   = "#fff400"   # Supertri Yellow (Pantone 108C) — primary FILL/highlight
INK      = "#1c1c1c"   # Off Black (419C) — primary text / axes / primary series
BLACK    = "#000000"   # pure black
OFF_WHITE= "#f4f4f4"   # off white — sidebar / secondary surfaces
GOLD     = "#c9a227"   # legible yellow-family tone for chart series on white (yellow itself vanishes)
MUTED    = "#6b6b6b"   # secondary text (neutral grey)
HAIRLINE = "#e6e6e6"   # gridlines / dividers
ACCENT   = INK         # emphasis in text/line contexts → ink (NOT yellow, which is fill-only)
ACCENT2  = "#1fb6c1"   # teal — secondary series
GREEN    = "#17B890"   # RAG green / positive
AMBER    = "#E8A33D"   # RAG amber
RED      = "#E4572E"   # RAG red / negative

# Series colours legible on a white background; yellow reserved for highlight fills only.
CATEGORICAL = [INK, GOLD, MUTED, ACCENT2, GREEN, "#9B6BDF", AMBER]
SEQUENTIAL  = ["#fff7b0", "#ffeb52", YELLOW, "#d9c400", GOLD, "#8a7000"]
RAG = {"green": GREEN, "amber": AMBER, "red": RED}

# ── Brand S-mark (solid), from the guidelines' S-outline path ────────────────
_SMARK_PATH = ("M425.76.75c-121.73.22-220.45,98.43-220.45,210.75l986.07.07V.75H425.76ZM879.73,"
    "401.18H205.3v-189.69C93.28,211.5,2.47,306.79,2.47,418.81c0,57.06,23.15,107.99,60.64,144.58,"
    "37.49,36.59,89.24,58.92,146.37,58.92h673.98c60.94,0,110.3,49.36,110.3,110.3l.67,79.23h234.19"
    "v-61.76c0-191.85-156.98-348.9-348.9-348.9ZM1.72,811.69l-.97,221.57h993.69v-221.43l-992.72-.15Z")

def smark(fill=YELLOW, h=28):
    """Inline solid Supertri S-mark SVG at the given pixel height."""
    w = round(h * 1229.38 / 1034.02)
    return (f'<svg width="{w}" height="{h}" viewBox="0 0 1229.38 1034.02" '
            f'xmlns="http://www.w3.org/2000/svg" style="display:block"><path fill="{fill}" '
            f'd="{_SMARK_PATH}"/></svg>')


def install():
    """Register a clean plotly template and make it the default."""
    t = go.layout.Template()
    t.layout = go.Layout(
        font=dict(family="Inter, -apple-system, Segoe UI, sans-serif", size=13, color=INK),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        colorway=CATEGORICAL,
        margin=dict(l=8, r=8, t=48, b=8),
        title=dict(font=dict(family="Montserrat, Inter, sans-serif", size=15, color=INK),
                   x=0, xanchor="left", y=0.97, yanchor="top"),
        legend=dict(orientation="h", yanchor="top", y=-0.18, x=0, font=dict(size=12),
                    title=None, bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(showgrid=False, zeroline=False, linecolor=HAIRLINE, ticks="outside",
                   tickcolor=HAIRLINE, title=dict(font=dict(size=12, color=MUTED))),
        yaxis=dict(showgrid=True, gridcolor=HAIRLINE, zeroline=False, linecolor="rgba(0,0,0,0)",
                   title=dict(font=dict(size=12, color=MUTED))),
        hoverlabel=dict(bgcolor="white", bordercolor=HAIRLINE,
                        font=dict(size=12, color=INK)),
    )
    pio.templates["supertri"] = t
    pio.templates.default = "supertri"


CSS = f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@600;700;800&family=Inter:wght@400;500;600;700&display=swap');

  .stApp {{ background:#FFFFFF; }}
  html, body, .stApp, [class*="css"] {{ font-family:'Inter',-apple-system,Segoe UI,sans-serif; }}
  section[data-testid="stSidebar"] {{ background:{OFF_WHITE}; border-right:1px solid {HAIRLINE}; }}
  h1,h2,h3,h4 {{ font-family:'Montserrat','Inter',sans-serif; color:{INK}; letter-spacing:-0.01em; }}
  h1 {{ font-weight:800; }} h2,h3 {{ font-weight:700; }}
  a, a:visited {{ color:{INK}; text-decoration:underline; }}   /* never yellow-on-white */

  /* brand header band — off-black with the yellow S-mark */
  .brandbar {{ display:flex; align-items:center; gap:16px; background:{INK};
     border-radius:14px; padding:16px 22px; margin:2px 0 20px;
     border-left:6px solid {YELLOW}; }}
  .brandbar .wm {{ height:26px; width:auto; display:block; }}
  .brandbar .title {{ font-family:'Montserrat',sans-serif; font-weight:600; font-size:19px;
     color:#FFFFFF; letter-spacing:-0.01em; line-height:1;
     padding-left:16px; border-left:1px solid rgba(255,255,255,0.25); }}
  .brandbar .title b {{ color:{YELLOW}; font-weight:800; }}
  .brandbar .tag {{ margin-left:auto; font-size:12px; font-weight:600; color:{OFF_WHITE};
     text-transform:uppercase; letter-spacing:0.06em; opacity:.85; }}
  /* sidebar brand lockup */
  .sb-brand {{ display:flex; align-items:center; gap:10px; margin:2px 0 2px; }}
  .sb-brand .ico {{ width:28px; height:28px; display:block; }}
  .sb-brand .nm {{ font-family:'Montserrat',sans-serif; font-weight:700; font-size:15px; color:{INK}; line-height:1.1; }}

  /* metric cards — yellow top accent */
  div[data-testid="stMetric"] {{
     background:#FFFFFF; border:1px solid {HAIRLINE}; border-top:3px solid {YELLOW};
     border-radius:14px; padding:16px 18px; box-shadow:0 1px 2px rgba(28,28,28,0.05);
  }}
  div[data-testid="stMetricLabel"] p {{ color:{MUTED}; font-size:12px; font-weight:600;
     text-transform:uppercase; letter-spacing:0.04em; }}
  div[data-testid="stMetricValue"] {{ color:{INK}; font-weight:700; }}
  .caveat {{ background:#FFFDF0; border:1px solid #F5E9A8; color:#7A6A15;
     border-radius:10px; padding:8px 12px; font-size:12.5px; margin:4px 0 14px; }}
  .lens {{ display:inline-block; font-size:11px; font-weight:700; text-transform:uppercase;
     letter-spacing:0.05em; padding:2px 8px; border-radius:6px; margin-right:6px; }}
  .lens-plan {{ background:{OFF_WHITE}; color:{INK}; }}
  .lens-yoy  {{ background:{YELLOW}; color:{INK}; }}
  .fwd {{ background:{OFF_WHITE}; border:1px solid {HAIRLINE}; color:{INK};
     border-radius:10px; padding:8px 12px; font-size:12.5px; margin:4px 0 14px; }}
  .stamp {{ color:{MUTED}; font-size:11.5px; font-style:italic; }}

  /* executive summary */
  .verdict {{ border-radius:16px; padding:20px 22px; margin:6px 0 22px;
     font-size:19px; line-height:1.45; color:{INK}; background:#FFFDF0;
     border:1px solid #F5E9A8; border-left:5px solid {YELLOW}; }}
  .verdict.win {{ background:#F1FBF7; border-color:#C8ECDD; border-left-color:{GREEN}; }}
  .verdict.lose {{ background:#FDF2EF; border-color:#F7D3C8; border-left-color:{RED}; }}
  .verdict b {{ font-weight:700; }}
  .kpi {{ background:#FFF; border:1px solid {HAIRLINE}; border-top:3px solid {YELLOW};
     border-radius:14px; padding:11px 16px 12px; box-shadow:0 1px 2px rgba(28,28,28,0.05);
     height:100%; min-height:88px; box-sizing:border-box; }}
  /* year-book season heading — year as headline, selling-count as a quiet subtitle */
  .seasonttl {{ font-family:'Montserrat','Inter',sans-serif; font-weight:700; font-size:26px;
     letter-spacing:-0.01em; color:{INK}; margin:8px 0 12px; line-height:1.1; }}
  .seasonttl .ssub {{ font-family:'Inter',sans-serif; font-weight:500; font-size:14px;
     color:{MUTED}; letter-spacing:0; }}
  /* soft attainment / growth pills — one colour language shared across Exec / AvF / YoY tables */
  .spill {{ display:inline-block; font-size:11px; font-weight:700; padding:2px 8px; border-radius:999px; }}
  .spill.sg {{ background:rgba(23,184,144,.16); color:#1f7a5c; }}
  .spill.sa {{ background:rgba(232,163,61,.20); color:#8a5e12; }}
  .spill.sr {{ background:rgba(228,87,46,.15); color:#a5452c; }}
  .spill.sm {{ background:rgba(107,107,107,.12); color:{MUTED}; }}
  .kpi .lab {{ color:{MUTED}; font-size:10.5px; font-weight:700; text-transform:uppercase;
     letter-spacing:0.03em; margin-bottom:6px; }}
  .kpi .val {{ color:{INK}; font-size:clamp(16px,1.7vw,27px); font-weight:700; line-height:1.05;
     font-family:'Montserrat',sans-serif; white-space:nowrap; }}
  .kpi .dlt {{ font-size:13px; font-weight:700; margin-top:4px; }}
  .kpi .sub {{ color:{MUTED}; font-size:11.5px; margin-top:6px; line-height:1.3; }}
  .panel {{ border:1px solid {HAIRLINE}; border-radius:14px; padding:6px 16px 14px; height:100%; }}
  .panel h4 {{ font-size:13px; text-transform:uppercase; letter-spacing:0.04em; margin:14px 0 8px; }}
  .panel.risk h4 {{ color:{RED}; }}
  .panel.opp h4 {{ color:{GREEN}; }}
  .row {{ display:flex; justify-content:space-between; align-items:baseline; gap:10px;
     padding:8px 0; border-bottom:1px solid {HAIRLINE}; font-size:13.5px; }}
  .row:last-child {{ border-bottom:none; }}
  .row .nm {{ font-weight:600; color:{INK}; }}
  .row .why {{ color:{MUTED}; font-size:11.5px; }}
  .row .mag {{ font-weight:700; white-space:nowrap; }}
  .action {{ padding:10px 0 10px 26px; position:relative; font-size:14px; line-height:1.4;
     border-bottom:1px solid {HAIRLINE}; color:{INK}; }}
  .action:last-child {{ border-bottom:none; }}
  .action:before {{ content:"→"; position:absolute; left:2px; color:{INK}; font-weight:700; }}
  /* per-view "so what" message banner */
  .msg {{ background:{OFF_WHITE}; border-left:4px solid {YELLOW}; border-radius:8px;
     padding:12px 16px; margin:2px 0 16px; font-size:16px; line-height:1.45; color:{INK}; }}
  .msg b {{ font-weight:700; }}
  .msg.good {{ border-left-color:{GREEN}; background:#F1FBF7; }}
  .msg.warn {{ border-left-color:{AMBER}; background:#FFF9F1; }}
  .msg.bad  {{ border-left-color:{RED};   background:#FDF2EF; }}
</style>
"""
