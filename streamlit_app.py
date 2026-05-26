"""
Enhanced Streamlit UI for UVM Testbench Generator
Shows advanced ML capabilities: V2 model, RL strategies, learning persistence, etc.
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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("uvmgen-streamlit")

st.set_page_config(
    page_title="UVM Testbench Generator - AI/ML Enhanced",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

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

MODEL_TYPES = {
    "template": "Template Only (Fast, No Learning)",
    "hybrid": "Hybrid ML (Retrieval + Templates)",
    "v2": "Advanced ML V2 (Recommended) - RL + Pattern Learning",
}

EXPLORATION_STRATEGIES = {
    "ucb": "UCB1 (Upper Confidence Bound) - Best for exploration/exploitation balance",
    "epsilon_greedy": "Epsilon-Greedy - Simple, with decaying randomness",
    "softmax": "Softmax (Boltzmann) - Probabilistic based on Q-values",
    "thompson": "Thompson Sampling - Bayesian approach with Beta distributions",
}

if 'last_result' not in st.session_state:
    st.session_state.last_result = None
if 'generated_files' not in st.session_state:
    st.session_state.generated_files = {}
if 'log_output' not in st.session_state:
    st.session_state.log_output = []
if 'ml_stats' not in st.session_state:
    st.session_state.ml_stats = None
if 'learning_state_path' not in st.session_state:
    st.session_state.learning_state_path = None

st.title("🔬 UVM Testbench Generator")
st.markdown("""
**AI-Powered Semiconductor Verification Pipeline with Advanced ML**  
Generate industry-grade UVM testbenches from YAML specifications. Now featuring:
- **Advanced ML V2** with Reinforcement Learning (UCB, Softmax, Thompson Sampling)
- **Experience Replay Buffer** (10,000 capacity)
- **Eligibility Traces** for better credit assignment
- **Pattern Mining** with N-grams and Association Rules
- **Deep UVM Compliance Validation** (factory registration, phases, TLM)
- **Continuous Learning** with state persistence
""")

with st.sidebar:
    st.header("⚙️ Configuration")
    
    with st.expander("📋 Quick Setup", expanded=True):
        selected_protocol = st.selectbox(
            "Protocol Example",
            list(EXAMPLES.keys()),
            index=0,
            help="Select a pre-built protocol specification"
        )
        
        default_name = selected_protocol.lower() + "_controller"
        design_name = st.text_input(
            "Design Name",
            value=default_name,
            help="Name for your generated IP"
        )

    st.divider()
    
    with st.expander("🤖 ML Configuration", expanded=True):
        use_ml = st.checkbox(
            "Enable AI/ML Features",
            value=True,
            help="Use machine learning for intelligent generation"
        )
        
        if use_ml:
            model_type = st.selectbox(
                "ML Model Version",
                list(MODEL_TYPES.keys()),
                index=2,
                format_func=lambda k: MODEL_TYPES[k],
                help="V2 is recommended for advanced learning"
            )
            
            if model_type == "v2":
                exploration_strategy = st.selectbox(
                    "RL Exploration Strategy",
                    list(EXPLORATION_STRATEGIES.keys()),
                    index=0,
                    format_func=lambda k: EXPLORATION_STRATEGIES[k].split(" - ")[0],
                    help="How the RL agent balances exploration and exploitation"
                )
                
                st.caption(EXPLORATION_STRATEGIES[exploration_strategy])
                
                persist_learning = st.checkbox(
                    "Persist Learning State",
                    value=True,
                    help="Save and load learned patterns between sessions"
                )
                
                if persist_learning:
                    st.session_state.learning_state_path = os.path.join(
                        tempfile.gettempdir(), 
                        "uvmgen_learning_state.json"
                    )
                    st.caption(f"State will be saved to: temporary directory")
            
            strict_validation = st.checkbox(
                "Strict UVM Compliance",
                value=True,
                help="Enforce deep UVM validation (factory, phases, TLM)"
            )
            
            auto_learn = st.checkbox(
                "Continuous Learning",
                value=True,
                help="Learn from each generation to improve future results"
            )
        else:
            model_type = "template"
            exploration_strategy = "ucb"
            strict_validation = False
            auto_learn = False

    st.divider()
    
    with st.expander("⚡ Generation Options"):
        auto_train = st.checkbox(
            "Coverage-Driven Auto-Training",
            value=False,
            help="Iteratively improve testbench based on coverage analysis"
        )
        
        max_iterations = st.slider(
            "Max Iterations",
            min_value=1,
            max_value=10,
            value=1,
            help="Maximum auto-training iterations"
        )
        
        st.caption("Auto-training requires a simulator (Icarus Verilog, VCS, or Questa)")

    st.divider()
    
    with st.expander("ℹ️ About"):
        st.info("💡 **UVM = Universal Verification Methodology**")
        st.info("🔬 **ML V2 = Reinforcement Learning + Pattern Mining**")
        st.markdown("---")
        st.caption("Developed by **Sai Kumar Taraka**")
        st.caption("Promotion-Ready Advanced ML System")

tab_spec, tab_results, tab_ml_insights = st.tabs([
    "📝 Specification", 
    "📊 Results & Files",
    "🤖 ML Insights"
])

with tab_spec:
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("✏️ YAML Specification Editor")
        spec_text = st.text_area(
            "Edit your specification",
            value=EXAMPLES[selected_protocol],
            height=450,
            key="spec_editor",
            help="Define your interfaces, signals, registers, and protocol"
        )
        
        st.caption(f"Protocol: {selected_protocol} | Model: {model_type.upper()} | Strategy: {exploration_strategy.upper()}")
    
    with col2:
        st.subheader("📋 Specification Summary")
        
        import yaml
        try:
            spec_dict = yaml.safe_load(spec_text)
            
            st.metric("Design Name", spec_dict.get('design_name', 'unknown'))
            st.metric("Protocol", spec_dict.get('protocol', 'unknown').upper())
            
            col_a, col_b = st.columns(2)
            with col_a:
                interfaces = spec_dict.get('interfaces', [])
                st.metric("Interfaces", len(interfaces))
                total_signals = sum(len(i.get('signals', [])) for i in interfaces)
                st.metric("Total Signals", total_signals)
            
            with col_b:
                registers = spec_dict.get('registers', [])
                st.metric("Registers", len(registers))
                total_fields = sum(len(r.get('fields', [])) for r in registers)
                st.metric("Register Fields", total_fields)
            
            if interfaces:
                st.subheader("Interface Signals")
                for iface in interfaces:
                    with st.expander(f"🔌 {iface.get('name', 'unknown')}"):
                        signals = iface.get('signals', [])
                        for sig in signals:
                            name = sig.get('name', 'unknown')
                            direction = sig.get('direction', 'input')
                            width = sig.get('width', 1)
                            st.text(f"  • {name} ({direction}, {width}bit)")
            
            if registers:
                st.subheader("Register Map")
                for reg in registers:
                    with st.expander(f"📋 {reg.get('name', 'unknown')} @ {reg.get('address', '0x0')}"):
                        st.text(f"  Description: {reg.get('description', 'None')}")
                        fields = reg.get('fields', [])
                        if fields:
                            st.text(f"  Fields:")
                            for field in fields:
                                st.text(f"    • {field.get('name', 'unknown')} [{field.get('bits', '0')}]")
                        
        except Exception as e:
            st.error(f"Invalid YAML: {e}")
    
    st.divider()
    
    generate_btn = st.button(
        "🚀 Generate UVM Testbench",
        type="primary",
        use_container_width=True,
        help=f"Generate using {model_type.upper()} model"
    )

with tab_results:
    status_placeholder = st.empty()
    
    metrics_placeholder = st.empty()
    
    with st.expander("📋 Log Output", expanded=True):
        log_placeholder = st.empty()
    
    files_placeholder = st.empty()

with tab_ml_insights:
    st.header("🤖 Advanced ML Insights")
    
    if st.session_state.ml_stats:
        stats = st.session_state.ml_stats
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📊 Learning Statistics")
            total_gen = stats.get('total_generations', 0)
            st.metric("Total Generations", total_gen)
            
            if 'recent_performance' in stats:
                perf = stats['recent_performance']
                st.metric("Recent Pass Rate", f"{perf.get('pass_rate', 0)*100:.1f}%")
                st.metric("Avg Score", f"{perf.get('avg_score', 0):.3f}")
            
            if 'rl_learner' in stats:
                rl_stats = stats['rl_learner']
                st.subheader("🎮 Reinforcement Learning")
                st.metric("Episode Count", rl_stats.get('episode_count', 0))
                st.metric("Total Updates", rl_stats.get('total_updates', 0))
                st.metric("Learning Rate", f"{rl_stats.get('learning_rate', 0.1):.4f}")
                
                if 'state_stats' in rl_stats:
                    st.subheader("📈 Strategy Performance")
                    state_stats = rl_stats['state_stats']
                    for state, info in list(state_stats.items())[:5]:
                        st.text(f"  {state}: best='{info.get('best_action', 'unknown')}' (Q={info.get('best_q_value', 0):.3f})")
        
        with col2:
            st.subheader("🎯 Source Distribution")
            if 'source_distribution' in stats:
                source_dist = stats['source_distribution']
                fig_data = {
                    'Source': list(source_dist.keys()),
                    'Count': list(source_dist.values())
                }
                st.bar_chart(fig_data, x='Source', y='Count')
            
            st.subheader("⚖️ Strategy Weights")
            if 'strategy_weights' in stats:
                weights = stats['strategy_weights']
                st.json(weights)
            
            if 'pattern_learner' in stats:
                st.subheader("🔍 Pattern Learner")
                patterns = stats['pattern_learner']
                if 'common_errors' in patterns:
                    st.text("Common Error Patterns:")
                    for err, count in patterns['common_errors'][:5]:
                        st.text(f"  • {err}: {count} occurrences")
                
                if 'recommendations' in patterns:
                    st.subheader("💡 Recommendations")
                    for rec in patterns['recommendations'][:5]:
                        st.info(rec)
        
        st.divider()
        
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("📥 Export Learning State"):
                if st.session_state.learning_state_path and os.path.exists(st.session_state.learning_state_path):
                    with open(st.session_state.learning_state_path, 'r') as f:
                        state_data = f.read()
                    st.download_button(
                        "Download Learning State JSON",
                        data=state_data,
                        file_name="uvmgen_learning_state.json",
                        mime="application/json"
                    )
                else:
                    st.warning("No learning state saved yet")
        
        with col_b:
            uploaded_file = st.file_uploader("📤 Import Learning State", type="json")
            if uploaded_file is not None:
                try:
                    state_data = json.load(uploaded_file)
                    if st.session_state.learning_state_path:
                        with open(st.session_state.learning_state_path, 'w') as f:
                            json.dump(state_data, f, indent=2)
                        st.success("Learning state imported! It will be loaded on next generation.")
                except Exception as e:
                    st.error(f"Failed to import: {e}")
    
    else:
        st.info("Run a generation first to see ML insights.")
        st.markdown("""
        ### What you'll see here:
        - **Learning Statistics**: Total generations, pass rates, average scores
        - **RL Metrics**: Episode counts, learning rates, strategy performance
        - **Pattern Analysis**: Common error patterns and recommendations
        - **Strategy Distribution**: Which generation sources work best
        - **Import/Export**: Save and load learned state
        
        ### ML V2 Capabilities:
        1. **Reinforcement Learning** with 4 exploration strategies
        2. **Experience Replay** buffer (10,000 capacity)
        3. **Eligibility Traces** for better credit assignment
        4. **Pattern Mining** with N-grams and Association Rules
        5. **Deep UVM Validation** for factory registration, phases, TLM connections
        """)

if generate_btn:
    st.session_state.log_output = []
    st.session_state.last_result = None
    st.session_state.generated_files = {}
    st.session_state.ml_stats = None
    
    status_placeholder.info("🔄 Generating UVM testbench...")
    
    try:
        from src.config import ConfigLoader, PipelineConfig
        from src.pipeline import TBPipeline
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
            f.write(spec_text)
            spec_path = f.name
        
        timestamp = datetime.now().strftime('%H:%M:%S')
        st.session_state.log_output.append(f"[{timestamp}] Starting generation for: {design_name}")
        st.session_state.log_output.append(f"[{timestamp}] Model: {model_type}")
        if model_type == "v2":
            st.session_state.log_output.append(f"[{timestamp}] RL Strategy: {exploration_strategy}")
        st.session_state.log_output.append(f"[{timestamp}] ML Enabled: {use_ml}")
        st.session_state.log_output.append(f"[{timestamp}] Strict Validation: {strict_validation}")
        log_placeholder.code("\n".join(st.session_state.log_output))
        
        pipeline = TBPipeline()
        
        if use_ml:
            pipeline.cfg.ml.enabled = True
            pipeline.cfg.ml.model_type = model_type
            pipeline.cfg.ml.use_llm = False
            pipeline.cfg.ml.use_semantic_encoder = False
            pipeline.cfg.ml.use_learning = auto_learn
            pipeline.cfg.ml.strict_validation = strict_validation
            
            if model_type == "v2":
                pipeline.cfg.ml.exploration_strategy = exploration_strategy
                if st.session_state.learning_state_path:
                    pipeline.cfg.ml.learning_storage_path = st.session_state.learning_state_path
        else:
            pipeline.cfg.ml.enabled = False
        
        pipeline.cfg.auto_train.enabled = auto_train
        pipeline.cfg.auto_train.max_iterations = max_iterations
        
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
            elif hasattr(pipeline.model, '_rl_learner') and hasattr(pipeline.model, '_pattern_learner'):
                st.session_state.ml_stats = {
                    'total_generations': len(st.session_state.log_output),
                    'rl_learner': pipeline.model._rl_learner.get_performance_stats() if hasattr(pipeline.model._rl_learner, 'get_performance_stats') else {},
                }
        except Exception as e:
            logger.warning(f"Could not get ML stats: {e}")
        
        timestamp = datetime.now().strftime('%H:%M:%S')
        st.session_state.log_output.append(f"[{timestamp}] Generation complete!")
        st.session_state.log_output.append(f"[{timestamp}] Files generated: {len(st.session_state.generated_files)}")
        if result.get('passed'):
            st.session_state.log_output.append(f"[{timestamp}] Status: PASSED ✅")
        else:
            st.session_state.log_output.append(f"[{timestamp}] Status: COMPLETED WITH WARNINGS ⚠️")
        log_placeholder.code("\n".join(st.session_state.log_output))
        
        if result.get('passed'):
            status_placeholder.success("✅ Generation successful!")
        else:
            status_placeholder.warning("⚠️ Generation completed with issues")
            
    except Exception as e:
        timestamp = datetime.now().strftime('%H:%M:%S')
        st.session_state.log_output.append(f"[{timestamp}] ERROR: {str(e)}")
        log_placeholder.code("\n".join(st.session_state.log_output))
        status_placeholder.error(f"❌ Error: {str(e)}")
        import traceback
        st.session_state.log_output.append(traceback.format_exc())
        log_placeholder.code("\n".join(st.session_state.log_output))

if st.session_state.last_result:
    with tab_results:
        result = st.session_state.last_result
        
        with metrics_placeholder.container():
            eval_metrics = result.get('evaluation', {})
            
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                completeness = eval_metrics.get('completeness', 0) * 100
                st.metric("Completeness", f"{completeness:.1f}%")
            with m2:
                signal_cov = eval_metrics.get('interface_signal_coverage', 0) * 100
                st.metric("Signal Coverage", f"{signal_cov:.1f}%")
            with m3:
                reg_cov = eval_metrics.get('register_coverage', 0) * 100
                st.metric("Register Coverage", f"{reg_cov:.1f}%")
            with m4:
                st.metric("Files Generated", len(st.session_state.generated_files))
            
            m5, m6 = st.columns(2)
            with m5:
                st.metric("Auto-Train Iterations", result.get('auto_train_iterations', 0))
            with m6:
                if result.get('passed'):
                    st.metric("Status", "✅ PASSED")
                else:
                    st.metric("Status", "⚠️ WARNINGS")
        
        with files_placeholder.expander("📄 Generated Files", expanded=True):
            if st.session_state.generated_files:
                file_names = sorted(st.session_state.generated_files.keys())
                selected_file = st.selectbox("Select file to preview", file_names, key="file_selector")
                
                if selected_file:
                    file_path = st.session_state.generated_files[selected_file]
                    if os.path.exists(file_path):
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                            
                            st.code(content, language='systemverilog')
                            
                            col1, col2 = st.columns([1, 1])
                            with col1:
                                st.download_button(
                                    f"📥 Download {selected_file}",
                                    data=content,
                                    file_name=selected_file,
                                    mime="text/plain",
                                    use_container_width=True
                                )
                            with col2:
                                st.info(f"Lines: {len(content.splitlines())} | Size: {len(content)} bytes")
                        except Exception as e:
                            st.warning(f"Could not read file: {e}")
            
            if st.session_state.generated_files:
                zip_buffer = io.BytesIO()
                
                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for name, path in st.session_state.generated_files.items():
                        if os.path.exists(path):
                            zipf.write(path, arcname=name)
                
                zip_buffer.seek(0)
                
                st.download_button(
                    label="📦 Download All Files as ZIP",
                    data=zip_buffer,
                    file_name=f"{design_name}_uvm_testbench.zip",
                    mime="application/zip",
                    use_container_width=True,
                    type="primary"
                )

st.divider()

footer_col1, footer_col2, footer_col3 = st.columns([1, 2, 1])

with footer_col2:
    st.caption("""
    **UVM Testbench Generator v2.0** • AI-Powered by **Sai Kumar Taraka**  
    🔬 Advanced ML: RL (UCB/Softmax/Thompson) + Pattern Mining + Experience Replay + Eligibility Traces  
    📚 Protocol Libraries: UART, SPI, I2C, AXI4-Lite, APB, Wishbone  
    🎯 Deep UVM Validation: Factory Registration, Phases, TLM Connections, Coverage  
    """)
