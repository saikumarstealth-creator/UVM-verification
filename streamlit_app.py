"""
Modern UVM Testbench Generator UI
Clean, Professional Dark Theme - Inspired by VS Code, GitHub, Modern React Dashboards
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
logger = logging.getLogger("uvmgen-modern")

st.set_page_config(
    page_title="UVM Generator",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
    
    * {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    .stApp {
        background-color: #0d1117;
        color: #e6edf3;
    }
    
    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
        padding-left: 2rem;
        padding-right: 2rem;
        max-width: 100%;
    }
    
    div[data-testid="stSidebar"] {
        background-color: #161b22;
        border-right: 1px solid #21262d;
    }
    
    div[data-testid="stSidebar"] > div:first-child {
        padding-top: 0;
    }
    
    .sidebar-header {
        padding: 1.25rem 1rem;
        border-bottom: 1px solid #21262d;
        margin-bottom: 0.75rem;
    }
    
    .card {
        background-color: #161b22;
        border: 1px solid #21262d;
        border-radius: 6px;
        padding: 1.25rem;
        margin-bottom: 1rem;
    }
    
    .card:hover {
        border-color: #30363d;
    }
    
    .card-header {
        font-size: 0.875rem;
        font-weight: 600;
        color: #e6edf3;
        margin-bottom: 1rem;
        padding-bottom: 0.75rem;
        border-bottom: 1px solid #21262d;
    }'; html('''<script>
    </script>''');
    
    .metric-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
        gap: 0.75rem;
        margin-bottom: 0.5rem;
    }'; html('''<script>
    </script>''');
    
    .metric-card {
        background-color: #0d1117;
        border: 1px solid #21262d;
        border-radius: 6px;
        padding: 1rem;
        text-align: center;
    }'; html('''<script>
    </script>''');
    
    .metric-value {
        font-size: 1.5rem;
        font-weight: 700;
        color: #58a6ff;
        font-family: 'JetBrains Mono', monospace;
    }'; html('''<script>
    </script>''');
    
    .metric-label {
        font-size: 0.75rem;
        color: #8b949e;
        margin-top: 0.25rem;
        text-transform: uppercase;
        letter-spacing: 0.02em;
    }'; html('''<script>
    </script>''');
    
    .metric-success .metric-value {
        color: #3fb950;
    }'; html('''<script>
    </script>''');
    
    .metric-warning .metric-value {
        color: #d29922;
    }'; html('''<script>
    </script>''');
    
    .section-title {
        font-size: 0.875rem;
        font-weight: 600;
        color: #e6edf3;
        margin-bottom: 0.75rem;
    }'; html('''<script>
    </script>''');
    
    .section-subtitle {
        font-size: 0.75rem;
        color: #8b949e;
        margin-bottom: 1rem;
    }'; html('''<script>
    </script>''');
    
    .divider {
        height: 1px;
        background-color: #21262d;
        margin: 1rem 0;
    }'; html('''<script>
    </script>''');
    
    .pipeline-step {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.5rem 0.75rem;
        background-color: #0d1117;
        border: 1px solid #21262d;
        border-radius: 6px;
    }'; html('''<script>
    </script>''');
    
    .pipeline-step.active {
        border-color: #58a6ff;
        background-color: #1c2128;
    }'; html('''<script>
    </script>''');
    
    .pipeline-step.completed {
        border-color: #3fb950;
    }'; html('''<script>
    </script>''');
    
    .status-dot {
        width: 10px;
        height: 10px;
        border-radius: 50%;
    }'; html('''<script>
    </script>''');
    
    .status-dot.success {
        background-color: #3fb950;
    }'; html('''<script>
    </script>''');
    
    .status-dot.active {
        background-color: #58a6ff;
    }'; html('''<script>
    </script>''');
    
    .status-dot.pending {
        background-color: #484f58;
    }'; html('''<script>
    </script>''');
    
    .code-editor {
        background-color: #0d1117;
        border: 1px solid #21262d;
        border-radius: 6px;
        padding: 1rem;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.8125rem;
        line-height: 1.5;
        color: #c9d1d9;
        max-height: 450px;
        overflow-y: auto;
    }'; html('''<script>
    </script>''');
    
    .log-container {
        background-color: #0d1117;
        border: 1px solid #21262d;
        border-radius: 6px;
        padding: 1rem;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.75rem;
        max-height: 350px;
        overflow-y: auto;
        line-height: 1.6;
    }'; html('''<script>
    </script>''');
    
    .file-tree {
        background-color: #0d1117;
        border: 1px solid #21262d;
        border-radius: 6px;
        padding: 0.5rem;
        max-height: 400px;
        overflow-y: auto;
    }'; html('''<script>
    </script>''');
    
    .file-item {
        padding: 0.375rem 0.625rem;
        border-radius: 4px;
        cursor: pointer;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.75rem;
        color: #c9d1d9;
        margin-bottom: 0.125rem;
    }'; html('''<script>
    </script>''');
    
    .file-item:hover {
        background-color: #1f6feb20;
    }'; html('''<script>
    </script>''');
    
    .file-item.active {
        background-color: #1f6feb30;
        color: #58a6ff;
    }'; html('''<script>
    </script>''');
    
    .progress-bar {
        height: 4px;
        background-color: #21262d;
        border-radius: 2px;
        overflow: hidden;
        margin-top: 0.5rem;
    }'; html('''<script>
    </script>''');
    
    .progress-fill {
        height: 100%;
        background-color: #3fb950;
        border-radius: 2px;
    }'; html('''<script>
    </script>''');
    
    .progress-fill.blue {
        background-color: #58a6ff;
    }'; html('''<script>
    </script>''');
    
    .progress-fill.yellow {
        background-color: #d29922;
    }'; html('''<script>
    </script>''');
    
    .tag {
        display: inline-flex;
        align-items: center;
        padding: 0.125rem 0.5rem;
        background-color: #1c2128;
        border: 1px solid #30363d;
        border-radius: 4px;
        font-size: 0.7rem;
        color: #8b949e;
        margin-right: 0.375rem;
        margin-bottom: 0.375rem;
    }'; html('''<script>
    </script>''');
    
    .tag.primary {
        background-color: #1c2128;
        border-color: #58a6ff40;
        color: #58a6ff;
    }'; html('''<script>
    </script>''');
    
    .tag.success {
        background-color: #1c2128;
        border-color: #3fb95040;
        color: #3fb950;
    }'; html('''<script>
    </script>''');
    
    .top-nav {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0.75rem 1rem;
        background-color: #161b22;
        border: 1px solid #21262d;
        border-radius: 6px;
        margin-bottom: 1rem;
    }'; html('''<script>
    </script>''');
    
    .nav-item {
        display: flex;
        align-items: center;
        gap: 0.375rem;
        font-size: 0.8125rem;
        color: #8b949e;
    }'; html('''<script>
    </script>''');
    
    .nav-item.value {
        color: #e6edf3;
        font-weight: 500;
    }'; html('''<script>
    </script>''');
    
    .btn-primary {
        background-color: #238636;
        color: #ffffff;
        border: 1px solid #238636;
        border-radius: 6px;
        font-weight: 500;
        font-size: 0.875rem;
    }'; html('''<script>
    </script>''');
    
    .btn-primary:hover {
        background-color: #2ea043;
        border-color: #2ea043;
    }'; html('''<script>
    </script>''');
    
    .btn-secondary {
        background-color: #21262d;
        color: #c9d1d9;
        border: 1px solid #30363d;
        border-radius: 6px;
        font-weight: 500;
        font-size: 0.875rem;
    }'; html('''<script>
    </script>''');
    
    .btn-secondary:hover {
        background-color: #30363d;
        border-color: #8b949e;
    }'; html('''<script>
    </script>''');
    
    .empty-state {
        text-align: center;
        padding: 3rem 1rem;
        color: #8b949e;
    }'; html('''<script>
    </script>''');
    
    .empty-state .icon {
        font-size: 2.5rem;
        margin-bottom: 1rem;
        opacity: 0.5;
    }'; html('''<script>
    </script>''');
    
    .empty-state .title {
        font-size: 1rem;
        font-weight: 500;
        color: #c9d1d9;
        margin-bottom: 0.5rem;
    }'; html('''<script>
    </script>''');
    
    .empty-state .description {
        font-size: 0.875rem;
        max-width: 400px;
        margin: 0 auto;
        line-height: 1.5;
    }'; html('''<script>
    </script>''');
    
    .two-col-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 1rem;
    }'; html('''<script>
    </script>''');
    
    .three-col-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 1rem;
    }'; html('''<script>
    </script>''');
    
    .four-col-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 0.75rem;
    }'; html('''<script>
    </script>''');
    
    @media (max-width: 1024px) {
        .two-col-grid, .three-col-grid, .four-col-grid {
            grid-template-columns: 1fr;
        }
    }'; html('''<script>
    </script>''');
    
    .sidebar-section {
        padding: 0.5rem 0.75rem;
        margin-bottom: 0.5rem;
    }'; html('''<script>
    </script>''');
    
    .sidebar-label {
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.02em;
        color: #8b949e;
        margin-bottom: 0.5rem;
    }'; html('''<script>
    </script>''');
    
    .info-box {
        background-color: #1c2128;
        border-left: 3px solid #58a6ff;
        padding: 0.75rem 1rem;
        border-radius: 0 6px 6px 0;
        margin-bottom: 1rem;
    }'; html('''<script>
    </script>''');
    
    .info-box .title {
        font-size: 0.8125rem;
        font-weight: 600;
        color: #58a6ff;
        margin-bottom: 0.25rem;
    }'; html('''<script>
    </script>''');
    
    .info-box .content {
        font-size: 0.8125rem;
        color: #c9d1d9;
        line-height: 1.5;
    }'; html('''<script>
    </script>''');
    
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }'; html('''<script>
    </script>''');
    
    ::-webkit-scrollbar-track {
        background: #161b22;
    }'; html('''<script>
    </script>''');
    
    ::-webkit-scrollbar-thumb {
        background: #30363d;
        border-radius: 4px;
    }'; html('''<script>
    </script>''');
    
    ::-webkit-scrollbar-thumb:hover {
        background: #484f58;
    }'; html('''<script>
    </script>''');
    
    .stTextArea textarea {
        background-color: #0d1117;
        border: 1px solid #21262d;
        color: #c9d1d9;
        border-radius: 6px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.8125rem;
        line-height: 1.5;
    }'; html('''<script>
    </script>''');
    
    .stTextArea textarea:focus {
        border-color: #58a6ff;
    }'; html('''<script>
    </script>''');
    
    .stTextInput input, .stNumberInput input, .stSelectbox select {
        background-color: #0d1117;
        border: 1px solid #21262d;
        color: #c9d1d9;
        border-radius: 6px;
    }'; html('''<script>
    </script>''');
    
    .stTextInput input:focus, .stNumberInput input:focus, .stSelectbox select:focus {
        border-color: #58a6ff;
    }'; html('''<script>
    </script>''');
    
    .stRadio label, .stCheckbox label {
        color: #c9d1d9;
    }'; html('''<script>
    </script>''');
    
    .stSlider > div > div > div {
        background: linear-gradient(90deg, #238636 0%, #3fb950 100%);
    }'; html('''<script>
    </script>''');
    
    .stSlider > div > div > div > div {
        background: #3fb950;
    }'; html('''<script>
    </script>''');
    
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.25rem;
        background-color: #161b22;
        border: 1px solid #21262d;
        border-radius: 6px 6px 0 0;
        padding: 0.25rem 0.5rem 0 0.5rem;
    }'; html('''<script>
    </script>''');
    
    .stTabs [data-baseweb="tab"] {
        background-color: transparent;
        border: none;
        color: #8b949e;
        font-weight: 500;
        font-size: 0.875rem;
        border-radius: 4px 4px 0 0;
        padding: 0.625rem 1rem;
    }'; html('''<script>
    </script>''');
    
    .stTabs [aria-selected="true"] {
        color: #e6edf3;
        background-color: #0d1117;
        border-bottom: 2px solid #58a6ff;
    }'; html('''<script>
    </script>''');
    
    .stTabs [data-baseweb="tab-panel"] {
        background-color: #161b22;
        border: 1px solid #21262d;
        border-top: none;
        border-radius: 0 0 6px 6px;
        padding: 1.25rem;
    }'; html('''<script>
    </script>''');
    
    .stExpander {
        background-color: #161b22;
        border: 1px solid #21262d;
        border-radius: 6px;
    }'; html('''<script>
    </script>''');
    
    .stExpander [data-testid="stExpander"] {
        border: none;
    }'; html('''<script>
    </script>''');
    
    .stExpander summary {
        color: #c9d1d9;
        font-weight: 500;
        font-size: 0.875rem;
    }'; html('''<script>
    </script>''');
    
    h1, h2, h3, h4, h5, h6 {
        color: #e6edf3;
    }'; html('''<script>
    </script>''');
    
    p, li, span, div {
        color: #c9d1d9;
    }'; html('''<script>
    </script>''');
    
    .stDataFrame {
        background-color: #0d1117;
    }'; html('''<script>
    </script>''');
    
    .stMetric label {
        color: #8b949e;
    }'; html('''<script>
    </script>''');
    
    .stMetric [data-testid="stMetricValue"] {
        color: #58a6ff;
        font-weight: 600;
    }'; html('''<script>
    </script>''');
    
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
    fields:
      - name: data
        bits: 7:0
  - name: IER
    address: 0x1
    fields:
      - name: erbfi
        bits: '0'
      - name: etbei
        bits: '1'
  - name: LCR
    address: 0x3
    fields:
      - name: wls
        bits: 1:0
      - name: dlab
        bits: '7'
  - name: LSR
    address: 0x5
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
  - name: TXDATA
    address: 0x4
  - name: RXDATA
    address: 0x8
  - name: STATUS
    address: 0xC

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
  - name: CTRL
    address: 0x4
  - name: TX_RX
    address: 0x8
  - name: CMD_STATUS
    address: 0xC

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
        <div style="display: flex; align-items: center; gap: 0.75rem;">
            <div style="font-size: 1.5rem;">⚡</div>
            <div>
                <div style="font-size: 1rem; font-weight: 700; color: #e6edf3;">UVM Generator</div>
                <div style="font-size: 0.7rem; color: #8b949e;">v2.1.0</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    with st.expander("Specification", expanded=True):
        st.markdown('<div class="sidebar-label">Protocol</div>', unsafe_allow_html=True)
        
        selected_protocol = st.selectbox(
            "Protocol",
            list(EXAMPLES.keys()),
            index=0,
            label_visibility="collapsed",
            key="p_sel"
        )
        
        st.markdown('<div class="sidebar-label">Design Name</div>', unsafe_allow_html=True)
        
        design_name = st.text_input(
            "Design Name",
            value=f"{selected_protocol.lower()}_controller",
            label_visibility="collapsed",
            key="d_nm"
        )
        
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        
        st.markdown('<div class="sidebar-label">Clock & Reset</div>', unsafe_allow_html=True)
        
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            clk_freq = st.number_input("Clock (MHz)", value=100.0, min_value=1.0, step=10.0, key="clk_f")
        with col_c2:
            rst_polarity = st.selectbox("Reset", ["Active Low", "Active High"], index=0, key="rst_p")

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    
    with st.expander("AI Configuration", expanded=True):
        st.markdown('<div class="sidebar-label">Generation Engine</div>', unsafe_allow_html=True)
        
        model_mode = st.radio(
            "Mode",
            list(MODEL_CONFIGS.keys()),
            index=0,
            format_func=lambda k: MODEL_CONFIGS[k]["name"],
            label_visibility="collapsed",
            key="m_mode"
        )
        
        st.caption(MODEL_CONFIGS[model_mode]["desc"])
        
        for feat in MODEL_CONFIGS[model_mode]["features"]:
            st.markdown(f'<span class="tag">{feat}</span>', unsafe_allow_html=True)
        
        if model_mode == "v2":
            st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
            st.markdown('<div class="sidebar-label">RL Optimization</div>', unsafe_allow_html=True)
            
            rl_strategy = st.selectbox(
                "Exploration Strategy",
                list(RL_STRATEGIES.keys()),
                index=0,
                format_func=lambda k: RL_STRATEGIES[k],
                key="rl_s"
            )
            
            enable_learning = st.checkbox("Continuous Learning", value=True, key="l_en")
            strict_uvm = st.checkbox("Strict UVM Compliance", value=True, key="uvm_s")

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    
    with st.expander("Execution", expanded=True):
        st.markdown('<div class="sidebar-label">Run Control</div>', unsafe_allow_html=True)
        
        max_iterations = st.slider(
            "Iterations",
            min_value=1,
            max_value=10,
            value=1,
            key="m_iter"
        )
        
        enable_sim = st.checkbox("Run Simulation", value=False, key="s_en")
        enable_val = st.checkbox("Validate Output", value=True, key="v_en")
        
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        
        generate_btn = st.button(
            "Generate Testbench",
            type="primary",
            use_container_width=True,
            key="r_btn"
        )
        
        col_a, col_b = st.columns(2)
        with col_a:
            validate_btn = st.button("Validate", use_container_width=True, key="v_btn")
        with col_b:
            export_btn = st.button("Export", use_container_width=True, key="e_btn")

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    
    with st.expander("Resources", expanded=False):
        st.markdown('<div class="sidebar-label">License Utilization</div>', unsafe_allow_html=True)
        
        st.markdown("""
        <div style="margin-bottom: 1rem;">
            <div style="display: flex; justify-content: space-between; font-size: 0.75rem; margin-bottom: 0.25rem;">
                <span style="color: #8b949e;">UVM Engine</span>
                <span style="color: #c9d1d9;">65%</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill blue" style="width: 65%;"></div>
            </div>
        </div>
        <div>
            <div style="display: flex; justify-content: space-between; font-size: 0.75rem; margin-bottom: 0.25rem;">
                <span style="color: #8b949e;">AI Credits</span>
                <span style="color: #c9d1d9;">82%</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill" style="width: 82%;"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        
        st.markdown('<div class="sidebar-label">System Status</div>', unsafe_allow_html=True)
        
        st.markdown("""
        <div style="display: flex; align-items: center; gap: 0.5rem; padding: 0.5rem 0.75rem; background-color: #1c2128; border-radius: 6px;">
            <div class="status-dot success"></div>
            <span style="font-size: 0.8125rem; color: #3fb950;">All Systems Operational</span>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    st.caption("Sai Kumar Taraka")

st.markdown("""
<div class="top-nav">
    <div style="display: flex; align-items: center; gap: 1.5rem;">
        <div class="nav-item">
            <span>Design:</span>
            <span class="nav-item value" id="design-display">uart_controller</span>
        </div>
        <div class="nav-item">
            <span>Protocol:</span>
            <span class="nav-item value" id="protocol-display">UART</span>
        </div>
        <div class="nav-item">
            <span>Engine:</span>
            <span class="nav-item value" id="engine-display">V2</span>
        </div>
    </div>
    <div style="display: flex; align-items: center; gap: 1.5rem;">
        <div class="nav-item">
            <span>Run:</span>
            <span class="nav-item value">#0</span>
        </div>
        <div style="display: flex; align-items: center; gap: 0.375rem;">
            <div class="status-dot success"></div>
            <span style="font-size: 0.8125rem; color: #8b949e;">Ready</span>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

tab_spec, tab_gen, tab_results, tab_analysis, tab_coverage, tab_logs = st.tabs([
    "Specification",
    "Generation",
    "Results",
    "Analysis",
    "Coverage",
    "Logs"
])

with tab_spec:
    col_edit, col_summary = st.columns([2, 1])
    
    with col_edit:
        st.markdown('<div class="card-header">YAML Specification Editor</div>', unsafe_allow_html=True)
        
        spec_text = st.text_area(
            "Edit Specification",
            value=EXAMPLES[selected_protocol],
            height=520,
            key="s_edit",
            label_visibility="collapsed"
        )
        
        cols = st.columns(4)
        with cols[0]:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{selected_protocol}</div>
                <div class="metric-label">Protocol</div>
            </div>
            """, unsafe_allow_html=True)
        with cols[1]:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{design_name}</div>
                <div class="metric-label">Design</div>
            </div>
            """, unsafe_allow_html=True)
        with cols[2]:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{model_mode.upper()}</div>
                <div class="metric-label">Engine</div>
            </div>
            """, unsafe_allow_html=True)
        with cols[3]:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">READY</div>
                <div class="metric-label">Status</div>
            </div>
            """, unsafe_allow_html=True)
    
    with col_summary:
        st.markdown('<div class="card-header">Specification Summary</div>', unsafe_allow_html=True)
        
        import yaml
        try:
            spec_dict = yaml.safe_load(spec_text)
            
            cols_s = st.columns(2)
            with cols_s[0]:
                st.metric("Interfaces", len(spec_dict.get('interfaces', [])))
                total_sigs = sum(len(i.get('signals', [])) for i in spec_dict.get('interfaces', []))
                st.metric("Signals", total_sigs)
            
            with cols_s[1]:
                st.metric("Registers", len(spec_dict.get('registers', [])))
                total_fields = sum(len(r.get('fields', [])) for r in spec_dict.get('registers', []))
                st.metric("Fields", total_fields)
            
            st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
            st.markdown('<div class="section-title">Interface Configuration</div>', unsafe_allow_html=True)
            
            for iface in spec_dict.get('interfaces', []):
                with st.expander(f"🔌 {iface.get('name')}"):
                    for sig in iface.get('signals', []):
                        name = sig.get('name')
                        direction = sig.get('direction')
                        width = sig.get('width', 1)
                        dir_color = "#3fb950" if direction == "input" else "#58a6ff"
                        st.markdown(f"""
                        <div style="display: flex; justify-content: space-between; padding: 0.375rem 0; border-bottom: 1px solid #21262d;">
                            <span style="font-family: 'JetBrains Mono', monospace; font-size: 0.8125rem;">{name}</span>
                            <span style="font-size: 0.75rem; color: {dir_color};">{direction} [{width}]</span>
                        </div>
                        """, unsafe_allow_html=True)
                        
        except Exception as e:
            st.error(f"Parse Error: {e}")

with tab_gen:
    st.markdown('<div class="card-header">Generation Control</div>', unsafe_allow_html=True)
    
    cols_g = st.columns(4)
    with cols_g[0]:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{model_mode.upper()}</div>
            <div class="metric-label">Engine</div>
        </div>
        """, unsafe_allow_html=True)
    with cols_g[1]:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{max_iterations}</div>
            <div class="metric-label">Iterations</div>
        </div>
        """, unsafe_allow_html=True)
    with cols_g[2]:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{'ON' if enable_learning else 'OFF'}</div>
            <div class="metric-label">Learning</div>
        </div>
        """, unsafe_allow_html=True)
    with cols_g[3]:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{'ON' if strict_uvm else 'OFF'}</div>
            <div class="metric-label">UVM Strict</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="card-header">Verification Pipeline</div>', unsafe_allow_html=True)
    
    pipeline_cols = st.columns(6)
    pipeline_steps = [
        ("Spec Parse", True, "success"),
        ("Feature Ext", True, "success"),
        ("ML Generation", False, "pending"),
        ("UVM Validation", False, "pending"),
        ("Coverage Analysis", False, "pending"),
        ("Export", False, "pending")
    ]
    
    for i, (step, is_done, status) in enumerate(pipeline_steps):
        with pipeline_cols[i]:
            dot_class = status
            bg_color = "#1c2128" if is_done else "#0d1117"
            border_color = "#3fb950" if is_done else "#21262d"
            text_color = "#3fb950" if is_done else "#8b949e"
            
            st.markdown(f"""
            <div style="text-align: center; padding: 1rem 0.5rem; background: {bg_color}; border: 1px solid {border_color}; border-radius: 6px;">
                <div class="status-dot {dot_class}" style="margin: 0 auto 0.5rem auto; width: 12px; height: 12px;"></div>
                <div style="font-size: 0.75rem; color: {text_color}; font-weight: 500;">{step}</div>
            </div>
            """, unsafe_allow_html=True)
    
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    
    col_info1, col_info2 = st.columns(2)
    
    with col_info1:
        st.markdown("""
        <div class="info-box">
            <div class="title">Coverage Strategy</div>
            <div class="content">
                Recommended: Add directed tests for reset values, bus protocols, and register access patterns.
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col_info2:
        st.markdown("""
        <div class="info-box">
            <div class="title">Assertion Generator</div>
            <div class="content">
                AI can generate protocol-specific assertions for signal timing, handshakes, and data integrity.
            </div>
        </div>
        """, unsafe_allow_html=True)

with tab_results:
    if st.session_state.last_result:
        result = st.session_state.last_result
        eval_metrics = result.get('evaluation', {})
        
        st.markdown('<div class="card-header">Generation Metrics</div>', unsafe_allow_html=True)
        
        cols_m = st.columns(6)
        
        metrics_display = [
            ("Completeness", eval_metrics.get('completeness', 0) * 100, "%"),
            ("Signal Cov", eval_metrics.get('interface_signal_coverage', 0) * 100, "%"),
            ("Register Cov", eval_metrics.get('register_coverage', 0) * 100, "%"),
            ("Files", len(st.session_state.generated_files), ""),
            ("Iterations", result.get('auto_train_iterations', 0), ""),
            ("Status", "PASS" if result.get('passed') else "DONE", "")
        ]
        
        for i, (label, value, suffix) in enumerate(metrics_display):
            with cols_m[i]:
                if isinstance(value, float):
                    display_val = f"{value:.1f}{suffix}"
                else:
                    display_val = f"{value}{suffix}"
                
                is_pass = (label == "Status" and value == "PASS") or (isinstance(value, (int, float)) and value >= 90)
                success_class = "metric-success" if is_pass else ""
                
                st.markdown(f"""
                <div class="metric-card {success_class}">
                    <div class="metric-value">{display_val}</div>
                    <div class="metric-label">{label}</div>
                </div>
                """, unsafe_allow_html=True)
        
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        
        if st.session_state.generated_files:
            st.markdown('<div class="card-header">Generated Files</div>', unsafe_allow_html=True)
            
            col_tree, col_code = st.columns([1, 3])
            
            with col_tree:
                file_names = sorted(st.session_state.generated_files.keys())
                
                if 'selected_file' not in st.session_state:
                    st.session_state.selected_file = file_names[0] if file_names else None
                
                st.markdown('<div class="file-tree">', unsafe_allow_html=True)
                for fn in file_names:
                    is_active = (fn == st.session_state.selected_file)
                    active_class = "active" if is_active else ""
                    if st.button(fn, key=f"f_{fn}", use_container_width=True):
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
                                    "Download",
                                    data=content,
                                    file_name=selected_file,
                                    mime="text/plain",
                                    use_container_width=True
                                )
                            with col_dl2:
                                st.button("Copy", use_container_width=True, key="cp_btn")
                            with col_info:
                                st.caption(f"Lines: {len(content.splitlines())} | Size: {len(content)} bytes")
                            
                            st.markdown(f"""
                            <div class="code-editor"><pre>{content}</pre></div>
                            """, unsafe_allow_html=True)
                            
                        except Exception as e:
                            st.warning(f"Could not read file: {e}")
            
            st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
            
            st.markdown('<div class="card-header">Export Package</div>', unsafe_allow_html=True)
            
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for name, path in st.session_state.generated_files.items():
                    if os.path.exists(path):
                        zipf.write(path, arcname=name)
            zip_buffer.seek(0)
            
            col_e1, col_e2, col_e3 = st.columns([2, 2, 3])
            with col_e1:
                st.download_button(
                    "Download UVM Package",
                    data=zip_buffer,
                    file_name=f"{design_name}_uvm_testbench.zip",
                    mime="application/zip",
                    use_container_width=True,
                    type="primary"
                )
            with col_e2:
                st.button("Generate Simulation Script", use_container_width=True)
            with col_e3:
                st.button("Create Regression Suite", use_container_width=True)
        
    else:
        st.markdown("""
        <div class="empty-state">
            <div class="icon">⚡</div>
            <div class="title">Ready to Generate</div>
            <div class="description">
                Configure your specification and click "Generate Testbench" in the sidebar.
            </div>
        </div>
        """, unsafe_allow_html=True)

with tab_analysis:
    if st.session_state.ml_stats:
        stats = st.session_state.ml_stats
        
        st.markdown('<div class="card-header">ML Analysis Dashboard</div>', unsafe_allow_html=True)
        
        cols_a = st.columns(4)
        with cols_a[0]:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{stats.get('total_generations', 0)}</div>
                <div class="metric-label">Generations</div>
            </div>
            """, unsafe_allow_html=True)
        with cols_a[1]:
            if 'rl_learner' in stats:
                rl = stats['rl_learner']
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-value">{rl.get('episode_count', 0)}</div>
                    <div class="metric-label">RL Episodes</div>
                </div>
                """, unsafe_allow_html=True)
        with cols_a[2]:
            if 'rl_learner' in stats:
                rl = stats['rl_learner']
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-value">{rl.get('total_updates', 0)}</div>
                    <div class="metric-label">Updates</div>
                </div>
                """, unsafe_allow_html=True)
        with cols_a[3]:
            if 'rl_learner' in stats:
                rl = stats['rl_learner']
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-value">{rl.get('learning_rate', 0.1):.3f}</div>
                    <div class="metric-label">Learning Rate</div>
                </div>
                """, unsafe_allow_html=True)
        
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        
        col_dist, col_weights = st.columns(2)
        
        with col_dist:
            st.markdown('<div class="card-header">Source Distribution</div>', unsafe_allow_html=True)
            
            if 'source_distribution' in stats:
                dist = stats['source_distribution']
                if dist:
                    df = pd.DataFrame({
                        'Source': list(dist.keys()),
                        'Count': list(dist.values())
                    })
                    st.bar_chart(df.set_index('Source'), color=["#58a6ff"])
            else:
                st.info("No distribution data yet")
        
        with col_weights:
            st.markdown('<div class="card-header">Strategy Weights</div>', unsafe_allow_html=True)
            
            if 'strategy_weights' in stats:
                weights = stats['strategy_weights']
                for strategy, weight in weights.items():
                    percentage = weight * 100
                    st.markdown(f"""
                    <div style="margin-bottom: 1rem;">
                        <div style="display: flex; justify-content: space-between; font-size: 0.8125rem; margin-bottom: 0.25rem;">
                            <span style="text-transform: uppercase; font-weight: 500; color: #c9d1d9;">{strategy}</span>
                            <span style="color: #58a6ff; font-weight: 600;">{percentage:.1f}%</span>
                        </div>
                        <div class="progress-bar">
                            <div class="progress-fill blue" style="width: {percentage}%"></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("No strategy weights yet")
        
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        
        st.markdown('<div class="card-header">RL State Performance</div>', unsafe_allow_html=True)
        
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
                        <div class="card" style="margin: 0; text-align: center;">
                            <div style="font-size: 0.7rem; color: #8b949e; text-transform: uppercase; letter-spacing: 0.02em; margin-bottom: 0.5rem;">{state[:20]}</div>
                            <div style="font-size: 1.25rem; font-weight: 700; color: #58a6ff; margin-bottom: 0.25rem;">{q_val:.3f}</div>
                            <div style="font-size: 0.75rem; color: #8b949e;">Q-Value</div>
                            <div style="margin-top: 0.75rem; padding-top: 0.75rem; border-top: 1px solid #21262d;">
                                <div style="font-size: 0.75rem; color: #8b949e;">Best: <span style="color: #3fb950; font-weight: 600;">{best_action}</span></div>
                                <div style="font-size: 0.75rem; color: #8b949e; margin-top: 0.25rem;">Visits: {visits}</div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
        else:
            st.info("No RL state data yet - run a generation to collect statistics")
        
    else:
        st.markdown("""
        <div class="empty-state">
            <div class="icon">🔬</div>
            <div class="title">ML Analysis</div>
            <div class="description">
                Run a generation with the ML-Driven engine to see:
                <br><br>
                • Reinforcement Learning metrics<br>
                • Strategy weight distributions<br>
                • Q-value tracking<br>
                • Source distribution analysis
            </div>
        </div>
        """, unsafe_allow_html=True)

with tab_coverage:
    st.markdown('<div class="card-header">Coverage Analysis</div>', unsafe_allow_html=True)
    
    cols_c = st.columns(4)
    with cols_c[0]:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">95%</div>
            <div class="metric-label">Target</div>
        </div>
        """, unsafe_allow_html=True)
    with cols_c[1]:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">--</div>
            <div class="metric-label">Functional</div>
        </div>
        """, unsafe_allow_html=True)
    with cols_c[2]:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">--</div>
            <div class="metric-label">Assertion</div>
        </div>
        """, unsafe_allow_html=True)
    with cols_c[3]:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">--</div>
            <div class="metric-label">Code</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    
    st.markdown('<div class="card-header">Coverage Closure Assistant</div>', unsafe_allow_html=True)
    
    st.markdown("""
    <div class="info-box">
        <div class="title">🎯 AI Coverage Recommendations</div>
        <div style="margin-top: 1rem;">
            <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.75rem; padding: 0.5rem 0; border-bottom: 1px solid #21262d;">
                <div style="width: 24px; height: 24px; border-radius: 50%; background: #1c2128; display: flex; align-items: center; justify-content: center; color: #58a6ff; font-size: 0.875rem; font-weight: 600;">1</div>
                <span style="font-size: 0.875rem;">Add directed tests for edge cases (all 0s, all 1s, max values)</span>
            </div>
            <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.75rem; padding: 0.5rem 0; border-bottom: 1px solid #21262d;">
                <div style="width: 24px; height: 24px; border-radius: 50%; background: #1c2128; display: flex; align-items: center; justify-content: center; color: #58a6ff; font-size: 0.875rem; font-weight: 600;">2</div>
                <span style="font-size: 0.875rem;">Verify reset values for all registers</span>
            </div>
            <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.75rem; padding: 0.5rem 0; border-bottom: 1px solid #21262d;">
                <div style="width: 24px; height: 24px; border-radius: 50%; background: #1c2128; display: flex; align-items: center; justify-content: center; color: #58a6ff; font-size: 0.875rem; font-weight: 600;">3</div>
                <span style="font-size: 0.875rem;">Test protocol handshakes with back-to-back transactions</span>
            </div>
            <div style="display: flex; align-items: center; gap: 0.75rem; padding: 0.5rem 0;">
                <div style="width: 24px; height: 24px; border-radius: 50%; background: #1c2128; display: flex; align-items: center; justify-content: center; color: #58a6ff; font-size: 0.875rem; font-weight: 600;">4</div>
                <span style="font-size: 0.875rem;">Add concurrent stimulus for protocol validation</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

with tab_logs:
    st.markdown('<div class="card-header">Execution Logs</div>', unsafe_allow_html=True)
    
    if st.session_state.log_output:
        log_html = "\n".join([
            f'<span style="color: #8b949e;">{line}</span>'
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
            <span style="color: #8b949e;">[{datetime.now().strftime('%H:%M:%S')}] System initialized</span><br>
            <span style="color: #8b949e;">[{datetime.now().strftime('%H:%M:%S')}] Waiting for specification...</span><br>
            <span style="color: #8b949e;">[{datetime.now().strftime('%H:%M:%S')}] AI engine ready</span><br>
            <span style="color: #8b949e;">[{datetime.now().strftime('%H:%M:%S')}] UVM templates loaded</span><br>
            <span style="color: #8b949e;">[{datetime.now().strftime('%H:%M:%S')}] All systems operational</span><br>
            <br>
            <span style="color: #484f58; font-style: italic;"># Click "Generate Testbench" to begin</span>
        </div>
        """, unsafe_allow_html=True)
    
    col_clear, col_export = st.columns([1, 5])
    with col_clear:
        st.button("Clear Logs", use_container_width=True)

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
