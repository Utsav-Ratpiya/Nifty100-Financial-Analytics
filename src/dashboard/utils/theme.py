"""
src/dashboard/utils/theme.py — Nifty 100 Analytics
Sprint 4+ visual-enhancement layer.

Shared CSS injection + small HTML helpers used by every page so the whole
app shares one consistent look: animated gradient titles, glowing/lifting
KPI cards, a colour-coded metric helper, and a couple of layout helpers.
Pure presentation — no data logic lives here.
"""
from __future__ import annotations

import streamlit as st

# Core palette (kept close to the navy / blue / gold scheme already used in
# the PDF reports, so the dashboard and the reports feel like one product).
NAVY = "#0B1E3D"
BLUE = "#3B82F6"
CYAN = "#22D3EE"
GOLD = "#F5B942"
PURPLE = "#A855F7"
PINK = "#F472B6"
GREEN = "#22C55E"
RED = "#EF4444"


def inject_global_css() -> None:
    """Injects one shared <style> block. Call once near the top of every
    page, right after st.set_page_config(). Safe to call multiple times
    (Streamlit just re-renders the same block)."""
    st.markdown(
        f"""
        <style>
        @keyframes gradientFlow {{
            0%   {{ background-position: 0% 50%; }}
            50%  {{ background-position: 100% 50%; }}
            100% {{ background-position: 0% 50%; }}
        }}
        @keyframes fadeInUp {{
            from {{ opacity: 0; transform: translateY(10px); }}
            to   {{ opacity: 1; transform: translateY(0); }}
        }}
        @keyframes pulseGlow {{
            0%, 100% {{ box-shadow: 0 0 0 rgba(59,130,246,0.0); }}
            50%      {{ box-shadow: 0 0 18px rgba(59,130,246,0.35); }}
        }}

        /* ---- animated gradient page titles ---- */
        .gradient-title {{
            font-size: 2.4rem;
            font-weight: 800;
            line-height: 1.2;
            margin-bottom: 0.1rem;
            background: linear-gradient(90deg, {BLUE}, {CYAN}, {PURPLE}, {PINK}, {GOLD}, {BLUE});
            background-size: 400% 400%;
            -webkit-background-clip: text;
            background-clip: text;
            -webkit-text-fill-color: transparent;
            color: transparent;
            animation: gradientFlow 8s ease infinite;
            display: inline-block;
        }}
        .gradient-subtitle {{
            color: #8B95A7;
            font-size: 0.98rem;
            margin-top: -0.3rem;
            margin-bottom: 0.6rem;
        }}

        /* ---- section headers with a small animated accent bar ---- */
        .section-header {{
            display: flex;
            align-items: center;
            gap: 10px;
            margin: 0.4rem 0 0.6rem 0;
            font-size: 1.28rem;
            font-weight: 700;
        }}
        .section-header .bar {{
            width: 6px;
            height: 22px;
            border-radius: 4px;
            background: linear-gradient(180deg, {BLUE}, {CYAN});
            animation: pulseGlow 2.4s ease-in-out infinite;
        }}

        /* ---- st.metric KPI tiles -> gradient cards that lift on hover ---- */
        div[data-testid="stMetric"] {{
            background: linear-gradient(135deg, rgba(59,130,246,0.10), rgba(34,211,238,0.05));
            border: 1px solid rgba(59,130,246,0.25);
            border-radius: 14px;
            padding: 12px 16px 8px 16px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.08);
            transition: transform 0.25s ease, box-shadow 0.25s ease;
            animation: fadeInUp 0.5s ease;
        }}
        div[data-testid="stMetric"]:hover {{
            transform: translateY(-4px) scale(1.015);
            box-shadow: 0 10px 22px rgba(59,130,246,0.28);
            border-color: rgba(34,211,238,0.55);
        }}
        div[data-testid="stMetricLabel"] {{
            font-weight: 600;
            opacity: 0.85;
        }}

        /* ---- nav cards on the landing page ---- */
        div[data-testid="stContainer"] {{
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }}

        /* ---- buttons: subtle gradient + lift ---- */
        div.stButton > button {{
            border-radius: 10px;
            border: 1px solid rgba(59,130,246,0.35);
            transition: transform 0.15s ease, box-shadow 0.15s ease;
        }}
        div.stButton > button:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 14px rgba(59,130,246,0.30);
            border-color: {CYAN};
        }}

        /* ---- sliders: gold/blue accent instead of default red ---- */
        div[data-testid="stSlider"] div[role="slider"] {{
            background-color: {BLUE} !important;
        }}

        /* ---- dataframes: rounded corners + fade in ---- */
        div[data-testid="stDataFrame"] {{
            border-radius: 12px;
            overflow: hidden;
            animation: fadeInUp 0.6s ease;
        }}

        /* ================================================================
           SIDEBAR NAVIGATION UPGRADE (CSS-only — no page files touched)
           Streamlit auto-builds the sidebar nav from pages/01_home.py ...
           08_reports.py, so it renders on every page for free the moment
           this stylesheet is injected via inject_global_css().
           ================================================================ */

        /* Brand header above the auto-generated nav list */
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"] {{
            padding-top: 6px;
        }}
        section[data-testid="stSidebar"] [data-testid="stSidebarNav"]::before {{
            content: "\U0001F4C8  NIFTY 100 ANALYTICS";
            display: block;
            font-size: 0.92rem;
            font-weight: 800;
            letter-spacing: 0.03em;
            padding: 2px 14px 12px 14px;
            margin-bottom: 6px;
            border-bottom: 1px solid rgba(59,130,246,0.25);
            background: linear-gradient(90deg, {BLUE}, {CYAN}, {PURPLE});
            background-size: 200% 200%;
            -webkit-background-clip: text;
            background-clip: text;
            -webkit-text-fill-color: transparent;
            color: transparent;
            animation: gradientFlow 8s ease infinite;
        }}

        /* Base nav link styling: spacing, rounded pill, smooth transitions */
        [data-testid="stSidebarNav"] a,
        [data-testid="stSidebarNavLink"] {{
            border-radius: 10px !important;
            margin: 2px 8px !important;
            padding: 8px 12px !important;
            font-weight: 600 !important;
            transition: background 0.2s ease, transform 0.15s ease, box-shadow 0.2s ease;
        }}
        [data-testid="stSidebarNav"] a:hover,
        [data-testid="stSidebarNavLink"]:hover {{
            background: rgba(59,130,246,0.12) !important;
            transform: translateX(2px);
        }}

        /* Active / current page — gradient pill + glowing left accent bar */
        [data-testid="stSidebarNav"] a[aria-current="page"],
        [data-testid="stSidebarNavLink"][aria-current="page"] {{
            background: linear-gradient(90deg, rgba(59,130,246,0.22), rgba(34,211,238,0.10)) !important;
            box-shadow: inset 3px 0 0 0 {CYAN}, 0 2px 8px rgba(59,130,246,0.25);
            font-weight: 800 !important;
        }}

        /* Emoji icons in front of each nav label, matched to fixed
           pages/01_.. .. 08_.. filename order (nth-child is safe here
           since the page order never changes). */
        [data-testid="stSidebarNav"] li:nth-child(1)  a::before {{ content: "\U0001F3E0  "; }}
        [data-testid="stSidebarNav"] li:nth-child(2)  a::before {{ content: "\U0001F3E2  "; }}
        [data-testid="stSidebarNav"] li:nth-child(3)  a::before {{ content: "\U0001F50D  "; }}
        [data-testid="stSidebarNav"] li:nth-child(4)  a::before {{ content: "\U0001F91D  "; }}
        [data-testid="stSidebarNav"] li:nth-child(5)  a::before {{ content: "\U0001F4C8  "; }}
        [data-testid="stSidebarNav"] li:nth-child(6)  a::before {{ content: "\U0001F3ED  "; }}
        [data-testid="stSidebarNav"] li:nth-child(7)  a::before {{ content: "\U0001F4B0  "; }}
        [data-testid="stSidebarNav"] li:nth-child(8)  a::before {{ content: "\U0001F4C4  "; }}

        /* Extra breathing room + subtle divider under the whole nav block */
        [data-testid="stSidebarNavItems"] {{
            padding-bottom: 10px;
            border-bottom: 1px solid rgba(59,130,246,0.15);
            margin-bottom: 8px;
        }}

        /* ---- badge chips used for quick status labels ---- */
        .badge {{
            display: inline-block;
            padding: 3px 10px;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0.02em;
        }}
        .badge-green  {{ background: rgba(34,197,94,0.15);  color: {GREEN}; border: 1px solid rgba(34,197,94,0.4); }}
        .badge-red    {{ background: rgba(239,68,68,0.15);  color: {RED};   border: 1px solid rgba(239,68,68,0.4); }}
        .badge-gold   {{ background: rgba(245,185,66,0.18); color: {GOLD};  border: 1px solid rgba(245,185,66,0.45); }}
        .badge-blue   {{ background: rgba(59,130,246,0.15); color: {BLUE}; border: 1px solid rgba(59,130,246,0.4); }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def animated_title(text: str, icon: str = "", subtitle: str | None = None) -> None:
    """Renders the page's <h1> as an animated colour-cycling gradient
    title (replacement for st.title). Optionally renders a caption-style
    subtitle right underneath."""
    prefix = f"{icon} " if icon else ""
    st.markdown(f'<div class="gradient-title">{prefix}{text}</div>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<div class="gradient-subtitle">{subtitle}</div>', unsafe_allow_html=True)


def section_header(text: str) -> None:
    """A styled subheader with a small pulsing accent bar — use in place
    of st.subheader for the major sections within a page."""
    st.markdown(
        f'<div class="section-header"><span class="bar"></span>{text}</div>',
        unsafe_allow_html=True,
    )


def badge(text: str, kind: str = "blue") -> str:
    """Returns an HTML badge chip string (embed inside another st.markdown
    call with unsafe_allow_html=True, or use directly via st.markdown)."""
    return f'<span class="badge badge-{kind}">{text}</span>'
