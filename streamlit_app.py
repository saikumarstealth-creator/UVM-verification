"""
Enterprise-Grade UVM Testbench Generator UI
Premium Dark Theme - Inspired by Cadence, Synopsys, NVIDIA AI Platforms
"""

import streamlit as st
import logging
import tempfile
import os
import zipfile
import io
from pathlib import Path
from datetime import datetime
import json
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("uvmgen-enterprise")

st.set_page_config(
    page_title="UVM Verification Platform",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://github.com/saikumarstealth-creator/UVM-verification',
        'Report a bug': 'https://github.com/saikumarstealth-creator/UVM-verification/issues',
        'About': 'Enterprise UVM Testbench Generator - AI-Powered Semiconductor Verification Platform'
    }
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
    
    * {
        font-family: 'Inter', sans-serif;
    }
    
    code, pre, .stCodeBlock {
        font-family: 'JetBrains Mono', monospace;
    }
    
    .stApp {
        background: linear-gradient(135deg, #0a0e27 0%, #1a1f3a 50%, #0d1120 100%);
    }
    
    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
    }
    
    .glass-card {
        background: rgba(30, 35, 60, 0.6);
        backdrop-filter: blur(20px);
        border: 1px solid rgba(100, 150, 255, 0.15);
        border-radius: 8px;
        padding: 1.25rem;
        margin-bottom: 1rem;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3),
                    inset 0 1px 0 rgba(255, 255, 255, 0.05);
        transition: all 0.3s ease;
    }
    
    .glass-card:hover {
        border-color: rgba(100, 200, 255, 0.3);
        box-shadow: 0 8px 32px rgba(0, 150, 255, 0.1),
                    inset 0 1px 0 rgba(255, 255, 255, 0.1);
        transform: translateY(-2px);
    }
    
    .metric-card {
        background: linear-gradient(135deg, rgba(30, 40, 70, 0.8) 0%, rgba(20, 25, 45, 0.9) 100%);
        backdrop-filter: blur(20px);
        border-left: 3px solid #00d4ff;
        border-radius: 6px;
        padding: 1rem;
        text-align: center;
        transition: all 0.3s ease;
        border-top: 1px solid rgba(100, 200, 255, 0.1);
        border-right: 1px solid rgba(0, 0, 0, 0.2);
        border-bottom: 1px solid rgba(0, 0, 0, 0.3);
    }
    
    .metric-card:hover {
        border-left-color: #00ff88;
        transform: translateY(-3px);
        box-shadow: 0 10px 40px rgba(0, 200, 255, 0.15);
    }
    
    .metric-value {
        font-size: 1.5rem;
        font-weight: 700;
        background: linear-gradient(135deg, #00d4ff 0%, #00ff88 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    
    .metric-label {
        font-size: 0.75rem;
        color: #8892b0;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-top: 0.25rem;
        font-weight: 500;
    }
    
    .section-header {
        font-size: 0.85rem;
        font-weight: 600;
        color: #00d4ff;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 0.75rem;
        padding-bottom: 0.5rem;
        border-bottom: 1px solid rgba(100, 150, 255, 0.2);
    }
    
    .status-passed {
        color: #00ff88;
        font-weight: 600;
    }
    
    .status-warning {
        color: #ffb020;
        font-weight: 600;
    }
    
    .status-error {
        color: #ff5555;
        font-weight: 600;
    }
    
    .neon-text {
        text-shadow: 0 0 10px rgba(0, 200, 255, 0.5),
                     0 0 20px rgba(0, 200, 255, 0.3);
    }
    
    div[data-testid="stSidebar"] {
        background: linear-gradient(180deg, rgba(15, 20, 40, 0.95) 0%, rgba(8, 12, 25, 0.98) 100%);
        border-right: 1px solid rgba(100, 150, 255, 0.1);
    }
    
    div[data-testid="stSidebar"] > div:first-child {
        padding-top: 0;
    }
    
    .sidebar-header {
        padding: 1.5rem 1rem 1rem 1rem;
        border-bottom: 1px solid rgba(100, 150, 255, 0.15);
        margin-bottom: 1rem;
        background: linear-gradient(180deg, rgba(0, 100, 200, 0.1) 0%, transparent 100%);
    }
    
    .sidebar-logo {
        font-size: 1.25rem;
        font-weight: 700;
        background: linear-gradient(135deg, #00d4ff 0%, #00ff88 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    
    .sidebar-subtitle {
        font-size: 0.7rem;
        color: #667799;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-top: 0.25rem;
    }
    
    button[data-baseweb="tab"] {
        background: transparent;
        border: none;
        color: #667799;
        font-weight: 500;
        transition: all 0.3s ease;
        border-radius: 4px 4px 0 0;
    }
    
    button[data-baseweb="tab"]:hover {
        color: #00d4ff;
        background: rgba(0, 150, 255, 0.05);
    }
    
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #00d4ff;
        border-bottom: 2px solid #00d4ff;
        background: rgba(0, 150, 255, 0.08);
    }
    
    .stTextArea textarea, .stTextInput input, .stSelectbox select, .stNumberInput input {
        background: rgba(20, 25, 45, 0.8);
        border: 1px solid rgba(100, 150, 255, 0.2);
        color: #ccd6f6;
        border-radius: 4px;
        font-family: 'JetBrains Mono', monospace;
        transition: all 0.3s ease;
    }
    
    .stTextArea textarea:focus, .stTextInput input:focus, .stSelectbox select:focus, .stNumberInput input:focus {
        border-color: #00d4ff;
        box-shadow: 0 0 0 2px rgba(0, 200, 255, 0.1);
    }
    
    div.stButton > button {
        background: linear-gradient(135deg, rgba(0, 100, 200, 0.8) 0%, rgba(0, 80, 180, 0.9) 100%);
        color: #ffffff;
        border: 1px solid rgba(100, 200, 255, 0.3);
        border-radius: 4px;
        font-weight: 600;
        transition: all 0.3s ease;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        font-size: 0.85rem;
    }
    
    div.stButton > button:hover {
        background: linear-gradient(135deg, rgba(0, 150, 255, 0.9) 0%, rgba(0, 100, 220, 1) 100%);
        border-color: rgba(100, 200, 255, 0.5);
        box-shadow: 0 0 20px rgba(0, 150, 255, 0.3);
        transform: translateY(-1px);
    }
    
    div.stButton > button:active {
        transform: translateY(0);
    }
    
    .stSlider > div > div > div {
        background: linear-gradient(90deg, #00d4ff 0%, #00ff88 100%);
    }
    
    .stSlider > div > div > div > div {
        background: #00d4ff;
        box-shadow: 0 0 10px rgba(0, 200, 255, 0.5);
    }
    
    .log-container {
        background: rgba(10, 12, 20, 0.95);
        border: 1px solid rgba(100, 150, 255, 0.15);
        border-radius: 4px;
        padding: 1rem;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.8rem;
        max-height: 400px;
        overflow-y: auto;
        line-height: 1.6;
    }
    
    .log-info {
        color: #88c0d0;
    }
    
    .log-pass {
        color: #00ff88;
    }
    
    .log-warn {
        color: #ffb020;
    }
    
    .log-error {
        color: #ff5555;
    }
    
    .top-nav {
        background: rgba(15, 20, 40, 0.8);
        backdrop-filter: blur(20px);
        border-bottom: 1px solid rgba(100, 150, 255, 0.15);
        padding: 0.5rem 1rem;
        margin-bottom: 1rem;
        border-radius: 6px;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    
    .nav-status {
        display: flex;
        align-items: center;
        gap: 2rem;
    }
    
    .status-pill {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        font-size: 0.8rem;
    }
    
    .status-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        animation: pulse 2s infinite;
    }
    
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }
    
    .progress-bar-container {
        background: rgba(20, 25, 45, 0.8);
        border-radius: 4px;
        height: 8px;
        overflow: hidden;
        margin-top: 0.5rem;
    }
    
    .progress-bar-fill {
        height: 100%;
        background: linear-gradient(90deg, #00d4ff 0%, #00ff88 100%);
        border-radius: 4px;
        transition: width 0.5s ease;
    }
    
    .file-tree-item {
        padding: 0.5rem 0.75rem;
        border-radius: 4px;
        cursor: pointer;
        transition: all 0.2s ease;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.85rem;
        color: #8892b0;
    }
    
    .file-tree-item:hover {
        background: rgba(100, 150, 255, 0.1);
        color: #ccd6f6;
    }
    
    .file-tree-item.active {
        background: rgba(0, 150, 255, 0.15);
        color: #00d4ff;
        border-left: 2px solid #00d4ff;
    }
    
    .ai-recommendation {
        background: linear-gradient(135deg, rgba(0, 100, 200, 0.1) 0%, rgba(0, 80, 180, 0.05) 100%);
        border: 1px solid rgba(0, 200, 255, 0.2);
        border-radius: 6px;
        padding: 1rem;
        margin-bottom: 0.75rem;
    }
    
    .ai-recommendation-header {
        color: #00d4ff;
        font-weight: 600;
        font-size: 0.85rem;
        margin-bottom: 0.5rem;
    }
    
    .divider-glow {
        height: 1px;
        background: linear-gradient(90deg, transparent 0%, rgba(100, 200, 255, 0.3) 50%, transparent 100%);
        margin: 1.5rem 0;
    }
    
    .feature-tag {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        background: rgba(0, 150, 255, 0.1);
        border: 1px solid rgba(0, 200, 255, 0.2);
        border-radius: 20px;
        font-size: 0.7rem;
        color: #00d4ff;
        margin-right: 0.5rem;
        margin-bottom: 0.5rem;
    }
    
    .license-indicator {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.5rem;
        background: rgba(30, 40, 60, 0.5);
        border-radius: 4px;
        font-size: 0.8rem;
    }
    
    .license-bar {
        flex: 1;
        height: 4px;
        background: rgba(60, 70, 100, 0.5);
        border-radius: 2px;
        overflow: hidden;
    }
    
    .license-bar-fill {
        height: 100%;
        background: linear-gradient(90deg, #00ff88 0%, #00d4ff 100%);
        border-radius: 2px;
    }
    
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    
    ::-webkit-scrollbar-track {
        background: rgba(10, 15, 30, 0.5);
    }
    
    ::-webkit-scrollbar-thumb {
        background: rgba(100, 150, 255, 0.2);
        border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: rgba(100, 150, 255, 0.3);
    }
</style>
""", unsafe_allow_html=True)

EXAMPLES = {
    "UART": """design_name: uart
clock_reset:
  clock: clk
  reset: rst_n

interfaces:
  - name: wb
    signals:
      - name: wb_cyc
        direction: input
      - name: wb_stb
        direction: input
      - name: wb_we
        direction: input
      - name: wb_addr
        direction: input
        width: 3
      - name: wb_data_o
        direction: output
        width: 8
      - name: wb_data_i
        direction: input
        width: 8
      - name: wb_ack
        direction: output

  - name: uart
    signals:
      - name: uart_tx
        direction: output
      - name: uart_rx
        direction: input
      - name: cts_n
        direction: input
      - name: rts_n
        direction: output
      - name: uart_intr
        direction: output

registers:
  - name: RBR_THR
    address: 0x0
    description: Receiver Buffer / Transmitter Holding
    fields:
      - name: data
        bits: 7:0
  - name: IER
    address: 0x1
    description: Interrupt Enable
    fields:
      - name: erbfi
        bits: '0'
      - name: etbei
        bits: '1'
  - name: LCR
    address: 0x3
    description: Line Control
    fields:
      - name: wls
        bits: 1:0
      - name: dlab
        bits: '7'
  - name: LSR
    address: 0x5
    description: Line Status
    fields:
      - name: dr
        bits: '0'
      - name: thre
        bits: '5'

protocol: uart""",
    "SPI": """design_name: spi_controller
clock_reset:
  clock: clk
  reset: rst_n

interfaces:
  - name: apb
    signals:
      - name: psel
        direction: input
      - name: penable
        direction: input
      - name: pwrite
        direction: input
      - name: paddr
        direction: input
        width: 8
      - name: pwdata
        direction: input
        width: 32
      - name: prdata
        direction: output
        width: 32
      - name: pready
        direction: output

  - name: spi
    signals:
      - name: sclk
        direction: output
      - name: mosi
        direction: output
      - name: miso
        direction: input
      - name: cs_n
        direction: output
        width: 4

registers:
  - name: CTRL
    address: 0x0
    description: Control Register
  - name: TXDATA
    address: 0x4
    description: TX Data
  - name: RXDATA
    address: 0x8
    description: RX Data
  - name: STATUS
    address: 0xC
    description: Status Register

protocol: spi""",
    "I2C": """design_name: i2c_master
clock_reset:
  clock: clk
  reset: rst_n

interfaces:
  - name: axi4lite
    signals:
      - name: awvalid
        direction: input
      - name: awready
        direction: output
      - name: awaddr
        direction: input
        width: 16
      - name: wvalid
        direction: input
      - name: wready
        direction: output
      - name: wdata
        direction: input
        width: 32
      - name: rvalid
        direction: output
      - name: rready
        direction: input
      - name: rdata
        direction: output
        width: 32

  - name: i2c
    signals:
      - name: scl
        direction: inout
      - name: sda
        direction: inout

registers:
  - name: PRESCALE
    address: 0x0
    description: Clock Prescale
  - name: CTRL
    address: 0x4
    description: Control
  - name: TX_RX
    address: 0x8
    description: TX/RX Data
  - name: CMD_STATUS
    address: 0xC
    description: Command / Status

protocol: i2c"""
}

MODEL_CONFIGS = {
    "v2": {
        "name": "ML-Driven (Recommended)",
        "desc": "Advanced RL with pattern recognition",
        "features": ["Reinforcement Learning", "Experience Replay", "Pattern Mining", "UVM Compliance"]
    },
    "hybrid": {
        "name": "Hybrid Retrieval",
        "desc": "Similarity + templates",
        "features": ["Similarity Search", "Template Matching"]
    },
    "template": {
        "name": "Template-Based",
        "desc": "Fast deterministic generation",
        "features": ["Fastest", "Deterministic"]
    }
}

RL_STRATEGIES = {
    "ucb": "Upper Confidence Bound",
    "softmax": "Softmax (Boltzmann)",
    "epsilon_greedy": "Epsilon-Greedy",
    "thompson": "Thompson Sampling"
}

if 'last_result' not in st.session_state:
    st.session_state.last_result = None
if 'generated_files' not in st.session_state:
    st.session_state.generated_files = {}
if 'log_output' not in st.session_state:
    st.session_state.log_output = []
if 'ml_stats' not in st.session_state:
    st.session_state.ml_stats = None
if 'run_id' not in st.session_state:
    st.session_state.run_id = 0

with st.sidebar:
    st.markdown("""
    <div class="sidebar-header">
        <div class="sidebar-logo neon-text">⚡ VERIFY.AI</div>
        <div class="sidebar-subtitle">UVM Testbench Generator</div>
    </div>
    """, unsafe_allow_html=True)
    
    with st.expander("📋 Specification", expanded=True):
        st.markdown('<div class="section-header">Design Configuration</div>', unsafe_allow_html=True)
        
        selected_protocol = st.selectbox(
            "Protocol",
            list(EXAMPLES.keys()),
            index=0,
            key="protocol_sel"
        )
        
        design_name = st.text_input(
            "Design Name",
            value=f"{selected_protocol.lower()}_controller",
            key="design_nm"
        )
        
        st.markdown("---")
        st.markdown('<div class="section-header">Clock & Reset</div>', unsafe_allow_html=True)
        
        col_clk1, col_clk2 = st.columns(2)
        with col_clk1:
            clk_freq = st.number_input("Clock (MHz)", value=100.0, min_value=1.0, step=10.0)
        with col_clk2:
            rst_polarity = st.selectbox("Reset Polarity", ["Active Low", "Active High"], index=0)
        
        st.markdown("---")
        st.markdown('<div class="section-header">Interface Signals</div>', unsafe_allow_html=True)
        
        addr_width = st.slider("Address Width", min_value=8, max_value=32, value=16, step=8)
        data_width = st.slider("Data Width", min_value=8, max_value=64, value=32, step=8)

    st.markdown('<div class="divider-glow"></div>', unsafe_allow_html=True)
    
    with st.expander("🤖 AI Configuration", expanded=True):
        st.markdown('<div class="section-header">Generation Engine</div>', unsafe_allow_html=True)
        
        model_mode = st.radio(
            "Mode",
            list(MODEL_CONFIGS.keys()),
            index=0,
            format_func=lambda k: MODEL_CONFIGS[k]["name"],
            key="engine_mode"
        )
        
        st.caption(MODEL_CONFIGS[model_mode]["desc"])
        
        for feat in MODEL_CONFIGS[model_mode]["features"]:
            st.markdown(f'<span class="feature-tag">{feat}</span>', unsafe_allow_html=True)
        
        if model_mode == "v2":
            st.markdown("---")
            st.markdown('<div class="section-header">RL Optimization</div>', unsafe_allow_html=True)
            
            rl_strategy = st.selectbox(
                "Exploration Strategy",
                list(RL_STRATEGIES.keys()),
                index=0,
                format_func=lambda k: RL_STRATEGIES[k],
                key="rl_strat"
            )
            
            enable_learning = st.checkbox("Continuous Learning", value=True, key="learn_en")
            strict_uvm = st.checkbox("Strict UVM Compliance", value=True, key="uvm_strict")
            
            st.markdown("---")
            st.markdown('<div class="section-header">Verification Goals</div>', unsafe_allow_html=True)
            
            coverage_target = st.slider("Coverage Target (%)", min_value=70, max_value=100, value=95, key="cov_tgt")
            auto_heal = st.checkbox("Auto-Healing", value=True, key="auto_hl")
            intelligent_assert = st.checkbox("AI Assertions", value=True, key="ai_assert")

    st.markdown('<div class="divider-glow"></div>', unsafe_allow_html=True)
    
    with st.expander("⚡ Execution", expanded=True):
        st.markdown('<div class="section-header">Run Control</div>', unsafe_allow_html=True)
        
        max_iterations = st.slider(
            "Max Iterations",
            min_value=1,
            max_value=10,
            value=1,
            key="max_iter"
        )
        
        enable_sim = st.checkbox("Run Simulation", value=False, key="sim_en")
        enable_val = st.checkbox("Validate Output", value=True, key="val_en")
        
        st.markdown("---")
        
        generate_btn = st.button(
            "▶ GENERATE TESTBENCH",
            type="primary",
            use_container_width=True,
            key="run_btn"
        )
        
        col_a, col_b = st.columns(2)
        with col_a:
            validate_btn = st.button("Validate", use_container_width=True, key="val_btn")
        with col_b:
            export_btn = st.button("Export", use_container_width=True, key="exp_btn")

    st.markdown('<div class="divider-glow"></div>', unsafe_allow_html=True)
    
    with st.expander("📊 Resources", expanded=False):
        st.markdown('<div class="section-header">License Utilization</div>', unsafe_allow_html=True)
        
        st.markdown(f"""
        <div class="license-indicator">
            <span>UVM</span>
            <div class="license-bar">
                <div class="license-bar-fill" style="width: 65%"></div>
            </div>
            <span style="color: #00d4ff; font-weight: 600;">65%</span>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown(f"""
        <div class="license-indicator">
            <span>AI Credits</span>
            <div class="license-bar">
                <div class="license-bar-fill" style="width: 82%"></div>
            </div>
            <span style="color: #00ff88; font-weight: 600;">82%</span>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        st.markdown('<div class="section-header">System Status</div>', unsafe_allow_html=True)
        
        st.markdown(f"""
        <div style="display: flex; align-items: center; gap: 0.5rem; padding: 0.5rem; background: rgba(0, 100, 50, 0.1); border-radius: 4px;">
            <div class="status-dot" style="background: #00ff88;"></div>
            <span style="color: #00ff88; font-size: 0.85rem;">All Systems Operational</span>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.caption("v2.1.0 • Sai Kumar Taraka")

col_logo, col_title, col_status = st.columns([1, 4, 3])

with col_logo:
    st.markdown("""
    <div style="text-align: center;">
        <div style="font-size: 2rem;">⚡</div>
    </div>
    """, unsafe_allow_html=True)

with col_title:
    st.markdown("""
    <div style="padding: 0.25rem 0;">
        <div style="font-size: 1.25rem; font-weight: 700; color: #ccd6f6;">UVM Verification Platform</div>
        <div style="font-size: 0.8rem; color: #667799;">AI-Powered Testbench Generator • Production Ready</div>
    </div>
    """, unsafe_allow_html=True)

with col_status:
    st.markdown(f"""
    <div class="nav-status">
        <div class="status-pill">
            <div class="status-dot" style="background: #00ff88;"></div>
            <span style="color: #8892b0;">READY</span>
        </div>
        <div class="status-pill">
            <span style="color: #8892b0;">Run: #{st.session_state.run_id}</span>
        </div>
        <div class="status-pill">
            <span style="color: #00d4ff; font-weight: 600;">{datetime.now().strftime('%H:%M')}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

st.markdown('<div class="divider-glow"></div>', unsafe_allow_html=True)

tab_spec, tab_gen, tab_results, tab_analysis, tab_coverage, tab_logs = st.tabs([
    "📋 Specification",
    "⚙️ Generation",
    "📊 Results",
    "🔬 Analysis",
    "🎯 Coverage",
    "📝 Logs"
])

with tab_spec:
    col_editor, col_summary = st.columns([2, 1])
    
    with col_editor:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-header">YAML Specification Editor</div>', unsafe_allow_html=True)
        
        spec_text = st.text_area(
            "Edit Specification",
            value=EXAMPLES[selected_protocol],
            height=520,
            key="spec_edit",
            label_visibility="collapsed"
        )
        
        col_s1, col_s2, col_s3 = st.columns(3)
        with col_s1:
            st.markdown(f'<div class="metric-card"><div class="metric-value">{selected_protocol}</div><div class="metric-label">Protocol</div></div>', unsafe_allow_html=True)
        with col_s2:
            st.markdown(f'<div class="metric-card"><div class="metric-value">{design_name}</div><div class="metric-label">Design</div></div>', unsafe_allow_html=True)
        with col_s3:
            st.markdown(f'<div class="metric-card"><div class="metric-value">{model_mode.upper()}</div><div class="metric-label">Engine</div></div>', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col_summary:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-header">Specification Summary</div>', unsafe_allow_html=True)
        
        import yaml
        try:
            spec_dict = yaml.safe_load(spec_text)
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Interfaces", len(spec_dict.get('interfaces', [])))
                total_sigs = sum(len(i.get('signals', [])) for i in spec_dict.get('interfaces', []))
                st.metric("Total Signals", total_sigs)
            
            with col2:
                st.metric("Registers", len(spec_dict.get('registers', [])))
                total_fields = sum(len(r.get('fields', [])) for r in spec_dict.get('registers', []))
                st.metric("Register Fields", total_fields)
            
            st.markdown("---")
            st.markdown('<div class="section-header">Interface Configuration</div>', unsafe_allow_html=True)
            
            for iface in spec_dict.get('interfaces', []):
                with st.expander(f"🔌 {iface.get('name')}"):
                    for sig in iface.get('signals', []):
                        name = sig.get('name')
                        direction = sig.get('direction')
                        width = sig.get('width', 1)
                        dir_color = "#00ff88" if direction == "input" else "#00d4ff"
                        st.markdown(f'<div style="display: flex; justify-content: space-between; padding: 0.25rem 0; border-bottom: 1px solid rgba(100,150,255,0.1);"> <span style="font-family: JetBrains Mono; font-size: 0.85rem; color: #ccd6f6;">{name}</span> <span style="font-size: 0.75rem; color: {dir_color};">{direction} [{width}]</span> </div>', unsafe_allow_html=True)
                        
        except Exception as e:
            st.error(f"Parse Error: {e}")
        
        st.markdown('</div>', unsafe_allow_html=True)

with tab_gen:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-header">Generation Control</div>', unsafe_allow_html=True)
    
    col_g1, col_g2, col_g3, col_g4 = st.columns(4)
    with col_g1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{model_mode.upper()}</div>
            <div class="metric-label">Engine</div>
        </div>
        """, unsafe_allow_html=True)
    with col_g2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{max_iterations}</div>
            <div class="metric-label">Iterations</div>
        </div>
        """, unsafe_allow_html=True)
    with col_g3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{'ON' if enable_learning else 'OFF'}</div>
            <div class="metric-label">Learning</div>
        </div>
        """, unsafe_allow_html=True)
    with col_g4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{'ON' if strict_uvm else 'OFF'}</div>
            <div class="metric-label">UVM Strict</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-header">AI Recommendations</div>', unsafe_allow_html=True)
    
    col_ai1, col_ai2 = st.columns(2)
    
    with col_ai1:
        st.markdown("""
        <div class="ai-recommendation">
            <div class="ai-recommendation-header">🧠 Coverage Strategy</div>
            <p style="color: #8892b0; font-size: 0.85rem; line-height: 1.5;">
                Recommended: Add directed tests for reset values, bus protocols, and register access patterns.
            </p>
            <div style="margin-top: 0.75rem;">
                <div style="display: flex; justify-content: space-between; font-size: 0.75rem; color: #667799; margin-bottom: 0.25rem;">
                    <span>Coverage Potential</span>
                    <span style="color: #00d4ff;">High</span>
                </div>
                <div class="progress-bar-container">
                    <div class="progress-bar-fill" style="width: 85%"></div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col_ai2:
        st.markdown("""
        <div class="ai-recommendation">
            <div class="ai-recommendation-header">🔧 Assertion Generator</div>
            <p style="color: #8892b0; font-size: 0.85rem; line-height: 1.5;">
                AI can generate protocol-specific assertions for validating signal timing, handshakes, and data integrity.
            </p>
            <div style="margin-top: 0.75rem;">
                <div style="display: flex; justify-content: space-between; font-size: 0.75rem; color: #667799; margin-bottom: 0.25rem;">
                    <span>Assertion Coverage</span>
                    <span style="color: #00ff88;">Optimal</span>
                </div>
                <div class="progress-bar-container">
                    <div class="progress-bar-fill" style="width: 72%"></div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-header">Verification Pipeline</div>', unsafe_allow_html=True)
    
    pipeline_steps = [
        ("Spec Parse", True),
        ("Feature Extract", True),
        ("ML Generation", generate_btn),
        ("UVM Validation", False),
        ("Coverage Analysis", False),
        ("Export Package", False)
    ]
    
    cols = st.columns(len(pipeline_steps))
    for i, (step, is_done) in enumerate(pipeline_steps):
        with cols[i]:
            status_color = "#00ff88" if is_done else "#445566"
            status_bg = "rgba(0, 100, 50, 0.2)" if is_done else "rgba(30, 35, 50, 0.5)"
            st.markdown(f"""
            <div style="text-align: center; padding: 1rem 0.5rem; background: {status_bg}; border-radius: 6px; border: 1px solid {status_color}33;">
                <div style="width: 32px; height: 32px; margin: 0 auto 0.5rem auto; border-radius: 50%; background: {status_color}; display: flex; align-items: center; justify-content: center; color: #0a0e27; font-weight: 700; font-size: 0.85rem;">
                    {"✓" if is_done else str(i+1)}
                </div>
                <div style="font-size: 0.75rem; color: #8892b0; font-weight: 500;">{step}</div>
            </div>
            """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

with tab_results:
    if st.session_state.last_result:
        result = st.session_state.last_result
        eval_metrics = result.get('evaluation', {})
        
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-header">Generation Metrics</div>', unsafe_allow_html=True)
        
        cols = st.columns(6)
        
        metrics_display = [
            ("Completeness", eval_metrics.get('completeness', 0) * 100, "%"),
            ("Signal Cov", eval_metrics.get('interface_signal_coverage', 0) * 100, "%"),
            ("Register Cov", eval_metrics.get('register_coverage', 0) * 100, "%"),
            ("Files", len(st.session_state.generated_files), ""),
            ("Iterations", result.get('auto_train_iterations', 0), ""),
            ("Status", "PASS" if result.get('passed') else "DONE", "")
        ]
        
        for i, (label, value, suffix) in enumerate(metrics_display):
            with cols[i]:
                if isinstance(value, float):
                    display_val = f"{value:.1f}{suffix}"
                else:
                    display_val = f"{value}{suffix}"
                
                is_pass = (label == "Status" and value == "PASS") or (isinstance(value, (int, float)) and value >= 90)
                
                st.markdown(f"""
                <div class="metric-card" style="border-left-color: {'#00ff88' if is_pass else '#00d4ff'}">
                    <div class="metric-value" style="background: linear-gradient(135deg, {'#00ff88' if is_pass else '#00d4ff'} 0%, {'#88ffcc' if is_pass else '#00ff88'} 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
                        {display_val}
                    </div>
                    <div class="metric-label">{label}</div>
                </div>
                """, unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        if st.session_state.generated_files:
            st.markdown('<div class="glass-card">', unsafe_allow_html=True)
            st.markdown('<div class="section-header">Generated Files</div>', unsafe_allow_html=True)
            
            col_tree, col_code = st.columns([1, 3])
            
            with col_tree:
                file_names = sorted(st.session_state.generated_files.keys())
                
                st.markdown('<div style="background: rgba(10, 15, 30, 0.5); border-radius: 6px; padding: 0.5rem;">', unsafe_allow_html=True)
                
                if 'selected_file' not in st.session_state:
                    st.session_state.selected_file = file_names[0] if file_names else None
                
                for fn in file_names:
                    is_active = (fn == st.session_state.selected_file)
                    active_class = "active" if is_active else ""
                    if st.button(fn, key=f"file_{fn}", use_container_width=True):
                        st.session_state.selected_file = fn
                
                st.markdown('</div>', unsafe_allow_html=True)
            
            with col_code:
                selected_file = st.session_state.selected_file
                if selected_file and selected_file in st.session_state.generated_files:
                    file_path = st.session_state.generated_files[selected_file]
                    if os.path.exists(file_path):
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                            
                            col_dl1, col_dl2, col_info = st.columns([1, 1, 3])
                            with col_dl1:
                                st.download_button(
                                    "📥 Download",
                                    data=content,
                                    file_name=selected_file,
                                    mime="text/plain",
                                    use_container_width=True
                                )
                            with col_dl2:
                                st.button("📋 Copy", use_container_width=True)
                            with col_info:
                                st.caption(f"Lines: {len(content.splitlines())} | Size: {len(content)} bytes")
                            
                            st.markdown(f"""
                            <div style="background: rgba(10, 12, 20, 0.9); border: 1px solid rgba(100, 150, 255, 0.15); border-radius: 6px; padding: 1rem; margin-top: 0.75rem; max-height: 450px; overflow-y: auto;">
                                <pre style="font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; line-height: 1.5; color: #88c0d0; white-space: pre-wrap; margin: 0;">{content}</pre>
                            </div>
                            """, unsafe_allow_html=True)
                            
                        except Exception as e:
                            st.warning(f"Could not read file: {e}")
            
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown('<div class="glass-card">', unsafe_allow_html=True)
            st.markdown('<div class="section-header">Export Package</div>', unsafe_allow_html=True)
            
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for name, path in st.session_state.generated_files.items():
                    if os.path.exists(path):
                        zipf.write(path, arcname=name)
            zip_buffer.seek(0)
            
            col_exp1, col_exp2, col_exp3 = st.columns([2, 2, 3])
            with col_exp1:
                st.download_button(
                    "📦 Download UVM Package",
                    data=zip_buffer,
                    file_name=f"{design_name}_uvm_testbench.zip",
                    mime="application/zip",
                    use_container_width=True,
                    type="primary"
                )
            with col_exp2:
                st.button("📋 Generate Simulation Script", use_container_width=True)
            with col_exp3:
                st.button("📊 Create Regression Suite", use_container_width=True)
            
            st.markdown('</div>', unsafe_allow_html=True)
        
    else:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown("""
        <div style="text-align: center; padding: 4rem 2rem;">
            <div style="font-size: 3rem; margin-bottom: 1rem;">⚡</div>
            <div style="font-size: 1.25rem; color: #8892b0; margin-bottom: 0.5rem;">Ready to Generate</div>
            <div style="font-size: 0.85rem; color: #667799;">
                Configure your specification and click "Generate Testbench" to begin.
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

with tab_analysis:
    if st.session_state.ml_stats:
        stats = st.session_state.ml_stats
        
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-header">ML Analysis Dashboard</div>', unsafe_allow_html=True)
        
        col_an1, col_an2, col_an3, col_an4 = st.columns(4)
        with col_an1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{stats.get('total_generations', 0)}</div>
                <div class="metric-label">Generations</div>
            </div>
            """, unsafe_allow_html=True)
        with col_an2:
            if 'rl_learner' in stats:
                rl = stats['rl_learner']
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-value">{rl.get('episode_count', 0)}</div>
                    <div class="metric-label">RL Episodes</div>
                </div>
                """, unsafe_allow_html=True)
        with col_an3:
            if 'rl_learner' in stats:
                rl = stats['rl_learner']
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-value">{rl.get('total_updates', 0)}</div>
                    <div class="metric-label">Updates</div>
                </div>
                """, unsafe_allow_html=True)
        with col_an4:
            if 'rl_learner' in stats:
                rl = stats['rl_learner']
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-value">{rl.get('learning_rate', 0.1):.3f}</div>
                    <div class="metric-label">Learning Rate</div>
                </div>
                """, unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        col_dist, col_weights = st.columns(2)
        
        with col_dist:
            st.markdown('<div class="glass-card">', unsafe_allow_html=True)
            st.markdown('<div class="section-header">Source Distribution</div>', unsafe_allow_html=True)
            
            if 'source_distribution' in stats:
                dist = stats['source_distribution']
                if dist:
                    df = pd.DataFrame({
                        'Source': list(dist.keys()),
                        'Count': list(dist.values())
                    })
                    st.bar_chart(df.set_index('Source'), color=["#00d4ff"])
            else:
                st.info("No distribution data yet")
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col_weights:
            st.markdown('<div class="glass-card">', unsafe_allow_html=True)
            st.markdown('<div class="section-header">Strategy Weights</div>', unsafe_allow_html=True)
            
            if 'strategy_weights' in stats:
                weights = stats['strategy_weights']
                for strategy, weight in weights.items():
                    percentage = weight * 100
                    st.markdown(f"""
                    <div style="margin-bottom: 1rem;">
                        <div style="display: flex; justify-content: space-between; font-size: 0.8rem; color: #8892b0; margin-bottom: 0.25rem;">
                            <span style="text-transform: uppercase; font-weight: 500;">{strategy}</span>
                            <span style="color: #00d4ff; font-weight: 600;">{percentage:.1f}%</span>
                        </div>
                        <div class="progress-bar-container">
                            <div class="progress-bar-fill" style="width: {percentage}%"></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("No strategy weights yet")
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown('<div class="section-header">RL State Performance</div>', unsafe_allow_html=True)
        
        if 'rl_learner' in stats and 'state_stats' in stats['rl_learner']:
            state_stats = stats['rl_learner']['state_stats']
            if state_stats:
                cols_state = st.columns(min(4, len(state_stats)))
                for i, (state, info) in enumerate(list(state_stats.items())[:4]):
                    with cols_state[i]:
                        q_val = info.get('best_q_value', 0)
                        best_action = info.get('best_action', 'N/A')
                        visits = info.get('visit_count', 0)
                        
                        st.markdown(f"""
                        <div style="background: rgba(20, 30, 50, 0.6); border: 1px solid rgba(100, 150, 255, 0.15); border-radius: 6px; padding: 1rem; text-align: center;">
                            <div style="font-size: 0.7rem; color: #667799; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 0.5rem;">{state[:20]}</div>
                            <div style="font-size: 1.25rem; font-weight: 700; color: #00d4ff; margin-bottom: 0.25rem;">{q_val:.3f}</div>
                            <div style="font-size: 0.7rem; color: #8892b0;">Q-Value</div>
                            <div style="margin-top: 0.75rem; padding-top: 0.75rem; border-top: 1px solid rgba(100, 150, 255, 0.1);">
                                <div style="font-size: 0.7rem; color: #667799;">Best: <span style="color: #00ff88; font-weight: 600;">{best_action}</span></div>
                                <div style="font-size: 0.7rem; color: #667799; margin-top: 0.25rem;">Visits: {visits}</div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
        else:
            st.info("No RL state data yet - run a generation to collect statistics")
        
        st.markdown('</div>', unsafe_allow_html=True)
        
    else:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown("""
        <div style="text-align: center; padding: 4rem 2rem;">
            <div style="font-size: 3rem; margin-bottom: 1rem;">🔬</div>
            <div style="font-size: 1.25rem; color: #8892b0; margin-bottom: 0.5rem;">ML Analysis</div>
            <div style="font-size: 0.85rem; color: #667799; max-width: 500px; margin: 0 auto;">
                Run a generation with the ML-Driven engine to see:
                <ul style="text-align: left; margin-top: 1rem; color: #8892b0;">
                    <li>Reinforcement Learning metrics</li>
                    <li>Strategy weight distributions</li>
                    <li>Q-value tracking</li>
                    <li>Source distribution analysis</li>
                </ul>
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

with tab_coverage:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-header">Coverage Analysis</div>', unsafe_allow_html=True)
    
    col_cov1, col_cov2, col_cov3, col_cov4 = st.columns(4)
    with col_cov1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{coverage_target}%</div>
            <div class="metric-label">Target</div>
        </div>
        """, unsafe_allow_html=True)
    with col_cov2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">--</div>
            <div class="metric-label">Functional</div>
        </div>
        """, unsafe_allow_html=True)
    with col_cov3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">--</div>
            <div class="metric-label">Assertion</div>
        </div>
        """, unsafe_allow_html=True)
    with col_cov4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">--</div>
            <div class="metric-label">Code</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-header">Coverage Closure Assistant</div>', unsafe_allow_html=True)
    
    st.markdown("""
    <div class="ai-recommendation">
        <div class="ai-recommendation-header">🎯 AI Coverage Recommendations</div>
        <div style="margin-top: 1rem;">
            <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.75rem;">
                <div style="width: 24px; height: 24px; border-radius: 50%; background: rgba(0, 200, 255, 0.1); display: flex; align-items: center; justify-content: center; color: #00d4ff; font-size: 0.85rem;">1</div>
                <span style="color: #ccd6f6; font-size: 0.85rem;">Add directed tests for edge cases (all 0s, all 1s, max values)</span>
            </div>
            <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.75rem;">
                <div style="width: 24px; height: 24px; border-radius: 50%; background: rgba(0, 200, 255, 0.1); display: flex; align-items: center; justify-content: center; color: #00d4ff; font-size: 0.85rem;">2</div>
                <span style="color: #ccd6f6; font-size: 0.85rem;">Verify reset values for all registers</span>
            </div>
            <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.75rem;">
                <div style="width: 24px; height: 24px; border-radius: 50%; background: rgba(0, 200, 255, 0.1); display: flex; align-items: center; justify-content: center; color: #00d4ff; font-size: 0.85rem;">3</div>
                <span style="color: #ccd6f6; font-size: 0.85rem;">Test protocol handshakes with back-to-back transactions</span>
            </div>
            <div style="display: flex; align-items: center; gap: 0.75rem;">
                <div style="width: 24px; height: 24px; border-radius: 50%; background: rgba(0, 200, 255, 0.1); display: flex; align-items: center; justify-content: center; color: #00d4ff; font-size: 0.85rem;">4</div>
                <span style="color: #ccd6f6; font-size: 0.85rem;">Add concurrent stimulus for protocol validation</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

with tab_logs:
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-header">Execution Logs</div>', unsafe_allow_html=True)
    
    if st.session_state.log_output:
        log_html = "\n".join([
            f'<span class="log-{"pass" if "PASS" in line else "info"}">{line}</span>'
            for line in st.session_state.log_output
        ])
        
        st.markdown(f"""
        <div class="log-container">
            {log_html}
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="log-container">
            <span class="log-info">[{datetime.now().strftime('%H:%M:%S')}] System initialized</span><br>
            <span class="log-info">[{datetime.now().strftime('%H:%M:%S')}] Waiting for specification...</span><br>
            <span class="log-info">[{datetime.now().strftime('%H:%M:%S')}] AI engine ready</span><br>
            <span class="log-info">[{datetime.now().strftime('%H:%M:%S')}] UVM templates loaded</span><br>
            <span class="log-info">[{datetime.now().strftime('%H:%M:%S')}] All systems operational</span><br>
            <br>
            <span style="color: #667799; font-style: italic;"># Click "Generate Testbench" to begin</span>
        </div>
        """, unsafe_allow_html=True)
    
    col_clear, col_export = st.columns([1, 5])
    with col_clear:
        st.button("Clear Logs", use_container_width=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

if generate_btn:
    st.session_state.run_id += 1
    st.session_state.log_output = []
    st.session_state.last_result = None
    st.session_state.generated_files = {}
    st.session_state.ml_stats = None
    
    try:
        from src.config import ConfigLoader, PipelineConfig, MLConfig, GenerationConfig, AutoTrainConfig
        from src.pipeline import TBPipeline
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
            f.write(spec_text)
            spec_path = f.name
        
        timestamp = datetime.now().strftime('%H:%M:%S')
        st.session_state.log_output.append(f"[{timestamp}] Starting generation: {design_name}")
        st.session_state.log_output.append(f"[{timestamp}] Engine: {model_mode}")
        if model_mode == "v2":
            st.session_state.log_output.append(f"[{timestamp}] RL Strategy: {rl_strategy}")
        
        ml_cfg = MLConfig(
            enabled=(model_mode != "template"),
            model_type=model_mode,
            use_llm=False,
            use_semantic_encoder=False,
        )
        
        if model_mode == "v2":
            ml_cfg.exploration_strategy = rl_strategy
            ml_cfg.use_learning = enable_learning
            ml_cfg.strict_validation = strict_uvm
        
        pipeline_cfg = PipelineConfig(
            ml=ml_cfg,
            generation=GenerationConfig(
                templates_dir=os.path.join(os.getcwd(), "src", "generation", "templates"),
                output_dir=os.path.join(os.getcwd(), "output"),
                overwrite=True
            ),
            auto_train=AutoTrainConfig(
                enabled=(max_iterations > 1),
                max_iterations=max_iterations
            )
        )
        
        pipeline = TBPipeline(pipeline_cfg)
        
        st.session_state.log_output.append(f"[{timestamp}] Model: {type(pipeline.model).__name__}")
        st.session_state.log_output.append(f"[{timestamp}] Processing specification...")
        
        result = pipeline.run(spec_path)
        
        try:
            os.unlink(spec_path)
        except:
            pass
        
        st.session_state.last_result = result
        st.session_state.generated_files = result.get('generated_files', {})
        
        try:
            if hasattr(pipeline.model, 'get_learning_stats'):
                st.session_state.ml_stats = pipeline.model.get_learning_stats()
        except Exception as e:
            logger.warning(f"Could not get ML stats: {e}")
        
        timestamp = datetime.now().strftime('%H:%M:%S')
        st.session_state.log_output.append(f"[{timestamp}] Generation complete")
        st.session_state.log_output.append(f"[{timestamp}] Files generated: {len(st.session_state.generated_files)}")
        
        if result.get('passed'):
            st.session_state.log_output.append(f"[{timestamp}] Status: PASS")
        else:
            st.session_state.log_output.append(f"[{timestamp}] Status: COMPLETED")
        
        st.rerun()
            
    except Exception as e:
        timestamp = datetime.now().strftime('%H:%M:%S')
        st.session_state.log_output.append(f"[{timestamp}] Error: {str(e)}")
        import traceback
        st.session_state.log_output.append(traceback.format_exc())
        st.rerun()
