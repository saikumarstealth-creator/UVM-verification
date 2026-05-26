# tests/test_pipeline.py — Integration test for the full ML pipeline

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import yaml

# Ensure src is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import DesignSpec, ConfigLoader, PipelineConfig
from src.data.validators import SpecValidator
from src.data.preprocessor import SpecPreprocessor
from src.features.extractors import SpecFeatureExtractor
from src.models.template_model import TemplateModel
from src.generation.engine import GenerationEngine
from src.pipeline import TBPipeline


DEMO_SPEC = {
    "design_name": "uart",
    "clock_reset": {"clock": "clk", "reset": "rst_n", "reset_active": 0},
    "interfaces": [{
        "name": "uart_if",
        "signals": [
            {"name": "tx", "direction": "output"},
            {"name": "rx", "direction": "input"},
            {"name": "baud_tick", "direction": "input"},
        ],
    }],
    "registers": [
        {"name": "ctrl", "address": "0x00", "fields": [
            {"name": "enable", "bits": "0"},
            {"name": "baud_div", "bits": "7:2"},
        ]},
        {"name": "status", "address": "0x04", "fields": [
            {"name": "tx_full", "bits": "0"},
            {"name": "rx_empty", "bits": "1"},
        ]},
    ],
}

SIMILAR_UART_SPEC = {
    "design_name": "uart2",
    "clock_reset": {"clock": "clk", "reset": "rst_n", "reset_active": 0},
    "interfaces": [{
        "name": "uart_if2",
        "signals": [
            {"name": "tx", "direction": "output"},
            {"name": "rx", "direction": "input"},
            {"name": "baud_tick", "direction": "input"},
        ],
    }],
    "registers": [
        {"name": "ctrl", "address": "0x00", "fields": [
            {"name": "enable", "bits": "0"},
            {"name": "baud_div", "bits": "7:2"},
        ]},
        {"name": "status", "address": "0x04", "fields": [
            {"name": "tx_full", "bits": "0"},
            {"name": "rx_empty", "bits": "1"},
        ]},
        {"name": "divisor", "address": "0x08", "fields": [
            {"name": "div", "bits": "15:0"},
        ]},
    ],
}


def test_design_spec_validation():
    spec = DesignSpec(**DEMO_SPEC)
    validator = SpecValidator()
    result = validator.validate(spec, strict=True)
    assert result.is_valid, f"Validation failed: {result}"


def test_preprocessor():
    pre = SpecPreprocessor()
    processed = pre.preprocess(dict(DEMO_SPEC))
    assert processed["design_name"] == "uart"
    assert "clock_reset" in processed


def test_feature_extraction():
    spec = DesignSpec(**DEMO_SPEC)
    extractor = SpecFeatureExtractor()
    features = extractor.extract(spec)
    assert features.interface_count == 1
    assert features.total_signals == 3
    assert features.register_count == 2
    assert features.total_fields == 4
    assert features.protocol_type == "uart"


def test_template_model_train_predict():
    spec = DesignSpec(**DEMO_SPEC)
    model = TemplateModel(templates_dir="src/generation/templates")
    meta = model.train([spec])
    assert model.is_trained
    assert meta["template_count"] >= 5

    cfg = PipelineConfig()
    with tempfile.TemporaryDirectory() as tmp:
        cfg.generation.output_dir = tmp
        result = model.predict(spec, cfg)
        assert len(result) >= 5
        assert any("testbench.sv" in k for k in result)


def test_generation_engine():
    spec = DesignSpec(**DEMO_SPEC)
    model = TemplateModel(templates_dir="src/generation/templates")
    model.train([spec])
    engine = GenerationEngine(model)
    cfg = PipelineConfig()
    with tempfile.TemporaryDirectory() as tmp:
        cfg.generation.output_dir = tmp
        result = engine.generate(spec, cfg)
        assert len(result) >= 5


def test_pipeline_e2e():
    with tempfile.TemporaryDirectory() as tmp:
        spec_path = Path(tmp) / "test_spec.yaml"
        with open(spec_path, "w") as f:
            yaml.dump(DEMO_SPEC, f)

        pipeline = TBPipeline()
        pipeline.cfg.generation.output_dir = tmp
        pipeline.cfg.tracking.enabled = False
        pipeline.cfg.evaluation.threshold = 0.5

        result = pipeline.run(str(spec_path))
        assert result["passed"]
        assert result["design_name"] == "uart"
        assert len(result["generated_files"]) >= 5
        assert "completeness" in result["evaluation"]


def test_core_file_parsing():
    """Test that a .core file is parsed correctly into a DesignSpec."""
    core_content = """
name: uart16550
version: "1.5"
clock_reset:
  clock: clk
  reset: rstn
  reset_active: 0
interfaces:
  - name: bus
    signals:
      - {name: clk, direction: input, width: 1}
      - {name: rstn, direction: input, width: 1}
      - {name: addr, direction: input, width: 3}
      - {name: data_in, direction: input, width: 8}
      - {name: data_out, direction: output, width: 8}
      - {name: irq, direction: output, width: 1}
registers:
  - name: IER
    address: '0x01'
    access: rw
    fields:
      - {name: erbfi, bits: '0', description: Enable RX interrupt}
      - {name: etbei, bits: '1', description: Enable TX interrupt}
  - name: LCR
    address: '0x03'
    access: rw
    fields:
      - {name: wls, bits: '1:0', description: Word length}
      - {name: dlab, bits: '7', description: Divisor latch bit}
"""
    from src.data.core_parser import CoreParser
    from src.config import DesignSpec

    parser = CoreParser()
    parsed = parser.parse(core_content)
    spec = DesignSpec(**parsed)

    assert spec.design_name == "uart16550"
    assert len(spec.interfaces) == 1
    assert spec.interfaces[0].name == "bus"
    assert len(spec.interfaces[0].signals) == 6
    assert len(spec.registers) == 2
    assert spec.registers[0].name == "IER"
    assert spec.registers[0].address == "0x01"
    assert len(spec.registers[0].fields) == 2
    assert spec.clock_reset.clock == "clk"
    assert spec.clock_reset.reset == "rstn"


def test_core_file_pipeline():
    """End-to-end: .core file through the full pipeline."""
    core_content = """
name: uart16550
version: "1.5"
clock_reset:
  clock: clk
  reset: rstn
  reset_active: 0
interfaces:
  - name: bus
    signals:
      - {name: addr, direction: input}
      - {name: data_in, direction: input}
      - {name: data_out, direction: output}
registers:
  - name: LSR
    address: '0x05'
    access: ro
    fields:
      - {name: dr, bits: '0'}
      - {name: thre, bits: '5'}
"""
    from src.pipeline import TBPipeline

    with tempfile.TemporaryDirectory() as tmp:
        core_path = Path(tmp) / "uart16550-1.5.core"
        core_path.write_text(core_content)

        pipeline = TBPipeline()
        pipeline.cfg.generation.output_dir = tmp
        pipeline.cfg.tracking.enabled = False
        pipeline.cfg.evaluation.threshold = 0.0

        result = pipeline.run(str(core_path))
        assert result["passed"]
        assert result["design_name"] == "uart16550"
        assert len(result["generated_files"]) >= 5


def test_rich_feature_extraction():
    """Test rich feature extraction for ML similarity."""
    from src.features.extractors import RichSpecFeatureExtractor
    from src.models.ml_utils import RichFeatureVector

    spec = DesignSpec(**DEMO_SPEC)
    extractor = RichSpecFeatureExtractor()
    fv = extractor.extract(spec)

    assert isinstance(fv, RichFeatureVector)
    assert fv.design_name == "uart"
    assert fv.interface_count == 1
    assert fv.total_signals == 3
    assert fv.register_count == 2
    assert "tx" in fv.signal_names
    assert "rx" in fv.signal_names
    assert "ctrl" in fv.register_names
    assert "status" in fv.register_names
    assert fv.protocol_type == "uart"

    fp = fv.fingerprint()
    assert len(fp) == 16
    assert isinstance(fp, str)


def test_similarity_index():
    """Test similarity index for spec retrieval."""
    from src.features.extractors import RichSpecFeatureExtractor
    from src.models.similarity_index import SimilarityIndex

    spec1 = DesignSpec(**DEMO_SPEC)
    spec2 = DesignSpec(**SIMILAR_UART_SPEC)

    extractor = RichSpecFeatureExtractor()
    fv1 = extractor.extract(spec1)
    fv2 = extractor.extract(spec2)

    index = SimilarityIndex()
    assert len(index) == 0

    index.add(fv1, DEMO_SPEC)
    assert len(index) == 1

    index.add(fv2, SIMILAR_UART_SPEC)
    assert len(index) == 2

    results = index.search(fv1, top_k=2)
    assert len(results) >= 1
    assert results[0].similarity >= 0.5
    assert results[0].protocol_type == "uart"

    fp = fv1.fingerprint()
    entry = index.get(fp)
    assert entry is not None
    assert entry.design_name == "uart"


def test_ml_model_config():
    """Test ML generation model configuration."""
    from src.models.ml_generation_model import MLModelConfig

    cfg = MLModelConfig()
    assert cfg.similarity_threshold == 0.75
    assert cfg.fallback_to_templates is True
    assert cfg.auto_learn is True
    assert cfg.top_k_retrieval == 3

    cfg2 = MLModelConfig(
        similarity_threshold=0.85,
        auto_learn=False,
    )
    assert cfg2.similarity_threshold == 0.85
    assert cfg2.auto_learn is False


def test_ml_generation_model():
    """Test ML generation model train/predict."""
    from src.models.ml_generation_model import MLGenerationModel
    from src.config import PipelineConfig

    spec = DesignSpec(**DEMO_SPEC)
    model = MLGenerationModel(templates_dir="src/generation/templates")

    assert not model.is_trained
    meta = model.train([spec])
    assert model.is_trained
    assert "index_size" in meta

    cfg = PipelineConfig()
    with tempfile.TemporaryDirectory() as tmp:
        cfg.generation.output_dir = tmp
        result = model.predict(spec, cfg)
        assert len(result) >= 5
        assert any("testbench.sv" in k for k in result)

        retrieval = model.last_retrieval
        assert retrieval is not None
        assert isinstance(retrieval.used_similarity, bool)


def test_combined_similarity():
    """Test combined similarity metric."""
    from src.features.extractors import RichSpecFeatureExtractor
    from src.models.ml_utils import combined_similarity

    spec1 = DesignSpec(**DEMO_SPEC)
    spec2 = DesignSpec(**SIMILAR_UART_SPEC)

    extractor = RichSpecFeatureExtractor()
    fv1 = extractor.extract(spec1)
    fv2 = extractor.extract(spec2)

    sim = combined_similarity(fv1, fv2)
    assert 0.0 <= sim <= 1.0
    assert sim > 0.5

    self_sim = combined_similarity(fv1, fv1)
    assert self_sim == 1.0


def test_pipeline_ml_mode():
    """Test pipeline with ML mode enabled."""
    with tempfile.TemporaryDirectory() as tmp:
        spec_path = Path(tmp) / "test_spec.yaml"
        with open(spec_path, "w") as f:
            yaml.dump(DEMO_SPEC, f)

        pipeline = TBPipeline()
        pipeline.cfg.generation.output_dir = tmp
        pipeline.cfg.tracking.enabled = False
        pipeline.cfg.evaluation.threshold = 0.5

        pipeline.cfg.ml.enabled = True
        pipeline.cfg.ml.model_type = "hybrid"
        pipeline.cfg.ml.similarity_threshold = 0.6

        model = pipeline._create_model()
        assert model is not None

        from src.models.ml_generation_model import MLGenerationModel
        assert isinstance(model, MLGenerationModel)

        result = pipeline.run(str(spec_path))
        assert result["passed"]
        assert result["design_name"] == "uart"
        assert len(result["generated_files"]) >= 5
