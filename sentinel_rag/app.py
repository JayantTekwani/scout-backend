"""
SCOUT — Stealth Intelligence UI
Obsidian · Emerald · Violet · Glassmorphism · HUD Cockpit
"""

import os
import sys
import time
import tempfile
from datetime import datetime, timedelta

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import CONFIG
from core.pipeline import SentinelPipeline
from core.ingestion import VectorStoreManager, load_and_chunk_file

st.set_page_config(
    page_title="SCOUT · Intelligence System",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ═══════════════════════════════════════════════════════════════════════════════
#  STEALTH INTELLIGENCE CSS
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600&display=swap');

/* ─── TOKENS ─────────────────────────────────────────────────────────────── */
:root {
  --obs:          #080c14;
  --obs2:         #0d1220;
  --obs3:         #111827;
  --obs4:         #1a2235;

  --em:           #10b981;
  --em-dim:       rgba(16,185,129,0.18);
  --em-glow:      rgba(16,185,129,0.35);
  --em-border:    rgba(16,185,129,0.28);

  --vi:           #8b5cf6;
  --vi-dim:       rgba(139,92,246,0.18);
  --vi-glow:      rgba(139,92,246,0.35);
  --vi-border:    rgba(139,92,246,0.28);

  --red:          #ef4444;
  --red-dim:      rgba(239,68,68,0.14);
  --red-border:   rgba(239,68,68,0.3);

  --amber:        #f59e0b;
  --amber-dim:    rgba(245,158,11,0.14);

  --glass:        rgba(255,255,255,0.032);
  --glass2:       rgba(255,255,255,0.055);
  --glass3:       rgba(255,255,255,0.08);
  --border:       rgba(255,255,255,0.07);
  --border2:      rgba(255,255,255,0.12);

  --text:         #f1f5f9;
  --text2:        #94a3b8;
  --text3:        #4b5e78;

  --mono:         'JetBrains Mono', monospace;
  --sans:         'Inter', sans-serif;
}

/* ─── BASE ───────────────────────────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

html, body, [class*="css"] {
  font-family: var(--sans) !important;
  background: var(--obs) !important;
  color: var(--text) !important;
  -webkit-font-smoothing: antialiased;
}
.stApp { background: var(--obs) !important; }
.main .block-container {
  padding: 1.5rem 2rem 4rem !important;
  max-width: 100% !important;
}

/* ─── RADAR ANIMATION ────────────────────────────────────────────────────── */
@keyframes radar-sweep {
  from { transform: rotate(0deg); }
  to   { transform: rotate(360deg); }
}
@keyframes radar-ping {
  0%   { transform: scale(0.6); opacity: 0.8; }
  100% { transform: scale(1.0); opacity: 0; }
}
@keyframes hud-blink {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.4; }
}
@keyframes em-pulse {
  0%, 100% { box-shadow: 0 0 12px var(--em-glow); }
  50%       { box-shadow: 0 0 28px var(--em-glow), 0 0 48px rgba(16,185,129,0.15); }
}
@keyframes scanline {
  0%   { top: -4px; }
  100% { top: 100%; }
}
@keyframes float-up {
  from { opacity: 0; transform: translateY(10px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* ─── SIDEBAR ────────────────────────────────────────────────────────────── */
section[data-testid="stSidebar"] {
  background: var(--obs2) !important;
  border-right: 1px solid var(--em-border) !important;
}
section[data-testid="stSidebar"] > div { padding-top: 0 !important; }

/* Sidebar brand */
.sb-brand {
  padding: 22px 18px 18px;
  background: linear-gradient(160deg, var(--em-dim) 0%, var(--vi-dim) 100%);
  border-bottom: 1px solid var(--em-border);
  position: relative; overflow: hidden;
}
.sb-brand::before {
  content: '';
  position: absolute; top: 0; left: 0; right: 0; height: 1px;
  background: linear-gradient(90deg, transparent, var(--em), var(--vi), transparent);
}
.sb-scout-badge {
  display: inline-flex; align-items: center; gap: 8px;
  background: var(--em-dim); border: 1px solid var(--em-border);
  border-radius: 6px; padding: 5px 11px; margin-bottom: 12px;
}
.sb-scout-dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--em);
  animation: hud-blink 2s ease-in-out infinite;
  box-shadow: 0 0 6px var(--em-glow);
}
.sb-scout-text {
  font-family: var(--mono); font-size: 0.66rem;
  font-weight: 600; color: var(--em); letter-spacing: 2px;
  text-transform: uppercase;
}
.sb-name {
  font-size: 1.1rem; font-weight: 800; color: var(--text);
  letter-spacing: -0.3px;
}
.sb-sub {
  font-size: 0.68rem; color: var(--text3);
  font-family: var(--mono); margin-top: 3px;
}

/* Sidebar section labels */
.sb-sec {
  font-size: 0.6rem; font-weight: 700; letter-spacing: 2.5px;
  text-transform: uppercase; color: var(--text3);
  padding: 16px 0 7px; border-bottom: 1px solid var(--border);
  margin-bottom: 8px;
}

/* Status pills */
.spill {
  display: inline-flex; align-items: center; gap: 6px;
  border-radius: 6px; padding: 5px 11px; margin-top: 6px;
  font-size: 0.71rem; font-family: var(--mono);
  width: 100%; box-sizing: border-box;
}
.spill-em {
  background: var(--em-dim); border: 1px solid var(--em-border); color: #6ee7b7;
}
.spill-vi {
  background: var(--vi-dim); border: 1px solid var(--vi-border); color: #c4b5fd;
}
.spill-warn {
  background: var(--amber-dim); border: 1px solid rgba(245,158,11,0.3); color: #fcd34d;
}
.spill-dot {
  width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0;
  box-shadow: 0 0 6px currentColor;
}

/* Doc badge */
.doc-badge {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 10px; border-radius: 6px;
  background: var(--glass); border: 1px solid var(--border);
  margin-bottom: 4px; font-size: 0.75rem; color: var(--text2);
  font-family: var(--mono);
}
.doc-dot {
  width: 5px; height: 5px; border-radius: 50%;
  background: var(--em); flex-shrink: 0;
  box-shadow: 0 0 5px var(--em-glow);
}

/* ─── PAGE HEADER ─────────────────────────────────────────────────────────── */
.page-header {
  position: relative; overflow: hidden;
  background: linear-gradient(135deg,
    rgba(16,185,129,0.07) 0%,
    rgba(8,12,20,0.9)    40%,
    rgba(139,92,246,0.07) 100%);
  border: 1px solid var(--em-border);
  border-radius: 16px;
  padding: 26px 32px 22px;
  margin-bottom: 28px;
  animation: float-up 0.5s ease both;
}
.page-header::before {
  content: '';
  position: absolute; top: 0; left: 0; right: 0; height: 1px;
  background: linear-gradient(90deg,
    transparent 0%, var(--em) 35%, var(--vi) 65%, transparent 100%);
}

/* RADAR ── */
.radar-wrap {
  position: absolute; top: -20px; right: 28px;
  width: 130px; height: 130px; opacity: 0.22;
}
.radar-base {
  position: absolute; inset: 0; border-radius: 50%;
  border: 1px solid var(--em);
}
.radar-ring {
  position: absolute; border-radius: 50%;
  border: 1px solid var(--em); top: 50%; left: 50%;
  transform: translate(-50%, -50%);
}
.radar-sweep {
  position: absolute; inset: 0; border-radius: 50%; overflow: hidden;
  animation: radar-sweep 3s linear infinite;
}
.radar-sweep::after {
  content: '';
  position: absolute; top: 50%; left: 50%;
  width: 50%; height: 2px;
  background: linear-gradient(90deg, transparent, var(--em));
  transform-origin: left center;
  box-shadow: 0 0 8px var(--em-glow);
}
.radar-ping {
  position: absolute; border-radius: 50%; border: 1px solid var(--em);
  top: 50%; left: 50%; transform: translate(-50%, -50%);
  animation: radar-ping 3s ease-out infinite;
}
.radar-cross-h {
  position: absolute; top: 50%; left: 0; right: 0; height: 1px;
  background: var(--em); transform: translateY(-50%);
}
.radar-cross-v {
  position: absolute; left: 50%; top: 0; bottom: 0; width: 1px;
  background: var(--em); transform: translateX(-50%);
}

.ph-system-tag {
  display: inline-flex; align-items: center; gap: 6px;
  background: var(--vi-dim); border: 1px solid var(--vi-border);
  border-radius: 6px; padding: 4px 11px; margin-bottom: 12px;
  font-family: var(--mono); font-size: 0.64rem; color: #c4b5fd;
  letter-spacing: 1.5px; text-transform: uppercase;
}
.ph-title {
  font-size: 2rem; font-weight: 900; letter-spacing: -1px;
  background: linear-gradient(135deg, #fff 30%, #94a3b8 100%);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  line-height: 1.1; margin-bottom: 6px;
}
.ph-sub {
  font-size: 0.8rem; color: var(--text3); letter-spacing: 0.3px;
}
.ph-badges {
  display: flex; gap: 7px; flex-wrap: wrap; margin-top: 16px;
}
.ph-badge {
  display: inline-flex; align-items: center; gap: 5px;
  background: var(--glass); border: 1px solid var(--border2);
  border-radius: 20px; padding: 4px 11px;
  font-size: 0.68rem; font-weight: 500; color: var(--text2);
}

/* ─── SECTION LABEL ──────────────────────────────────────────────────────── */
.sec-lbl {
  font-size: 0.6rem; font-weight: 700; letter-spacing: 2.5px;
  text-transform: uppercase; color: var(--text3);
  margin-bottom: 12px; display: flex; align-items: center; gap: 8px;
}
.sec-lbl::after {
  content: ''; flex: 1; height: 1px;
  background: linear-gradient(90deg, var(--border), transparent);
}

/* ─── GLASS CARDS ────────────────────────────────────────────────────────── */
.g-card {
  background: var(--glass);
  border: 1px solid var(--em-border);
  border-radius: 12px; padding: 18px 22px; margin-bottom: 14px;
  backdrop-filter: blur(12px);
  box-shadow: 0 0 0 0 transparent;
  transition: box-shadow 0.3s;
}
.g-card:hover { box-shadow: 0 0 20px rgba(16,185,129,0.06); }
.g-card-vi   { border-color: var(--vi-border); background: var(--vi-dim); }
.g-card-red  { border-color: var(--red-border); background: var(--red-dim); }
.g-card-em   { border-color: var(--em-border); background: var(--em-dim); }
.g-card-amber{ border-color: rgba(245,158,11,0.3); background: var(--amber-dim); }

/* ─── CHIPS ──────────────────────────────────────────────────────────────── */
.chip {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 3px 10px; border-radius: 20px;
  font-size: 0.69rem; font-weight: 500; font-family: var(--mono);
}
.chip-em  { background: var(--em-dim);    color: #6ee7b7; border: 1px solid var(--em-border); }
.chip-vi  { background: var(--vi-dim);    color: #c4b5fd; border: 1px solid var(--vi-border); }
.chip-red { background: var(--red-dim);   color: #fca5a5; border: 1px solid var(--red-border); }
.chip-amb { background: var(--amber-dim); color: #fcd34d; border: 1px solid rgba(245,158,11,0.3); }
.chip-off { background: var(--glass);     color: var(--text2); border: 1px solid var(--border); }

/* ─── HUD METRIC STRIP ───────────────────────────────────────────────────── */
.hud-strip {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 8px; margin-bottom: 22px;
}
.hud-cell {
  background: var(--glass);
  border: 1px solid var(--em-border);
  border-radius: 10px; padding: 14px 10px;
  text-align: center; position: relative; overflow: hidden;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.hud-cell:hover {
  border-color: var(--em);
  box-shadow: 0 0 18px var(--em-glow);
}
/* scanline sweep */
.hud-cell::before {
  content: '';
  position: absolute; left: 0; right: 0; height: 2px;
  background: linear-gradient(90deg, transparent, var(--em), transparent);
  opacity: 0.4;
  animation: scanline 4s linear infinite;
}
.hud-cell::after {
  content: '';
  position: absolute; bottom: 0; left: 0; right: 0; height: 2px;
  background: linear-gradient(90deg, transparent, var(--em), transparent);
  opacity: 0.6;
}
.hud-val {
  font-family: var(--mono); font-size: 1.65rem; font-weight: 600;
  color: var(--em); line-height: 1; display: block;
  text-shadow: 0 0 20px var(--em-glow);
  animation: em-pulse 3s ease-in-out infinite;
}
.hud-val.vi { color: var(--vi); text-shadow: 0 0 20px var(--vi-glow); animation: none; }
.hud-val.dim{ color: var(--text3); text-shadow: none; animation: none; }
.hud-lbl {
  font-family: var(--mono); font-size: 0.58rem; font-weight: 500;
  color: var(--text3); text-transform: uppercase; letter-spacing: 1.5px;
  margin-top: 6px; display: block;
}

/* ─── ANSWER BOX ─────────────────────────────────────────────────────────── */
.ans-box {
  background: var(--glass);
  border: 1px solid var(--em-border);
  border-radius: 14px; padding: 24px 28px;
  font-size: 0.92rem; line-height: 1.82; color: var(--text);
  margin-bottom: 14px; position: relative; overflow: hidden;
  box-shadow: 0 0 30px rgba(16,185,129,0.05);
  animation: float-up 0.4s ease both;
}
.ans-box::before {
  content: '';
  position: absolute; top: 0; left: 0; width: 3px; height: 100%;
  background: linear-gradient(180deg, var(--em), var(--vi));
  box-shadow: 0 0 12px var(--em-glow);
}

/* ─── SOURCE CARDS ───────────────────────────────────────────────────────── */
.src-card {
  background: var(--glass);
  border: 1px solid var(--border);
  border-radius: 12px; margin-bottom: 10px;
  overflow: hidden; position: relative;
  transition: border-color 0.25s, box-shadow 0.25s, transform 0.2s;
}
/* Violet lift on hover */
.src-card:hover {
  border-color: var(--vi-border);
  box-shadow: 0 4px 30px var(--vi-glow), 0 0 0 1px var(--vi-border);
  transform: translateY(-2px);
}
.src-card::before {
  content: '';
  position: absolute; top: 0; left: 0; right: 0; height: 1px;
  background: linear-gradient(90deg, transparent, var(--vi), transparent);
  opacity: 0; transition: opacity 0.25s;
}
.src-card:hover::before { opacity: 1; }

.src-head {
  background: var(--glass2);
  border-bottom: 1px solid var(--border);
  padding: 9px 14px;
  display: flex; justify-content: space-between; align-items: center; gap: 10px;
}
.src-meta {
  font-family: var(--mono); font-size: 0.69rem; color: var(--text3);
  display: flex; gap: 8px; align-items: center; flex-wrap: wrap;
}
.src-name { color: var(--text2); font-weight: 500; }
.sc-badge {
  font-family: var(--mono); font-size: 0.67rem; font-weight: 500;
  padding: 2px 8px; border-radius: 5px;
}
.sc-h { background: var(--em-dim);    color: #6ee7b7; border: 1px solid var(--em-border); }
.sc-m { background: var(--amber-dim); color: #fcd34d; border: 1px solid rgba(245,158,11,0.3); }
.sc-l { background: var(--red-dim);   color: #fca5a5; border: 1px solid var(--red-border); }
.sc-a { background: var(--glass);     color: var(--text3); border: 1px solid var(--border); }
.src-body {
  padding: 12px 15px; font-size: 0.83rem;
  line-height: 1.72; color: var(--text2);
}

/* ─── TRACE ROWS ─────────────────────────────────────────────────────────── */
.t-row {
  display: flex; align-items: flex-start; gap: 14px;
  padding: 12px 0; border-bottom: 1px solid var(--border);
}
.t-row:last-child { border-bottom: none; }
.t-num {
  width: 24px; height: 24px; border-radius: 50%;
  background: linear-gradient(135deg, var(--vi), #6d28d9);
  color: #fff; font-size: 0.67rem; font-weight: 700;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0; margin-top: 2px;
  box-shadow: 0 0 10px var(--vi-glow);
  font-family: var(--mono);
}
.t-num.ok   {
  background: linear-gradient(135deg, var(--em), #059669);
  box-shadow: 0 0 10px var(--em-glow);
}
.t-num.warn {
  background: linear-gradient(135deg, var(--amber), #d97706);
  box-shadow: 0 0 10px rgba(245,158,11,0.4);
}
.t-title  { font-size: 0.83rem; font-weight: 600; color: var(--text); margin-bottom: 3px; }
.t-detail { font-size: 0.74rem; color: var(--text3); font-family: var(--mono); line-height: 1.55; }

/* ─── REJECTED ROW ───────────────────────────────────────────────────────── */
.rej-row {
  background: var(--red-dim);
  border: 1px solid var(--red-border);
  border-left: 3px solid var(--red);
  border-radius: 8px; padding: 7px 12px; margin-bottom: 5px;
  font-family: var(--mono); font-size: 0.71rem; color: var(--text3);
}

/* ─── COMPUTE PANEL ──────────────────────────────────────────────────────── */
.cmp-panel {
  background: var(--glass);
  border: 1px solid var(--vi-border);
  border-radius: 12px; padding: 22px 26px;
  box-shadow: 0 0 24px rgba(139,92,246,0.08);
  position: relative; overflow: hidden;
}
.cmp-panel::before {
  content: '';
  position: absolute; top: 0; left: 0; right: 0; height: 1px;
  background: linear-gradient(90deg, transparent, var(--vi), transparent);
}
.cmp-hdr {
  font-family: var(--mono); font-size: 0.62rem; font-weight: 600;
  text-transform: uppercase; letter-spacing: 2px; color: var(--vi);
  margin-bottom: 16px;
}
.cmp-fl {
  font-family: var(--mono); font-size: 0.6rem; font-weight: 600;
  text-transform: uppercase; letter-spacing: 1.5px; color: var(--text3);
  margin-top: 14px; margin-bottom: 5px;
}
.cmp-val {
  font-family: var(--mono); font-size: 1.75rem; font-weight: 700;
  color: var(--vi); text-shadow: 0 0 20px var(--vi-glow);
}

/* ─── INFO PANEL ─────────────────────────────────────────────────────────── */
.ip-row {
  display: flex; align-items: flex-start; gap: 10px;
  padding: 8px 0; border-bottom: 1px solid var(--border);
}
.ip-row:last-child { border-bottom: none; }
.ip-icon {
  width: 28px; height: 28px; border-radius: 7px;
  background: var(--em-dim); border: 1px solid var(--em-border);
  display: flex; align-items: center; justify-content: center;
  font-size: 13px; flex-shrink: 0;
}
.ip-name { font-size: 0.8rem; font-weight: 600; color: var(--text); }
.ip-desc { font-size: 0.69rem; color: var(--text3); margin-top: 1px; }

/* ─── ACCESS TABLE ───────────────────────────────────────────────────────── */
.acc-tbl { width: 100%; font-size: 0.75rem; border-collapse: collapse; }
.acc-tbl tr { border-bottom: 1px solid var(--border); }
.acc-tbl tr:last-child { border-bottom: none; }
.acc-tbl td { padding: 6px 4px; color: var(--text2); }
.acc-tbl td:first-child {
  font-family: var(--mono); color: var(--em);
  font-weight: 600; width: 20px;
  text-shadow: 0 0 8px var(--em-glow);
}

/* ─── STREAMLIT OVERRIDES ────────────────────────────────────────────────── */
.stTextArea textarea {
  background: var(--obs3) !important;
  border: 1px solid var(--em-border) !important;
  color: var(--text) !important; border-radius: 10px !important;
  font-family: var(--sans) !important; font-size: 0.9rem !important;
  box-shadow: none !important; caret-color: var(--em);
}
.stTextArea textarea:focus {
  border-color: var(--em) !important;
  box-shadow: 0 0 0 3px var(--em-dim) !important;
}
.stTextInput input {
  background: var(--obs3) !important;
  border: 1px solid var(--em-border) !important;
  color: var(--text) !important; border-radius: 8px !important;
}
.stTextInput input:focus {
  border-color: var(--em) !important;
  box-shadow: 0 0 0 3px var(--em-dim) !important;
}
.stButton > button {
  background: linear-gradient(135deg, var(--em) 0%, #059669 100%) !important;
  color: #fff !important; font-weight: 700 !important;
  border: none !important; border-radius: 9px !important;
  font-family: var(--sans) !important; font-size: 0.84rem !important;
  padding: 0.48rem 1.1rem !important; letter-spacing: 0.2px;
  box-shadow: 0 4px 18px var(--em-glow) !important;
  transition: all 0.2s !important;
}
.stButton > button:hover {
  transform: translateY(-2px) !important;
  box-shadow: 0 8px 28px var(--em-glow) !important;
  background: linear-gradient(135deg, #34d399 0%, var(--em) 100%) !important;
}
.stButton > button:active { transform: translateY(0) !important; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
  background: var(--glass) !important;
  border: 1px solid var(--em-border) !important;
  border-radius: 10px !important; padding: 4px !important; gap: 2px !important;
}
.stTabs [data-baseweb="tab"] {
  color: var(--text3) !important; font-family: var(--sans) !important;
  font-weight: 500 !important; font-size: 0.8rem !important;
  border-radius: 7px !important; padding: 7px 13px !important;
  border: none !important; transition: all 0.2s !important;
}
.stTabs [aria-selected="true"] {
  color: var(--em) !important; font-weight: 700 !important;
  background: var(--em-dim) !important;
  box-shadow: 0 0 14px var(--em-glow) !important;
}

/* Expander */
.streamlit-expanderHeader {
  background: var(--glass) !important;
  border: 1px solid var(--em-border) !important;
  border-radius: 8px !important;
  font-family: var(--sans) !important; font-size: 0.8rem !important;
  font-weight: 500 !important; color: var(--text2) !important;
}

/* Slider thumb */
.stSlider > div > div > div { background: var(--em) !important; }

/* Select */
.stSelectbox [data-baseweb="select"] > div {
  background: var(--obs3) !important;
  border: 1px solid var(--em-border) !important;
  border-radius: 8px !important; color: var(--text) !important;
}

/* File uploader */
[data-testid="stFileUploader"] {
  border: 1.5px dashed var(--em-border) !important;
  border-radius: 10px !important; background: var(--glass) !important;
}
[data-testid="stFileUploader"]:hover {
  border-color: var(--em) !important;
  background: var(--em-dim) !important;
}

/* Checkbox / radio */
.stCheckbox span, .stRadio span { color: var(--text2) !important; font-size: 0.81rem !important; }

/* Caption */
.stCaption { color: var(--text3) !important; font-size: 0.69rem !important; }

/* Progress bar */
.stProgress > div > div {
  background: linear-gradient(90deg, var(--em), var(--vi)) !important;
  border-radius: 4px !important;
  box-shadow: 0 0 10px var(--em-glow) !important;
}

/* Alerts */
.stSuccess {
  background: var(--em-dim) !important; border-color: var(--em-border) !important;
  color: #6ee7b7 !important; border-radius: 8px !important;
}
.stWarning {
  background: var(--amber-dim) !important; border-color: rgba(245,158,11,0.3) !important;
  color: #fcd34d !important; border-radius: 8px !important;
}
.stError {
  background: var(--red-dim) !important; border-color: var(--red-border) !important;
  color: #fca5a5 !important; border-radius: 8px !important;
}

/* Labels */
label[data-testid="stWidgetLabel"] { color: var(--text2) !important; font-size: 0.78rem !important; }

/* Divider */
hr { border-color: var(--border) !important; }

/* Scrollbar */
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--em-border); border-radius: 2px; }
::-webkit-scrollbar-thumb:hover { background: var(--em); }
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  SESSION STATE
# ═══════════════════════════════════════════════════════════════════════════════
for k, v in [("pipeline", None), ("vector_manager", None), ("last_response", None),
              ("ingested_docs", []), ("api_key_set", bool(CONFIG.GROQ_API_KEY)),
              ("chat_history", []), ("active_feature", None), ("docs_loaded", False)]:
    if k not in st.session_state:
        st.session_state[k] = v


def get_pipeline():
    if st.session_state.pipeline is None:
        st.session_state.pipeline       = SentinelPipeline()
        st.session_state.vector_manager = st.session_state.pipeline.vector_store
    return st.session_state.pipeline


# ═══════════════════════════════════════════════════════════════════════════════
#  SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("""
    <div class="sb-brand">
      <div class="sb-scout-badge">
        <div class="sb-scout-dot"></div>
        <span class="sb-scout-text">SCOUT SYSTEM</span>
      </div>
      <div class="sb-name">SCOUT</div>
      <div class="sb-sub">stealth intelligence · v1.0</div>
    </div>
    """, unsafe_allow_html=True)

    # ── API Key ──
    st.markdown('<div class="sb-sec">API Configuration</div>', unsafe_allow_html=True)
    api_key = st.text_input("", value=CONFIG.GROQ_API_KEY, type="password",
                            placeholder="sk-...", label_visibility="collapsed")
    if api_key:
        CONFIG.GROQ_API_KEY = api_key
        os.environ["GROQ_API_KEY"] = api_key
        st.session_state.api_key_set = True
    if st.session_state.api_key_set:
        st.markdown('<div class="spill spill-em"><div class="spill-dot" style="background:var(--em)"></div>API · CONNECTED</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="spill spill-warn"><div class="spill-dot" style="background:var(--amber)"></div>API · KEY REQUIRED</div>', unsafe_allow_html=True)

    # ── RBAC ──
    st.markdown('<div class="sb-sec">Access Control (RBAC)</div>', unsafe_allow_html=True)
    user_access = st.slider("", 1, 5, 2, label_visibility="collapsed")
    lbl = {1: "PUBLIC", 2: "STANDARD", 3: "PROFESSIONAL", 4: "INTERNAL", 5: "ADMINISTRATOR"}
    st.markdown(f'<div class="spill spill-em"><div class="spill-dot" style="background:var(--em)"></div>LVL {user_access} · {lbl[user_access]}</div>', unsafe_allow_html=True)

    # ── Temporal ──
    st.markdown('<div class="sb-sec">Temporal Filter</div>', unsafe_allow_html=True)
    use_temporal = st.checkbox("Enable temporal filtering", value=False)
    after_date = before_date = milestone_filter = None
    if use_temporal:
        ftype = st.radio("", ["Date Range", "Milestone"], horizontal=True, label_visibility="collapsed")
        if ftype == "Date Range":
            after_date  = st.date_input("From", value=datetime.now().date() - timedelta(days=180), label_visibility="collapsed")
            before_date = st.date_input("To",   value=datetime.now().date(), label_visibility="collapsed")
            after_date  = datetime.combine(after_date,  datetime.min.time())
            before_date = datetime.combine(before_date, datetime.max.time())
        else:
            milestone_filter = st.selectbox("", ["Q1-2024","Q2-2024","Q3-2024","Q4-2024","Q1-2025","v1.0","v2.0","v3.0"],
                                            label_visibility="collapsed")

    # ── Ingestion ──
    st.markdown('<div class="sb-sec">Document Ingestion</div>', unsafe_allow_html=True)
    uploaded_files = st.file_uploader("", type=["pdf","txt","md"],
                                      accept_multiple_files=True, label_visibility="collapsed")
    c1, c2 = st.columns(2)
    with c1: authority  = st.slider("Authority",  0.0, 1.0, 0.85, 0.05)
    with c2: doc_access = st.slider("Doc Level",  1,   5,   1)

    if st.button("⬆  Ingest Documents", use_container_width=True):
        if not st.session_state.api_key_set:
            st.error("API key required.")
        elif not uploaded_files:
            st.warning("Select files first.")
        else:
            p = get_pipeline(); total = 0
            with st.spinner("Embedding vectors…"):
                for uf in uploaded_files:
                    ext = os.path.splitext(uf.name)[-1].lower()
                    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                        tmp.write(uf.read()); tmp_path = tmp.name
                    try:
                        docs = load_and_chunk_file(tmp_path, authority_score=authority, access_level=doc_access)
                        for d in docs: d.metadata["source"] = uf.name
                        n = p.vector_store.add_documents(docs)
                        total += n; st.session_state.ingested_docs.append(uf.name)
                        st.session_state.docs_loaded = True
                        st.success(f"{uf.name} · {n} chunks")
                    except Exception as e: st.error(str(e))
                    finally: os.unlink(tmp_path)
            st.success(f"Total indexed: {total} chunks")

    if st.button("✦  Load Demo Dataset", use_container_width=True):
        if not st.session_state.api_key_set:
            st.error("API key required.")
        else:
            p = get_pipeline()
            demo = os.path.join(os.path.dirname(__file__), "data", "demo_documents.txt")
            with st.spinner("Initialising demo corpus…"):
                try:
                    docs  = load_and_chunk_file(demo, authority_score=0.85, access_level=1)
                    hdocs = load_and_chunk_file(demo, authority_score=0.99, access_level=4)
                    for d in hdocs:
                        d.metadata["source"] = "security_policy_internal.txt"
                        d.metadata["access_level"] = 4
                    n = p.vector_store.add_documents(docs + hdocs[:10])
                    st.session_state.ingested_docs.append("Demo Dataset")
                    st.session_state.docs_loaded = True
                    st.success(f"Demo corpus loaded · {n} chunks")
                except Exception as e: st.error(str(e))

    if st.session_state.vector_manager:
        count = st.session_state.vector_manager.doc_count()
        cls = "spill-em" if count > 0 else "spill-warn"
        dot_bg = "var(--em)" if count > 0 else "var(--amber)"
        st.markdown(f'<div class="spill {cls}" style="margin-top:10px"><div class="spill-dot" style="background:{dot_bg}"></div>INDEX · {count} VECTORS</div>', unsafe_allow_html=True)

    if st.session_state.ingested_docs:
        st.markdown('<div class="sb-sec">Indexed Sources</div>', unsafe_allow_html=True)
        for doc in st.session_state.ingested_docs:
            st.markdown(f'<div class="doc-badge"><div class="doc-dot"></div>{doc}</div>', unsafe_allow_html=True)

    st.markdown("---")
    if st.button("↺  Reset Index", use_container_width=True):
        if st.session_state.vector_manager:
            st.session_state.vector_manager.reset()
            st.session_state.pipeline = st.session_state.vector_manager = None
            st.session_state.ingested_docs = []
            st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE HEADER  — with Radar
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div class="page-header">

  <!-- Radar -->
  <div class="radar-wrap">
    <div class="radar-base"></div>
    <div class="radar-ring" style="width:70%;height:70%"></div>
    <div class="radar-ring" style="width:42%;height:42%"></div>
    <div class="radar-cross-h"></div>
    <div class="radar-cross-v"></div>
    <div class="radar-sweep"></div>
    <div class="radar-ping" style="width:90%;height:90%;animation-delay:0s"></div>
    <div class="radar-ping" style="width:60%;height:60%;animation-delay:1s"></div>
  </div>

  <div class="ph-system-tag">
    <span>◈</span> SCOUT INTELLIGENCE SYSTEM
  </div>
  <div class="ph-title">SCOUT</div>
  <div class="ph-sub">Agentic retrieval with full pipeline observability · stealth mode active</div>
  <div class="ph-badges">
    <div class="ph-badge">🎯 Intent Routing</div>
    <div class="ph-badge">🔒 RBAC</div>
    <div class="ph-badge">⚡ LLM Rerank</div>
    <div class="ph-badge">⚠️ Conflict Detection</div>
    <div class="ph-badge">🔢 Compute Sandbox</div>
    <div class="ph-badge">📊 Decision Trace</div>
  </div>
</div>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN LAYOUT  — full-width chatbot
# ═══════════════════════════════════════════════════════════════════════════════

# Extra CSS for chatbot UI, feature panel, + button
st.markdown("""
<style>
/* ─── CHAT MESSAGES ─────────────────────────────────────────────────────────── */
.chat-wrap { display:flex; flex-direction:column; gap:14px; margin-bottom:18px; }

.msg-user {
  display:flex; justify-content:flex-end;
}
.msg-user .bubble {
  background: linear-gradient(135deg, var(--em-dim), var(--vi-dim));
  border: 1px solid var(--em-border);
  border-radius: 16px 16px 4px 16px;
  padding: 11px 16px; max-width: 72%;
  font-size: 0.88rem; color: var(--text); line-height: 1.65;
}

.msg-scout {
  display:flex; justify-content:flex-start; gap:10px;
}
.msg-scout .avatar {
  width:32px; height:32px; border-radius:50%;
  background: linear-gradient(135deg, var(--em), var(--vi));
  display:flex; align-items:center; justify-content:center;
  font-size:14px; flex-shrink:0; margin-top:4px;
  box-shadow: 0 0 12px var(--em-glow);
}
.msg-scout .bubble {
  background: var(--glass);
  border: 1px solid var(--border2);
  border-radius: 4px 16px 16px 16px;
  padding: 13px 18px; max-width: 80%;
  font-size: 0.88rem; color: var(--text); line-height: 1.72;
}

.msg-chips {
  display:flex; gap:6px; flex-wrap:wrap; margin-top:10px;
}

/* ─── INPUT ROW ──────────────────────────────────────────────────────────────── */
.input-row-wrap {
  display: flex; align-items: flex-end; gap: 8px;
}

/* ─── FEATURE PANEL ──────────────────────────────────────────────────────────── */
.feat-panel {
  background: var(--obs2);
  border: 1px solid var(--vi-border);
  border-radius: 14px;
  padding: 16px; margin-bottom: 16px;
  animation: float-up 0.25s ease both;
}
.feat-panel-title {
  font-family: var(--mono); font-size:0.6rem; font-weight:700;
  text-transform:uppercase; letter-spacing:2px; color:var(--vi);
  margin-bottom: 12px;
}
.feat-item {
  display:flex; align-items:flex-start; gap:10px;
  padding: 9px 11px; border-radius:9px;
  border: 1px solid var(--border);
  background: var(--glass);
  margin-bottom:7px; cursor:pointer;
  transition: border-color 0.2s, background 0.2s;
}
.feat-item:hover, .feat-item.active {
  border-color: var(--vi-border);
  background: var(--vi-dim);
}
.feat-icon { font-size:16px; flex-shrink:0; margin-top:1px; }
.feat-name { font-size:0.8rem; font-weight:600; color:var(--text); }
.feat-desc { font-size:0.68rem; color:var(--text3); margin-top:2px; font-family:var(--mono); }

/* ─── QUICK QUERIES ──────────────────────────────────────────────────────────── */
.qq-row {
  display:flex; flex-wrap:wrap; gap:7px; margin-bottom:18px;
}
.qq-chip {
  background: var(--glass); border: 1px solid var(--em-border);
  border-radius:20px; padding:5px 13px;
  font-size:0.73rem; color:var(--text2); cursor:pointer;
  font-family:var(--mono);
  transition: background 0.2s, color 0.2s, border-color 0.2s;
}
.qq-chip:hover {
  background: var(--em-dim); color: var(--em); border-color: var(--em);
}

/* ─── SEND BUTTON ────────────────────────────────────────────────────────────── */
.stButton > button[kind="primary"] {
  min-width: 44px !important; width: 44px !important;
  height: 44px !important; padding: 0 !important;
  border-radius: 12px !important;
  font-size: 1.1rem !important; line-height:1 !important;
}

/* ─── PLUS BUTTON ────────────────────────────────────────────────────────────── */
.plus-btn-wrap .stButton > button {
  background: var(--glass) !important;
  border: 1px solid var(--vi-border) !important;
  color: var(--vi) !important;
  box-shadow: none !important;
  min-width: 44px !important; width: 44px !important;
  height: 44px !important; padding: 0 !important;
  border-radius: 12px !important; font-size: 1.2rem !important;
}
.plus-btn-wrap .stButton > button:hover {
  background: var(--vi-dim) !important;
  box-shadow: 0 0 14px var(--vi-glow) !important;
  transform: none !important;
}
</style>
""", unsafe_allow_html=True)


# ── Document loading gate ──────────────────────────────────────────────────────
if not st.session_state.docs_loaded and not st.session_state.ingested_docs:
    # Welcome / onboarding screen
    st.markdown("""
    <div style="display:flex; flex-direction:column; align-items:center; justify-content:center;
                min-height:55vh; text-align:center; padding:40px 20px;">
      <div style="width:72px; height:72px; border-radius:50%;
                  background:linear-gradient(135deg, var(--em-dim), var(--vi-dim));
                  border: 1px solid var(--em-border);
                  display:flex; align-items:center; justify-content:center;
                  font-size:32px; margin:0 auto 24px; box-shadow:0 0 28px var(--em-glow)">
        🛡️
      </div>
      <div style="font-size:1.8rem; font-weight:900; letter-spacing:-0.5px;
                  background:linear-gradient(135deg,#fff 30%,#94a3b8 100%);
                  -webkit-background-clip:text; -webkit-text-fill-color:transparent;
                  margin-bottom:10px">
        Welcome to SCOUT
      </div>
      <div style="font-size:0.88rem; color:var(--text3); max-width:440px; line-height:1.7; margin-bottom:32px">
        Load your documents in the sidebar to begin. SCOUT will intelligently index, retrieve,
        and reason across your knowledge base with full pipeline observability.
      </div>
      <div style="background:var(--glass); border:1px solid var(--em-border); border-radius:14px;
                  padding:22px 28px; max-width:420px; text-align:left">
        <div style="font-family:var(--mono); font-size:0.6rem; font-weight:700; text-transform:uppercase;
                    letter-spacing:2px; color:var(--em); margin-bottom:14px">← Upload in the sidebar</div>
        <div style="font-size:0.82rem; color:var(--text2); line-height:1.9">
          1. Enter your <strong style="color:var(--text)">GROQ API key</strong><br>
          2. Upload <strong style="color:var(--text)">PDF / TXT / MD</strong> documents<br>
          3. Set authority &amp; access level<br>
          4. Click <strong style="color:var(--em)">⬆ Ingest Documents</strong><br>
          5. Start chatting with your knowledge base
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)
else:
    # Mark docs as logically loaded once sidebar has ingested
    if st.session_state.ingested_docs:
        st.session_state.docs_loaded = True

    # ── Feature panel (+ button) ──────────────────────────────────────────────
    FEATURES = [
        ("🎯", "Intent Classification",  "Support / Technical routing"),
        ("🔍", "Vector Retrieval",        "FAISS top-20 semantic"),
        ("🔒", "RBAC Filter",             "Access level gate"),
        ("📅", "Temporal Filter",         "Date & milestone scope"),
        ("⚡", "LLM Reranker",            "Relevance × Recency × Auth"),
        ("⚠️", "Conflict Detection",      "Contradiction analysis"),
        ("🔢", "Compute Sandbox",         "Safe numerical execution"),
        ("📝", "Answer Agent",            "Grounded generation"),
        ("📊", "Decision Trace",          "Full audit trail"),
    ]

    plus_col, _ = st.columns([1, 11])
    with plus_col:
        st.markdown('<div class="plus-btn-wrap">', unsafe_allow_html=True)
        if st.button("＋", key="plus_btn"):
            st.session_state.active_feature = None if st.session_state.active_feature == "open" else "open"
        st.markdown('</div>', unsafe_allow_html=True)

    if st.session_state.active_feature == "open":
        st.markdown('<div class="feat-panel">', unsafe_allow_html=True)
        st.markdown('<div class="feat-panel-title">Pipeline Features</div>', unsafe_allow_html=True)
        f_cols = st.columns(3)
        for idx, (icon, name, desc) in enumerate(FEATURES):
            with f_cols[idx % 3]:
                st.markdown(f"""
                <div class="feat-item">
                  <div class="feat-icon">{icon}</div>
                  <div>
                    <div class="feat-name">{name}</div>
                    <div class="feat-desc">{desc}</div>
                  </div>
                </div>""", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # ── Quick Queries (document-tailored) ────────────────────────────────────
    if st.session_state.ingested_docs:
        doc_names = st.session_state.ingested_docs
        # Generate queries based on what docs are loaded
        if any("demo" in d.lower() for d in doc_names):
            quick_queries = [
                "API rate limit for Enterprise?",
                "Password reset steps",
                "Q1-2025 cost & revenue",
                "Encryption standards (Level 4+)",
                "v1 vs v2 auth methods",
                "Refund policy",
            ]
        else:
            quick_queries = [f"Summarise {doc_names[0]}" if doc_names else "What documents are loaded?",
                             "What are the key topics covered?",
                             "Find any conflicts or contradictions",
                             "What access levels are required?"]
        st.markdown('<div class="qq-row">' +
                    "".join(f'<span class="qq-chip" onclick="void(0)">→ {q}</span>' for q in quick_queries) +
                    '</div>', unsafe_allow_html=True)

    # ── Chat history display ──────────────────────────────────────────────────
    st.markdown('<div class="chat-wrap">', unsafe_allow_html=True)
    for entry in st.session_state.chat_history:
        role = entry["role"]
        if role == "user":
            st.markdown(f"""
            <div class="msg-user">
              <div class="bubble">{entry["content"]}</div>
            </div>""", unsafe_allow_html=True)
        else:
            r = entry.get("response")
            if r:
                trace = r.decision_trace
                ic  = "chip-em"  if trace.intent.intent == "support" else "chip-vi"
                cc2 = "chip-red" if r.conflict.has_conflict else "chip-em"
                cl  = "⚠ CONFLICT" if r.conflict.has_conflict else "✓ VERIFIED"
                chips = f"""
                <div class="msg-chips">
                  <span class="chip {ic}">INTENT · {trace.intent.intent.upper()}</span>
                  <span class="chip chip-off">CONF · {trace.intent.confidence:.0%}</span>
                  <span class="chip {cc2}">{cl}</span>
                  {'<span class="chip chip-amb">⚠ SOURCES DISAGREE</span>' if r.conflict.has_conflict else ''}
                </div>"""
                st.markdown(f"""
                <div class="msg-scout">
                  <div class="avatar">⚡</div>
                  <div class="bubble">
                    {r.answer.replace(chr(10), "<br>")}
                    {chips}
                  </div>
                </div>""", unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="msg-scout">
                  <div class="avatar">⚡</div>
                  <div class="bubble">{entry["content"]}</div>
                </div>""", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Show last response detail tabs if there is a last response
    if st.session_state.last_response:
        r     = st.session_state.last_response
        trace = r.decision_trace

        # HUD metrics
        cv  = "ACTIVE" if r.computation.triggered else "—"
        cvc = "vi" if r.computation.triggered else "dim"
        st.markdown(f"""
        <div class="hud-strip">
          <div class="hud-cell">
            <span class="hud-val">{trace.total_retrieved}</span>
            <span class="hud-lbl">Retrieved</span>
          </div>
          <div class="hud-cell">
            <span class="hud-val">{trace.rbac_filtered}</span>
            <span class="hud-lbl">RBAC Blocked</span>
          </div>
          <div class="hud-cell">
            <span class="hud-val">{trace.temporal_filtered}</span>
            <span class="hud-lbl">Time Filtered</span>
          </div>
          <div class="hud-cell">
            <span class="hud-val">{trace.reranked_selected}</span>
            <span class="hud-lbl">Selected</span>
          </div>
          <div class="hud-cell">
            <span class="hud-val {cvc}">{cv}</span>
            <span class="hud-lbl">Compute</span>
          </div>
        </div>
        """, unsafe_allow_html=True)

        # Tabs
        t1, t2, t3, t4, t5 = st.tabs([
            "✦ Answer", "📡 Sources", "⚡ Conflicts", "🔍 Trace", "🔢 Compute"
        ])

        # ── Answer ──────────────────────────────────────────────────────────
        with t1:
            st.markdown(
                f'<div class="ans-box">{r.answer.replace(chr(10), "<br>")}</div>',
                unsafe_allow_html=True,
            )
            if r.conflict.has_conflict:
                st.markdown("""
                <div class="g-card g-card-red">
                  <div style="font-size:0.79rem; font-weight:700; color:#fca5a5; margin-bottom:6px">
                    ⚠  CONFLICT ALERT — Sources disagree
                  </div>
                  <div style="font-size:0.79rem; color:var(--text3); line-height:1.65">
                    Multiple retrieved documents contain contradictory information.
                    Check the Conflicts tab. Prioritise higher authority scores and newer timestamps.
                  </div>
                </div>""", unsafe_allow_html=True)

        # ── Sources ─────────────────────────────────────────────────────────
        with t2:
            st.markdown(
                f'<div style="font-size:0.7rem; color:var(--text3); font-family:var(--mono); margin-bottom:12px">'
                f'CORPUS · {len(r.sources)} sources ranked by relevance · recency · authority</div>',
                unsafe_allow_html=True,
            )
            for i, c in enumerate(r.sources, 1):
                sc, sl = ("sc-h","HIGH") if c.rerank_score >= 0.7 else \
                         (("sc-m","MED") if c.rerank_score >= 0.4 else ("sc-l","LOW"))
                st.markdown(f"""
                <div class="src-card">
                  <div class="src-head">
                    <div class="src-meta">
                      <span style="color:var(--em); font-weight:600">#{i:02d}</span>
                      <span class="src-name">{c.metadata.source}</span>
                      <span>·</span><span>{c.metadata.milestone_tag or "—"}</span>
                      <span>·</span><span>{c.metadata.timestamp.strftime("%Y-%m-%d")}</span>
                      <span>·</span><span>LVL {c.metadata.access_level}</span>
                    </div>
                    <div style="display:flex; gap:5px; align-items:center">
                      <span class="sc-badge {sc}">SCORE {c.rerank_score:.2f} · {sl}</span>
                      <span class="sc-badge sc-a">AUTH {c.metadata.authority_score:.2f}</span>
                    </div>
                  </div>
                  <div class="src-body">{c.content[:440]}{"…" if len(c.content) > 440 else ""}</div>
                </div>""", unsafe_allow_html=True)

        # ── Conflict Analysis ────────────────────────────────────────────────
        with t3:
            if r.conflict.has_conflict:
                ids_html = "".join(
                    f'<span class="chip chip-red" style="margin:2px">{cid}</span>'
                    for cid in r.conflict.conflicting_chunks
                )
                st.markdown(f"""
                <div class="g-card g-card-red">
                  <div style="font-size:0.79rem; font-weight:700; color:#fca5a5; margin-bottom:10px">
                    ⚠  CONFLICT DETECTED
                  </div>
                  <div style="font-size:0.86rem; color:var(--text); line-height:1.8; margin-bottom:14px">
                    {r.conflict.explanation}
                  </div>
                  <div style="font-family:var(--mono); font-size:0.6rem; font-weight:600; text-transform:uppercase;
                              letter-spacing:1.5px; color:var(--text3); margin-bottom:8px">Conflicting IDs</div>
                  <div>{ids_html}</div>
                </div>
                <div class="g-card">
                  <div style="font-size:0.79rem; color:var(--text3); line-height:1.72">
                    <strong style="color:var(--text2)">Recommendation:</strong>
                    Prefer documents with higher authority scores and newer timestamps.
                    Deprecated sources may contain stale data. Verify against the most current documentation before acting.
                  </div>
                </div>""", unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class="g-card g-card-em">
                  <div style="font-size:0.82rem; font-weight:700; color:#6ee7b7; margin-bottom:7px">
                    ✓  VERIFIED — No Conflicts Detected
                  </div>
                  <div style="font-size:0.81rem; color:var(--text3)">
                    All retrieved chunks are consistent.
                    No contradictory information found across selected sources.
                  </div>
                </div>""", unsafe_allow_html=True)

        # ── Decision Trace ───────────────────────────────────────────────────
        with t4:
            st.markdown('<div class="sec-lbl">Pipeline Execution Log</div>', unsafe_allow_html=True)

            pipe_steps = [
                (False, "Intent Classification",
                 f"Classified as {trace.intent.intent.upper()} · {trace.intent.confidence:.0%} confidence · {trace.intent.reasoning}"),
                (False, "Vector Retrieval",
                 f"Retrieved {trace.total_retrieved} candidates from FAISS via semantic similarity"),
                (trace.rbac_filtered > 0, "RBAC Enforcement",
                 f"{trace.rbac_filtered} chunks blocked · User LVL {user_access} · {trace.total_retrieved - trace.rbac_filtered} passed"),
                (trace.temporal_filtered > 0, "Temporal Filtering",
                 f"{trace.temporal_filtered} chunks excluded by date / milestone rule"),
                (False, "LLM Reranking",
                 f"Relevance 50% · Recency 30% · Authority 20% → top {trace.reranked_selected} selected"),
                (r.conflict.has_conflict, "Conflict Detection",
                 (r.conflict.explanation[:110] + "…") if r.conflict.has_conflict else "No contradictions found across selected chunks"),
                (False, "Answer Generation",
                 f"Synthesised from {len(r.sources)} sources · {'Conflict-aware dual mode' if r.conflict.has_conflict else 'Standard grounded generation'}"),
            ]

            st.markdown('<div class="g-card" style="padding:14px 18px">', unsafe_allow_html=True)
            for i, (warn, title, detail) in enumerate(pipe_steps, 1):
                nc = "warn" if warn else "ok"
                st.markdown(f"""
                <div class="t-row">
                  <div class="t-num {nc}">{i}</div>
                  <div>
                    <div class="t-title">{title}</div>
                    <div class="t-detail">{detail}</div>
                  </div>
                </div>""", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

            st.markdown(f"""
            <div class="g-card g-card-vi" style="margin-top:0">
              <div style="font-family:var(--mono); font-size:0.6rem; font-weight:600;
                          text-transform:uppercase; letter-spacing:2px; color:var(--vi); margin-bottom:9px">
                REASONING SUMMARY
              </div>
              <div style="font-size:0.86rem; color:var(--text); line-height:1.8">
                {trace.reasoning_summary}
              </div>
            </div>""", unsafe_allow_html=True)

            if trace.rejected_chunks:
                with st.expander(f"Rejected chunks  ·  {len(trace.rejected_chunks)} total"):
                    for rj in trace.rejected_chunks:
                        st.markdown(
                            f'<div class="rej-row"><strong style="color:var(--text2)">{rj.get("id","?")}</strong>'
                            f'&nbsp;&nbsp;{rj.get("reason","")}</div>',
                            unsafe_allow_html=True,
                        )

        # ── Computation ──────────────────────────────────────────────────────
        with t5:
            if r.computation.triggered:
                st.markdown(f"""
                <div class="cmp-panel">
                  <div class="cmp-hdr">◈ Numerical Compute · Excel Sandbox</div>
                  <div class="cmp-fl">Extracted Data</div>
                  <div style="font-size:0.84rem; color:var(--text); line-height:1.6">
                    {r.computation.extracted_data or "—"}
                  </div>
                  <div class="cmp-fl">Computation Applied</div>
                  <div style="font-size:0.84rem; color:var(--text)">
                    {r.computation.computation or "—"}
                  </div>
                  <div class="cmp-fl">Result</div>
                  <div class="cmp-val">{r.computation.result or "—"}</div>
                </div>""", unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class="g-card">
                  <div style="font-size:0.82rem; color:var(--text3); margin-bottom:6px">
                    No computation triggered for this query.
                  </div>
                  <div style="font-size:0.76rem; color:var(--text3); font-family:var(--mono)">
                    AUTO-ACTIVATES for: sums · averages · costs · counts · rates
                  </div>
                </div>""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  CHAT INPUT  — always at the bottom when docs are loaded
# ═══════════════════════════════════════════════════════════════════════════════
if st.session_state.ingested_docs or st.session_state.docs_loaded:
    st.markdown('<div class="sec-lbl" style="margin-top:8px">ASK SCOUT</div>', unsafe_allow_html=True)

    inp_col, send_col = st.columns([11, 1])
    with inp_col:
        query = st.text_input("", placeholder="Ask anything about your documents…",
                              label_visibility="collapsed", key="chat_input")
    with send_col:
        send_btn = st.button("➤", use_container_width=True, type="primary", key="send_btn")

    if (send_btn or (query and query.strip())) and query.strip():
        if not st.session_state.api_key_set:
            st.error("Enter your GROQ API key in the sidebar.")
        else:
            pipeline = get_pipeline()
            if not pipeline.vector_store.is_ready():
                st.warning("No vectors indexed — load the demo dataset or upload documents.")
            else:
                # Add user message to chat
                st.session_state.chat_history.append({"role": "user", "content": query.strip()})

                prog = st.progress(0, "Initialising SCOUT…")
                try:
                    for pct, msg in [
                        (12, "SCOUT · Classifying intent…"),
                        (27, "SCOUT · Retrieving top-20 candidates…"),
                        (45, "SCOUT · RBAC & temporal gate…"),
                        (62, "SCOUT · LLM reranking…"),
                        (78, "SCOUT · Conflict analysis…"),
                        (91, "SCOUT · Synthesising answer…"),
                    ]:
                        prog.progress(pct, msg); time.sleep(0.07)

                    response = pipeline.run(
                        query=query.strip(),
                        user_access_level=user_access,
                        after_date=after_date   if use_temporal else None,
                        before_date=before_date if use_temporal else None,
                        milestone_tag=milestone_filter if use_temporal else None,
                    )
                    prog.progress(100, "SCOUT · Complete ✓")
                    time.sleep(0.12); prog.empty()

                    # Add scout response to chat
                    st.session_state.chat_history.append({
                        "role": "scout",
                        "content": response.answer,
                        "response": response
                    })
                    st.session_state.last_response = response
                    st.rerun()

                except Exception as e:
                    prog.empty(); st.error(f"Pipeline error: {e}")
                    import traceback; st.code(traceback.format_exc())
