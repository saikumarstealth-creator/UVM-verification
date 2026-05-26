"""
Industry-Grade UVM Testbench Generator UI
Professional, clean, industry-standard EDA tool interface
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
logger = logging.getLogger("uvmgen-streamlit")

st.set_page_config(
    page_title="UVM Testbench Generator",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main-header {
        font-size: 1.8rem;
        font-weight: 600;
        color: #1f77b4;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.0rem;
        color: #666;
        margin-bottom: 1rem;
    }
    .status-passed {
        color: #2ecc71;
        font-weight: 600;
    }
    .stButton>button {
        background-color: #1f77b4;
        color: white;
        border-radius: 4px;
        border: none;
        font-weight: 500;
    }
    .stButton>button:hover {
        background-color: #1a5f8a;
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
        description: Enable RX data available interrupt
      - name: etbei
        bits: '1'
        description: Enable TX holding register empty interrupt
  - name: LCR
    address: 0x3
    description: Line Control
    fields:
      - name: wls
        bits: 1:0
        description: Word length select
      - name: dlab
        bits: '7'
        description: Divisor latch access bit
  - name: LSR
    address: 0x5
    description: Line Status
    fields:
      - name: dr
        bits: '0'
        description: Data Ready
      - name: thre
        bits: '5'
        description: TX Holding Register Empty

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

MODEL_NAMES = {
    "v2": "ML-Driven (Recommended)",
    "hybrid": "Hybrid Retrieval",
    "template": "Template Only"
}

RL_STRATEGY_NAMES = {
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

st.markdown('<p class="main-header">UVM Testbench Generator</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">AI-Powered Semiconductor Verification Pipeline • Production-Grade UVM Framework</p>', unsafe_allow_html=True)
st.markdown("---")

with st.sidebar:
    st.header("Configuration")
    
    with st.expander("Specification", expanded=True):
        selected_protocol = st.selectbox(
            "Protocol",
            list(EXAMPLES.keys()),
            index=0
        )
        
        design_name = st.text_input(
            "Design Name",
            value=f"{selected_protocol.lower()}_controller"
        )

    st.markdown("---")
    
    with st.expander("Generation Mode", expanded=True):
        model_mode = st.radio(
            "Engine",
            list(MODEL_NAMES.keys()),
            index=0,
            format_func=lambda k: MODEL_NAMES[k]
        )
        
        if model_mode == "v2":
            st.caption("Advanced RL with pattern recognition")
        elif model_mode == "hybrid":
            st.caption("Similarity search + templates")
        else:
            st.caption("Fast deterministic generation")

    if model_mode == "v2":
        st.markdown("---")
        with st.expander("RL Configuration"):
            rl_strategy = st.selectbox(
                "Exploration Strategy",
                list(RL_STRATEGY_NAMES.keys()),
                index=0,
                format_func=lambda k: RL_STRATEGY_NAMES[k]
            )
            
            enable_learning = st.checkbox("Enable Learning", value=True)
            strict_uvm = st.checkbox("Strict UVM Compliance", value=True)

    st.markdown("---")
    
    with st.expander("Execution"):
        max_iterations = st.slider(
            "Iterations",
            min_value=1,
            max_value=10,
            value=1
        )

    st.markdown("---")
    
    st.header("Actions")
    
    generate_btn = st.button(
        "Run Generation",
        type="primary",
        use_container_width=True
    )
    
    st.markdown("---")
    
    with st.expander("About"):
        st.markdown("""
        **Version**: 2.0.0  
        **Author**: Sai Kumar Taraka  
        **UVM Compliance**: IEEE 1800.2-2020  
        **Status**: Production Ready
        """)

tab_spec, tab_exec, tab_results, tab_analysis = st.tabs([
    "Specification", 
    "Execution", 
    "Results", 
    "Analysis"
])

with tab_spec:
    col_edit, col_summary = st.columns([2, 1])
    
    with col_edit:
        st.subheader("YAML Specification")
        spec_text = st.text_area(
            "Editor",
            value=EXAMPLES[selected_protocol],
            height=450,
            label_visibility="collapsed"
        )
        
        st.caption(f"Protocol: {selected_protocol} | Engine: {model_mode.upper()}")
    
    with col_summary:
        st.subheader("Summary")
        
        import yaml
        try:
            spec_dict = yaml.safe_load(spec_text)
            
            st.metric("Design", spec_dict.get('design_name', 'N/A'))
            st.metric("Protocol", spec_dict.get('protocol', 'N/A').upper())
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Interfaces", len(spec_dict.get('interfaces', [])))
                total_sigs = sum(len(i.get('signals', [])) for i in spec_dict.get('interfaces', []))
                st.metric("Signals", total_sigs)
            
            with col2:
                st.metric("Registers", len(spec_dict.get('registers', [])))
                total_fields = sum(len(r.get('fields', [])) for r in spec_dict.get('registers', []))
                st.metric("Fields", total_fields)
            
            st.subheader("Interfaces")
            for iface in spec_dict.get('interfaces', []):
                with st.expander(f"{iface.get('name')}"):
                    for sig in iface.get('signals', []):
                        name = sig.get('name')
                        direction = sig.get('direction')
                        width = sig.get('width', 1)
                        st.text(f"{name} ({direction}, {width}b)")
            
            st.subheader("Registers")
            for reg in spec_dict.get('registers', []):
                st.text(f"{reg.get('name')} @ {reg.get('address')}")
                        
        except Exception as e:
            st.error(f"Parse Error: {e}")

with tab_exec:
    st.subheader("Execution")
    
    status_placeholder = st.empty()
    
    with st.expander("Run Log", expanded=True):
        log_placeholder = st.empty()

with tab_results:
    st.subheader("Results")
    
    metrics_placeholder = st.empty()
    
    with st.expander("Generated Files", expanded=True):
        file_view_placeholder = st.empty()
    
    with st.expander("Download"):
        dl_placeholder = st.empty()

with tab_analysis:
    st.subheader("ML Analysis")
    
    if st.session_state.ml_stats:
        stats = st.session_state.ml_stats
        
        col_metrics, col_details = st.columns([1, 1])
        
        with col_metrics:
            st.markdown("**Learning Metrics**")
            st.metric("Generations", stats.get('total_generations', 0))
            
            if 'rl_learner' in stats:
                rl = stats['rl_learner']
                st.metric("RL Episodes", rl.get('episode_count', 0))
                st.metric("Updates", rl.get('total_updates', 0))
        
        with col_details:
            st.markdown("**Source Distribution**")
            if 'source_distribution' in stats:
                dist = stats['source_distribution']
                if dist:
                    df = pd.DataFrame({
                        'Source': list(dist.keys()),
                        'Count': list(dist.values())
                    })
                    st.bar_chart(df.set_index('Source'))
            
            st.markdown("**Strategy Weights**")
            if 'strategy_weights' in stats:
                st.json(stats['strategy_weights'])
        
        st.markdown("---")
        st.markdown("**State Performance**")
        if 'rl_learner' in stats and 'state_stats' in stats['rl_learner']:
            state_stats = stats['rl_learner']['state_stats']
            for state, info in list(state_stats.items())[:5]:
                st.text(f"{state}: best='{info.get('best_action')}' (Q={info.get('best_q_value'):.3f})")
        
    else:
        st.info("Run a generation to view analysis data.")
        
        st.markdown("""
        **ML Analysis Features:**
        - Learning metrics tracking
        - RL strategy performance
        - Source distribution analysis
        - Q-value tracking
        """)

if generate_btn:
    st.session_state.log_output = []
    st.session_state.last_result = None
    st.session_state.generated_files = {}
    st.session_state.ml_stats = None
    
    status_placeholder.info("Running generation...")
    
    try:
        from src.config import ConfigLoader, PipelineConfig, MLConfig, GenerationConfig, AutoTrainConfig
        from src.pipeline import TBPipeline
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
            f.write(spec_text)
            spec_path = f.name
        
        timestamp = datetime.now().strftime('%H:%M:%S')
        st.session_state.log_output.append(f"[{timestamp}] Starting: {design_name}")
        st.session_state.log_output.append(f"[{timestamp}] Engine: {model_mode}")
        log_placeholder.code("\n".join(st.session_state.log_output))
        
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
        st.session_state.log_output.append(f"[{timestamp}] Complete")
        st.session_state.log_output.append(f"[{timestamp}] Files: {len(st.session_state.generated_files)}")
        
        log_placeholder.code("\n".join(st.session_state.log_output))
        
        if result.get('passed'):
            status_placeholder.success("Generation completed successfully")
        else:
            status_placeholder.warning("Generation completed")
            
    except Exception as e:
        timestamp = datetime.now().strftime('%H:%M:%S')
        st.session_state.log_output.append(f"[{timestamp}] Error: {str(e)}")
        log_placeholder.code("\n".join(st.session_state.log_output))
        status_placeholder.error(f"Error: {str(e)}")
        import traceback
        st.session_state.log_output.append(traceback.format_exc())
        log_placeholder.code("\n".join(st.session_state.log_output))

if st.session_state.last_result:
    result = st.session_state.last_result
    
    with tab_results:
        eval_metrics = result.get('evaluation', {})
        
        with metrics_placeholder.container():
            cols = st.columns(5)
            
            completeness = eval_metrics.get('completeness', 0) * 100
            signal_cov = eval_metrics.get('interface_signal_coverage', 0) * 100
            reg_cov = eval_metrics.get('register_coverage', 0) * 100
            
            cols[0].metric("Completeness", f"{completeness:.1f}%")
            cols[1].metric("Signal Coverage", f"{signal_cov:.1f}%")
            cols[2].metric("Register Coverage", f"{reg_cov:.1f}%")
            cols[3].metric("Files", len(st.session_state.generated_files))
            cols[4].metric("Iterations", result.get('auto_train_iterations', 0))
        
        with file_view_placeholder.container():
            if st.session_state.generated_files:
                file_names = sorted(st.session_state.generated_files.keys())
                selected_file = st.selectbox("File", file_names)
                
                if selected_file:
                    file_path = st.session_state.generated_files[selected_file]
                    if os.path.exists(file_path):
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                            
                            st.code(content, language='systemverilog')
                            
                            st.caption(f"Lines: {len(content.splitlines())} | Size: {len(content)} bytes")
                        except Exception as e:
                            st.warning(f"Could not read file: {e}")
        
        with dl_placeholder.container():
            if st.session_state.generated_files:
                zip_buffer = io.BytesIO()
                
                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for name, path in st.session_state.generated_files.items():
                        if os.path.exists(path):
                            zipf.write(path, arcname=name)
                
                zip_buffer.seek(0)
                
                st.download_button(
                    label="Download All Files",
                    data=zip_buffer,
                    file_name=f"{design_name}_uvm_tb.zip",
                    mime="application/zip",
                    use_container_width=True,
                    type="primary"
                )

st.markdown("---")

col_foot1, col_foot2, col_foot3 = st.columns([2, 2, 2])

with col_foot1:
    st.caption("**UVM Testbench Generator v2.0**")

with col_foot2:
    st.caption("IEEE 1800.2-2020 Compliant")

with col_foot3:
    st.caption("Sai Kumar Taraka")
