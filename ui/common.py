import base64
from pathlib import Path

import streamlit as st

from config.settings import COLORS


def _get_base64(path: Path) -> str:
    if not path.exists():
        return ""
    with path.open("rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def inject_custom_styles():
    svg_style_path = Path("assets/FX_style_top_right.svg")
    bg_color_hex = COLORS.get("Blau", "#006DB9")
    bg_opacity = 0.25

    h = bg_color_hex.lstrip("#")
    r, g, b = tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    rgba_bg = f"rgba({r}, {g}, {b}, {bg_opacity})"

    style_base64 = _get_base64(svg_style_path)
    bg_style = ""
    if style_base64:
        bg_style = f"""
        [data-testid="stAppViewContainer"]::before {{
            content: "";
            position: fixed;
            top: -5px;
            right: -5px;
            width: 400px;
            height: 400px;
            background-image: url('data:image/svg+xml;base64,{style_base64}');
            background-size: contain;
            background-repeat: no-repeat;
            background-position: top right;
            opacity: 0.4;
            transform: rotate(180deg);
            pointer-events: none;
            z-index: 0;
        }}
        """

    st.markdown(f"""
    <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,0,0" />
    <style>
        [data-testid="stAppViewContainer"] {{
            background: radial-gradient(
                circle at top left,
                {rgba_bg} 0%,
                rgba(255, 255, 255, 0) 70%
            ) !important;
            background-attachment: fixed !important;
        }}
        {bg_style}
        [data-testid="stSidebarHeader"] {{
            height: 120px !important;
            padding-top: 1rem !important;
            padding-bottom: 1rem !important;
        }}
        [data-testid="stSidebarHeader"] img {{
            height: 100px !important;
            width: auto !important;
        }}
        [data-testid="stMainBlockContainer"] {{
            padding-top: 2rem !important;
        }}
        header[data-testid="stHeader"], [data-testid="stToolbar"] {{
            background-color: transparent !important;
        }}
        .material-symbols-rounded {{
            font-family: 'Material Symbols Rounded';
            vertical-align: middle;
            margin-right: 8px;
            font-variation-settings: 'opsz' 24;
        }}
    </style>
    """, unsafe_allow_html=True)


def render_tab_header(icon_name: str, title: str, description: str):
    st.markdown(
        f"""
        <div style='display:flex; align-items:center; gap:16px; margin-top:0.5rem;'>
            <span class='material-symbols-rounded' style='font-size:32px;'>{icon_name}</span>
            <h2 style='margin:0;'>{title}</h2>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(description)
    st.divider()


def handle_llm_error(e):
    error_msg = str(e)
    if "429" in error_msg or "quota" in error_msg.lower():
        st.error("Quota exceeded or rate limit reached. Please try another model or wait a moment.")
    else:
        st.error(f"Error: {e}")


def render_main_title():
    st.markdown(
        """
        <div style='display:flex; align-items:center; gap:24px; margin-bottom:1rem;'>
            <span class='material-symbols-rounded' style='font-size:48px;'>analytics</span>
            <span style='font-size:48px; font-weight:700; letter-spacing:0.8px;'>
                Factory-X Audit-App
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )
