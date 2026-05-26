import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json
import re

logger = logging.getLogger("uvmgen.ml.llm")


class LLMType(Enum):
    CODEGEN = "codegen"
    CODET5 = "codet5"
    CODEBERT = "codebert"
    STARCODER = "starcoder"
    LLAMA = "llama"
    MISTRAL = "mistral"
    FALLBACK = "fallback"


@dataclass
class LLMGenerationResult:
    generated_code: str
    prompt_used: str
    model_name: str
    tokens_generated: int
    confidence: float = 0.5
    metadata: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class LLMCodeGenerator:
    _instance: Optional["LLMCodeGenerator"] = None
    _model = None
    _tokenizer = None
    _model_name: str = "Salesforce/codegen-350M-mono"
    _device: str = "cpu"
    _initialized: bool = False
    _llm_type: LLMType = LLMType.FALLBACK

    UVM_PROMPT_TEMPLATE = """
You are an expert in UVM (Universal Verification Methodology) and SystemVerilog.
Generate production-quality UVM testbench code based on the following specification.

SPECIFICATION:
{spec_text}

REQUIREMENTS:
- Follow UVM 1.2 conventions and best practices
- Use proper factory registration with `uvm_component_utils` or `uvm_object_utils`
- Include appropriate phases (build_phase, connect_phase, run_phase)
- Use TLM ports and exports for component communication
- Include proper configuration database usage if needed
- Generate synthesizable SystemVerilog code

{context_examples}

Generate the {file_type} for this specification. Return only the SystemVerilog code, no explanations.
"""

    FEW_SHOT_EXAMPLES = {
        "driver": """
EXAMPLE DRIVER:
class my_driver extends uvm_driver #(my_seq_item);
    `uvm_component_utils(my_driver)
    
    virtual my_if vif;
    
    function new(string name = "my_driver", uvm_component parent = null);
        super.new(name, parent);
    endfunction
    
    function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        if (!uvm_config_db#(virtual my_if)::get(this, "", "vif", vif))
            `uvm_fatal(get_type_name(), "Virtual interface not found")
    endfunction
    
    task run_phase(uvm_phase phase);
        forever begin
            seq_item_port.get_next_item(req);
            drive_item(req);
            seq_item_port.item_done();
        end
    endtask
    
    task drive_item(my_seq_item item);
        @(posedge vif.clk);
        vif.valid <= 1'b1;
        vif.data <= item.data;
        @(posedge vif.clk);
        vif.valid <= 1'b0;
    endtask
endclass
""",
        "monitor": """
EXAMPLE MONITOR:
class my_monitor extends uvm_monitor;
    `uvm_component_utils(my_monitor)
    
    uvm_analysis_port #(my_seq_item) item_collected_port;
    virtual my_if vif;
    
    function new(string name = "my_monitor", uvm_component parent = null);
        super.new(name, parent);
        item_collected_port = new("item_collected_port", this);
    endfunction
    
    function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        if (!uvm_config_db#(virtual my_if)::get(this, "", "vif", vif))
            `uvm_fatal(get_type_name(), "Virtual interface not found")
    endfunction
    
    task run_phase(uvm_phase phase);
        my_seq_item item;
        forever begin
            @(posedge vif.clk);
            if (vif.valid) begin
                item = my_seq_item::type_id::create("item");
                item.data = vif.data;
                item_collected_port.write(item);
            end
        end
    endtask
endclass
""",
        "agent": """
EXAMPLE AGENT:
class my_agent extends uvm_agent;
    `uvm_component_utils(my_agent)
    
    my_driver driver;
    my_monitor monitor;
    my_sequencer sequencer;
    uvm_analysis_port #(my_seq_item) item_collected_port;
    
    function new(string name = "my_agent", uvm_component parent = null);
        super.new(name, parent);
        item_collected_port = new("item_collected_port", this);
    endfunction
    
    function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        
        if (get_is_active() == UVM_ACTIVE) begin
            driver = my_driver::type_id::create("driver", this);
            sequencer = my_sequencer::type_id::create("sequencer", this);
        end
        
        monitor = my_monitor::type_id::create("monitor", this);
    endfunction
    
    function void connect_phase(uvm_phase phase);
        super.connect_phase(phase);
        
        if (get_is_active() == UVM_ACTIVE) begin
            driver.seq_item_port.connect(sequencer.seq_item_export);
        end
        
        monitor.item_collected_port.connect(item_collected_port);
    endfunction
endclass
""",
    }

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, model_name: Optional[str] = None, device: Optional[str] = None):
        if self._initialized:
            return

        if model_name:
            self._model_name = model_name
        if device:
            self._device = device

        self._initialized = False
        self._model = None
        self._tokenizer = None
        self._detect_llm_type()

    def _detect_llm_type(self):
        name_lower = self._model_name.lower()
        if "codegen" in name_lower:
            self._llm_type = LLMType.CODEGEN
        elif "codet5" in name_lower:
            self._llm_type = LLMType.CODET5
        elif "codebert" in name_lower:
            self._llm_type = LLMType.CODEBERT
        elif "starcoder" in name_lower or "starcoder" in name_lower:
            self._llm_type = LLMType.STARCODER
        elif "llama" in name_lower:
            self._llm_type = LLMType.LLAMA
        elif "mistral" in name_lower:
            self._llm_type = LLMType.MISTRAL
        else:
            self._llm_type = LLMType.FALLBACK

    def _load_model(self):
        if self._initialized and self._model is not None:
            return

        if self._llm_type == LLMType.FALLBACK:
            logger.info("LLMCodeGenerator using fallback mode (template-based)")
            self._initialized = True
            return

        try:
            import torch
            from transformers import AutoTokenizer, AutoModelForCausalLM, AutoModelForSeq2SeqLM

            if self._device == "auto":
                self._device = "cuda" if torch.cuda.is_available() else "cpu"

            logger.info("Loading LLM: %s on %s", self._model_name, self._device)

            self._tokenizer = AutoTokenizer.from_pretrained(self._model_name)

            if self._llm_type == LLMType.CODET5:
                self._model = AutoModelForSeq2SeqLM.from_pretrained(
                    self._model_name,
                    torch_dtype=torch.float16 if self._device == "cuda" else torch.float32,
                )
            else:
                self._model = AutoModelForCausalLM.from_pretrained(
                    self._model_name,
                    torch_dtype=torch.float16 if self._device == "cuda" else torch.float32,
                )

            self._model.to(self._device)
            self._model.eval()

            if self._tokenizer.pad_token is None:
                self._tokenizer.pad_token = self._tokenizer.eos_token

            self._initialized = True
            logger.info("LLM loaded successfully")

        except ImportError as e:
            logger.warning(
                "Could not load LLM (missing dependencies: %s). Using fallback mode.",
                e,
            )
            self._llm_type = LLMType.FALLBACK
            self._initialized = True
        except Exception as e:
            logger.warning(
                "Could not load LLM (%s). Using fallback mode.",
                e,
            )
            self._llm_type = LLMType.FALLBACK
            self._initialized = True

    def is_available(self) -> bool:
        self._load_model()
        return self._initialized and self._llm_type != LLMType.FALLBACK

    def _spec_to_text(self, spec_dict: Dict[str, Any]) -> str:
        lines = []

        if "design_name" in spec_dict:
            lines.append(f"Design Name: {spec_dict['design_name']}")

        if "protocol" in spec_dict:
            lines.append(f"Protocol: {spec_dict['protocol']}")

        if "signals" in spec_dict:
            lines.append("\nSignals:")
            for sig in spec_dict["signals"]:
                name = sig.get("name", "unknown")
                direction = sig.get("direction", "inout")
                width = sig.get("width", 1)
                desc = sig.get("description", "")
                lines.append(f"  - {name}: {direction}, width={width} {desc}")

        if "registers" in spec_dict:
            lines.append("\nRegisters:")
            for reg in spec_dict["registers"]:
                name = reg.get("name", "unknown")
                addr = reg.get("address", "0x0")
                width = reg.get("width", 32)
                lines.append(f"  - {name}: addr={addr}, width={width}")

        if "features" in spec_dict:
            lines.append("\nFeatures:")
            for feat in spec_dict["features"]:
                lines.append(f"  - {feat}")

        return "\n".join(lines)

    def _build_prompt(
        self,
        spec_dict: Dict[str, Any],
        file_type: str,
        use_few_shot: bool = True,
    ) -> str:
        spec_text = self._spec_to_text(spec_dict)

        context_examples = ""
        if use_few_shot and file_type in self.FEW_SHOT_EXAMPLES:
            context_examples = self.FEW_SHOT_EXAMPLES[file_type]

        prompt = self.UVM_PROMPT_TEMPLATE.format(
            spec_text=spec_text,
            file_type=file_type,
            context_examples=context_examples,
        )

        return prompt.strip()

    def _extract_code(self, text: str) -> str:
        code_block_patterns = [
            r"```systemverilog\s+(.*?)```",
            r"```verilog\s+(.*?)```",
            r"```sv\s+(.*?)```",
            r"```\s+(.*?)```",
        ]

        for pattern in code_block_patterns:
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return text.strip()

    def _fallback_generate(
        self,
        spec_dict: Dict[str, Any],
        file_type: str,
        templates: Optional[Dict[str, str]] = None,
    ) -> LLMGenerationResult:
        design_name = spec_dict.get("design_name", "unknown").lower()

        fallback_templates = {
            "driver": f"""
class {design_name}_driver extends uvm_driver #({design_name}_seq_item);
    `uvm_component_utils({design_name}_driver)
    
    virtual {design_name}_if vif;
    
    function new(string name = "{design_name}_driver", uvm_component parent = null);
        super.new(name, parent);
    endfunction
    
    function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        if (!uvm_config_db#(virtual {design_name}_if)::get(this, "", "vif", vif))
            `uvm_fatal(get_type_name(), "Virtual interface not found in config DB")
    endfunction
    
    task run_phase(uvm_phase phase);
        forever begin
            seq_item_port.get_next_item(req);
            drive_item(req);
            seq_item_port.item_done();
        end
    endtask
    
    task drive_item({design_name}_seq_item item);
        // Implement drive logic based on item
        @(posedge vif.clk);
    endtask
endclass
""",
            "monitor": f"""
class {design_name}_monitor extends uvm_monitor;
    `uvm_component_utils({design_name}_monitor)
    
    uvm_analysis_port #({design_name}_seq_item) item_collected_port;
    virtual {design_name}_if vif;
    
    function new(string name = "{design_name}_monitor", uvm_component parent = null);
        super.new(name, parent);
        item_collected_port = new("item_collected_port", this);
    endfunction
    
    function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        if (!uvm_config_db#(virtual {design_name}_if)::get(this, "", "vif", vif))
            `uvm_fatal(get_type_name(), "Virtual interface not found in config DB")
    endfunction
    
    task run_phase(uvm_phase phase);
        {design_name}_seq_item item;
        forever begin
            @(posedge vif.clk);
            // Sample signals and create item
        end
    endtask
endclass
""",
            "agent": f"""
class {design_name}_agent extends uvm_agent;
    `uvm_component_utils({design_name}_agent)
    
    {design_name}_driver driver;
    {design_name}_monitor monitor;
    {design_name}_sequencer sequencer;
    uvm_analysis_port #({design_name}_seq_item) item_collected_port;
    
    function new(string name = "{design_name}_agent", uvm_component parent = null);
        super.new(name, parent);
        item_collected_port = new("item_collected_port", this);
    endfunction
    
    function void build_phase(uvm_phase phase);
        super.build_phase(phase);
        
        if (get_is_active() == UVM_ACTIVE) begin
            driver = {design_name}_driver::type_id::create("driver", this);
            sequencer = {design_name}_sequencer::type_id::create("sequencer", this);
        end
        
        monitor = {design_name}_monitor::type_id::create("monitor", this);
    endfunction
    
    function void connect_phase(uvm_phase phase);
        super.connect_phase(phase);
        
        if (get_is_active() == UVM_ACTIVE) begin
            driver.seq_item_port.connect(sequencer.seq_item_export);
        end
        
        monitor.item_collected_port.connect(item_collected_port);
    endfunction
endclass
""",
        }

        if templates and file_type in templates:
            code = templates[file_type]
        elif file_type in fallback_templates:
            code = fallback_templates[file_type]
        else:
            code = f"// {file_type} for {design_name} - template placeholder"

        return LLMGenerationResult(
            generated_code=code,
            prompt_used=f"// Fallback generation for {file_type}",
            model_name="fallback_template",
            tokens_generated=len(code.split()),
            confidence=0.3,
            warnings=["Using fallback template generation (LLM not available)"],
        )

    def generate(
        self,
        spec_dict: Dict[str, Any],
        file_type: str,
        use_few_shot: bool = True,
        max_tokens: int = 1024,
        temperature: float = 0.2,
        templates: Optional[Dict[str, str]] = None,
    ) -> LLMGenerationResult:
        self._load_model()

        prompt = self._build_prompt(spec_dict, file_type, use_few_shot)

        if self._llm_type == LLMType.FALLBACK or self._model is None:
            return self._fallback_generate(spec_dict, file_type, templates)

        try:
            import torch

            inputs = self._tokenizer(
                prompt,
                return_tensors="pt",
                truncation=True,
                max_length=1024,
                padding=True,
            )
            inputs = {k: v.to(self._device) for k, v in inputs.items()}

            with torch.no_grad():
                if self._llm_type == LLMType.CODET5:
                    outputs = self._model.generate(
                        **inputs,
                        max_new_tokens=max_tokens,
                        temperature=temperature,
                        do_sample=temperature > 0,
                        num_return_sequences=1,
                        pad_token_id=self._tokenizer.pad_token_id,
                        eos_token_id=self._tokenizer.eos_token_id,
                    )
                else:
                    outputs = self._model.generate(
                        **inputs,
                        max_new_tokens=max_tokens,
                        temperature=temperature,
                        do_sample=temperature > 0,
                        num_return_sequences=1,
                        pad_token_id=self._tokenizer.pad_token_id,
                        eos_token_id=self._tokenizer.eos_token_id,
                    )

            generated_text = self._tokenizer.decode(outputs[0], skip_special_tokens=True)

            if generated_text.startswith(prompt):
                generated_text = generated_text[len(prompt) :].strip()

            code = self._extract_code(generated_text)
            tokens_generated = len(outputs[0]) - inputs["input_ids"].shape[1]

            confidence = 0.7
            if "uvm_component_utils" in code or "uvm_object_utils" in code:
                confidence += 0.1
            if "class" in code and "extends" in code:
                confidence += 0.05
            if "build_phase" in code or "run_phase" in code:
                confidence += 0.05
            if "endclass" in code:
                confidence += 0.05

            confidence = min(confidence, 0.95)

            return LLMGenerationResult(
                generated_code=code,
                prompt_used=prompt,
                model_name=self._model_name,
                tokens_generated=tokens_generated,
                confidence=confidence,
                warnings=[],
            )

        except Exception as e:
            logger.warning("Error during LLM generation: %s. Using fallback.", e)
            result = self._fallback_generate(spec_dict, file_type, templates)
            result.warnings.append(f"LLM generation failed: {str(e)}")
            return result

    def generate_batch(
        self,
        spec_dict: Dict[str, Any],
        file_types: List[str],
        use_few_shot: bool = True,
        max_tokens: int = 1024,
        temperature: float = 0.2,
        templates: Optional[Dict[str, str]] = None,
    ) -> Dict[str, LLMGenerationResult]:
        results = {}

        for file_type in file_types:
            results[file_type] = self.generate(
                spec_dict=spec_dict,
                file_type=file_type,
                use_few_shot=use_few_shot,
                max_tokens=max_tokens,
                temperature=temperature,
                templates=templates.get(file_type) if templates else None,
            )

        return results
