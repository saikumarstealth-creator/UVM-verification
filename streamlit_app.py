"""
Streamlit UI for UVM Testbench Generator
Deploy to: https://share.streamlit.io/
"""

import streamlit as st
import logging
import tempfile
import os
import zipfile
import io
from pathlib import Path
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("uvmgen-streamlit")

# Page config
st.set_page_config(
    page_title="UVM Testbench Generator",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Example specifications
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

registers:
  - name: RBR_THR
    address: 0x0
    description: Receiver Buffer / Transmitter Holding
  - name: IER
    address: 0x1
    description: Interrupt Enable
  - name: LCR
    address: 0x3
    description: Line Control
  - name: LSR
    address: 0x5
    description: Line Status

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

# Session state
if 'last_result' not in st.session_state:
    st.session_state.last_result = None
if 'generated_files' not in st.session_state:
    st.session_state.generated_files = {}
if 'log_output' not in st.session_state:
    st.session_state.log_output = []

# Header
st.title("🔬 UVM Testbench Generator")
st.markdown("""
**AI-Powered Semiconductor Verification Pipeline**  
Generate industry-grade UVM testbenches from YAML specifications with protocol libraries, coverage-driven auto-training, and CI/CD integration.
""")

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # Protocol selector
    selected_protocol = st.selectbox(
        "Select Protocol Example",
        list(EXAMPLES.keys()),
        index=0
    )
    
    # Design name
    default_name = selected_protocol.lower() + "_controller"
    design_name = st.text_input(
        "Design Name",
        value=default_name
    )
    
    st.divider()
    
    # Options
    st.subheader("Options")
    use_ml = st.checkbox(
        "Enable AI/ML Features",
        value=True,
        help="Use semantic embeddings and learning (when dependencies available)"
    )
    
    auto_train = st.checkbox(
        "Enable Auto-Training",
        value=False,
        help="Coverage-driven iterative improvement"
    )
    
    max_iterations = st.slider(
        "Max Iterations",
        min_value=1,
        max_value=10,
        value=1
    )
    
    st.divider()
    
    st.info("💡 UVM = Universal Verification Methodology")
    st.caption(f"Developed by **Sai Kumar Taraka**")

# Main content
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📝 Specification")
    
    # Spec editor
    spec_text = st.text_area(
        "YAML Specification",
        value=EXAMPLES[selected_protocol],
        height=400,
        key="spec_editor",
        help="Edit the YAML specification for your design"
    )
    
    # Generate button
    generate_btn = st.button(
        "🚀 Generate UVM Testbench",
        type="primary",
        use_container_width=True
    )

with col2:
    st.subheader("📊 Results & Output")
    
    # Status
    status_placeholder = st.empty()
    
    # Metrics
    metrics_placeholder = st.empty()
    
    # Logs
    with st.expander("📋 Log Output", expanded=True):
        log_placeholder = st.empty()
    
    # Files
    files_placeholder = st.empty()


# Generate logic
if generate_btn:
    st.session_state.log_output = []
    st.session_state.last_result = None
    st.session_state.generated_files = {}
    
    status_placeholder.info("🔄 Generating UVM testbench...")
    
    try:
        # Import here for lazy loading
        from src.config import ConfigLoader, PipelineConfig
        from src.pipeline import TBPipeline
        
        # Save spec to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
            f.write(spec_text)
            spec_path = f.name
        
        st.session_state.log_output.append(f"[{datetime.now().strftime('%H:%M:%S')}] Starting generation for: {design_name}")
        log_placeholder.code("\n".join(st.session_state.log_output))
        
        # Create pipeline
        pipeline = TBPipeline()
        pipeline.cfg.ml.enabled = use_ml
        pipeline.cfg.ml.model_type = "hybrid"
        pipeline.cfg.ml.use_llm = use_ml
        pipeline.cfg.ml.use_semantic_encoder = use_ml
        pipeline.cfg.ml.use_learning = use_ml
        pipeline.cfg.auto_train.enabled = auto_train
        pipeline.cfg.auto_train.max_iterations = max_iterations
        
        st.session_state.log_output.append(f"[{datetime.now().strftime('%H:%M:%S')}] ML enabled: {use_ml}")
        st.session_state.log_output.append(f"[{datetime.now().strftime('%H:%M:%S')}] Auto-train: {auto_train} (iterations: {max_iterations})")
        log_placeholder.code("\n".join(st.session_state.log_output))
        
        # Run pipeline
        result = pipeline.run(spec_path)
        
        # Cleanup
        try:
            os.unlink(spec_path)
        except:
            pass
        
        # Store results
        st.session_state.last_result = result
        st.session_state.generated_files = result.get('generated_files', {})
        
        st.session_state.log_output.append(f"[{datetime.now().strftime('%H:%M:%S')}] Generation complete!")
        st.session_state.log_output.append(f"[{datetime.now().strftime('%H:%M:%S')}] Files generated: {len(st.session_state.generated_files)}")
        log_placeholder.code("\n".join(st.session_state.log_output))
        
        # Update status
        if result.get('passed'):
            status_placeholder.success("✅ Generation successful!")
        else:
            status_placeholder.warning("⚠️ Generation completed with issues")
            
    except Exception as e:
        st.session_state.log_output.append(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR: {str(e)}")
        log_placeholder.code("\n".join(st.session_state.log_output))
        status_placeholder.error(f"❌ Error: {str(e)}")
        import traceback
        st.session_state.log_output.append(traceback.format_exc())
        log_placeholder.code("\n".join(st.session_state.log_output))


# Show results
if st.session_state.last_result:
    result = st.session_state.last_result
    
    # Metrics
    with metrics_placeholder.container():
        eval_metrics = result.get('evaluation', {})
        
        m1, m2, m3 = st.columns(3)
        with m1:
            completeness = eval_metrics.get('completeness', 0) * 100
            st.metric("Completeness", f"{completeness:.1f}%")
        with m2:
            signal_cov = eval_metrics.get('interface_signal_coverage', 0) * 100
            st.metric("Signal Coverage", f"{signal_cov:.1f}%")
        with m3:
            reg_cov = eval_metrics.get('register_coverage', 0) * 100
            st.metric("Register Coverage", f"{reg_cov:.1f}%")
        
        m4, m5 = st.columns(2)
        with m4:
            st.metric("Files Generated", len(st.session_state.generated_files))
        with m5:
            st.metric("Iterations", result.get('auto_train_iterations', 0))
    
    # Files list
    with files_placeholder.expander("📄 Generated Files", expanded=True):
        if st.session_state.generated_files:
            # File selector
            file_names = sorted(st.session_state.generated_files.keys())
            selected_file = st.selectbox("Select file to preview", file_names)
            
            if selected_file:
                file_path = st.session_state.generated_files[selected_file]
                if os.path.exists(file_path):
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        st.code(content, language='systemverilog')
                    except Exception as e:
                        st.warning(f"Could not read file: {e}")
        
        # Download ZIP
        if st.session_state.generated_files:
            zip_buffer = io.BytesIO()
            
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for name, path in st.session_state.generated_files.items():
                    if os.path.exists(path):
                        zipf.write(path, arcname=name)
            
            zip_buffer.seek(0)
            
            st.download_button(
                label="📥 Download All Files as ZIP",
                data=zip_buffer,
                file_name=f"{design_name}_uvm_testbench.zip",
                mime="application/zip",
                use_container_width=True,
                type="secondary"
            )


# Footer
st.divider()
st.caption("""
**UVM Testbench Generator** • AI-Powered by Sai Kumar Taraka  
Protocol Libraries: UART, SPI, I2C, AXI4-Lite, APB, Wishbone • Coverage-Driven Auto-Training
""")
