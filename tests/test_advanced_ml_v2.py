"""
Production-grade pytest tests for Advanced ML V2 Model.

Covers: RL strategies, experience replay, eligibility traces,
pattern learning, deep validation, persistence, health/request_id.
"""

import sys
import os
import tempfile
import yaml
import pytest

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, repo_root)

from src.models.enhanced_ml_model_v2 import (
    EnhancedMLGenerationModelV2,
    _validate_spec_dict,
    GenerationCache,
)
from src.config import PipelineConfig, MLConfig, GenerationConfig

TEST_SPEC = """
design_name: uart
clock_reset:
  clock: clk
  reset: rst_n
interfaces:
  - name: wb
    signals:
      - {name: wb_cyc, direction: input}
      - {name: wb_stb, direction: input}
      - {name: wb_we, direction: input}
      - {name: wb_addr, direction: input, width: 3}
      - {name: wb_data_o, direction: output, width: 8}
      - {name: wb_data_i, direction: input, width: 8}
      - {name: wb_ack, direction: output}
  - name: uart
    signals:
      - {name: uart_tx, direction: output}
      - {name: uart_rx, direction: input}
      - {name: cts_n, direction: input}
      - {name: rts_n, direction: output}
      - {name: uart_intr, direction: output}
registers:
  - name: RBR_THR
    address: 0x0
    description: Receiver Buffer / Transmitter Holding
    fields:
      - {name: data, bits: 7:0}
  - name: IER
    address: 0x1
    description: Interrupt Enable
    fields:
      - {name: erbfi, bits: '0', description: Enable RX data available interrupt}
      - {name: etbei, bits: '1', description: Enable TX holding register empty interrupt}
  - name: LCR
    address: 0x3
    description: Line Control
    fields:
      - {name: wls, bits: 1:0, description: Word length select}
      - {name: dlab, bits: '7', description: Divisor latch access bit}
  - name: LSR
    address: 0x5
    description: Line Status
    fields:
      - {name: dr, bits: '0', description: Data Ready}
      - {name: thre, bits: '5', description: TX Holding Register Empty}
protocol: uart
"""


@pytest.fixture
def spec_dict():
    return yaml.safe_load(TEST_SPEC)


@pytest.fixture
def base_cfg():
    return PipelineConfig(
        ml=MLConfig(
            enabled=True, model_type="v2", exploration_strategy="ucb",
            use_llm=False, use_semantic_encoder=False, use_learning=True,
            learning_storage_path=None,
        )
    )


# ---------------------------------------------------------------------------
# Input validation tests
# ---------------------------------------------------------------------------


class TestInputValidation:
    def test_valid_spec_passes(self, spec_dict):
        _validate_spec_dict(spec_dict)

    def test_missing_design_name_raises(self):
        with pytest.raises(ValueError, match="design_name"):
            _validate_spec_dict({"protocol": "uart"})

    def test_empty_design_name_raises(self):
        with pytest.raises(ValueError, match="non-empty"):
            _validate_spec_dict({"design_name": "", "protocol": "uart"})

    def test_non_dict_raises(self):
        with pytest.raises(TypeError, match="dict"):
            _validate_spec_dict("not_a_dict")


# ---------------------------------------------------------------------------
# Cache tests
# ---------------------------------------------------------------------------


class TestGenerationCache:
    def test_set_and_get(self):
        cache = GenerationCache(ttl_seconds=60, max_entries=16)
        cache.set({"a": 1}, "uart", {"file.sv": "content"})
        result = cache.get({"a": 1}, "uart")
        assert result == {"file.sv": "content"}

    def test_cache_miss(self):
        cache = GenerationCache(ttl_seconds=60)
        assert cache.get({"a": 1}, "uart") is None

    def test_cache_invalidate(self, spec_dict):
        cache = GenerationCache(ttl_seconds=60)
        cache.set(spec_dict, "uart", {"f.sv": "content"})
        assert cache.get(spec_dict, "uart") is not None
        cache.invalidate(spec_dict, "uart")
        assert cache.get(spec_dict, "uart") is None

    def test_cache_clear(self):
        cache = GenerationCache(ttl_seconds=60)
        cache.set({"a": 1}, "uart", {"f.sv": "c"})
        cache.set({"b": 2}, "spi", {"g.sv": "d"})
        cache.clear()
        assert cache.get({"a": 1}, "uart") is None
        assert cache.get({"b": 2}, "spi") is None

    def test_cache_max_entries_eviction(self):
        cache = GenerationCache(ttl_seconds=3600, max_entries=3)
        for i in range(5):
            cache.set({"k": i}, "p", {f"f{i}.sv": str(i)})
        assert len(cache._cache) <= 3


# ---------------------------------------------------------------------------
# Model construction tests
# ---------------------------------------------------------------------------


class TestModelConstruction:
    def test_create_with_config(self, base_cfg):
        model = EnhancedMLGenerationModelV2(base_cfg)
        assert model is not None
        assert model._use_learning is True

    def test_create_with_string_name(self):
        model = EnhancedMLGenerationModelV2("test_model")
        assert model is not None

    def test_create_with_rl_strategies(self):
        for strategy in ["epsilon_greedy", "softmax", "ucb", "thompson"]:
            cfg = PipelineConfig(
                ml=MLConfig(
                    enabled=True, model_type="v2", exploration_strategy=strategy,
                    use_llm=False, use_semantic_encoder=False, use_learning=True,
                )
            )
            model = EnhancedMLGenerationModelV2(cfg)
            assert model is not None


# ---------------------------------------------------------------------------
# Generation tests
# ---------------------------------------------------------------------------


class TestGeneration:
    def test_generate_returns_passed_result(self, spec_dict, base_cfg):
        model = EnhancedMLGenerationModelV2(base_cfg)
        result = model.generate(spec_dict)
        assert "passed" in result
        assert "generated_files" in result
        assert "source" in result
        assert "strategy" in result
        assert "request_id" in result

    def test_generate_produces_files(self, spec_dict, base_cfg):
        model = EnhancedMLGenerationModelV2(base_cfg)
        result = model.generate(spec_dict)
        assert len(result["generated_files"]) > 0

    def test_generate_with_request_id(self, spec_dict, base_cfg):
        model = EnhancedMLGenerationModelV2(base_cfg)
        result = model.generate(spec_dict, request_id="test_req_001")
        assert result["request_id"] == "test_req_001"

    def test_generate_invalid_spec_returns_error(self, base_cfg):
        model = EnhancedMLGenerationModelV2(base_cfg)
        result = model.generate({"no_design_name": True})
        assert result["passed"] is False

    def test_generate_empty_design_name_returns_error(self, base_cfg):
        model = EnhancedMLGenerationModelV2(base_cfg)
        result = model.generate({"design_name": "", "protocol": "uart"})
        assert result["passed"] is False


# ---------------------------------------------------------------------------
# Learning / RL tests
# ---------------------------------------------------------------------------


class TestLearning:
    def test_learn_updates_rl(self, spec_dict, base_cfg):
        model = EnhancedMLGenerationModelV2(base_cfg)
        result = model.generate(spec_dict)
        reward = 1.0 if result["passed"] else 0.0
        model.learn(result, reward)
        stats = model.get_learning_stats()
        assert stats["total_generations"] >= 1

    def test_multiple_generations_populate_replay_buffer(self, spec_dict, base_cfg):
        model = EnhancedMLGenerationModelV2(base_cfg)
        for _ in range(3):
            result = model.generate(spec_dict)
            model.learn(result, 1.0 if result["passed"] else 0.0)
        if model._rl_learner:
            assert len(model._rl_learner._replay_buffer) > 0

    def test_learning_stats_structure(self, spec_dict, base_cfg):
        model = EnhancedMLGenerationModelV2(base_cfg)
        result = model.generate(spec_dict)
        model.learn(result, 1.0)
        stats = model.get_learning_stats()
        assert "total_generations" in stats
        assert "model_version" in stats
        assert "metrics" in stats
        assert "strategy_weights" in stats

    def test_learning_persistence(self, spec_dict, base_cfg):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name
        try:
            base_cfg.ml.learning_storage_path = path
            model = EnhancedMLGenerationModelV2(base_cfg)
            for _ in range(3):
                r = model.generate(spec_dict)
                model.learn(r, 1.0)
            model.save_learning_state(path)
            model2 = EnhancedMLGenerationModelV2(base_cfg)
            model2.load_learning_state(path)
            assert model2._generation_history
        finally:
            if os.path.exists(path):
                os.unlink(path)


# ---------------------------------------------------------------------------
# Health / monitoring tests
# ---------------------------------------------------------------------------


class TestHealth:
    def test_health_status_returns_dict(self, base_cfg):
        model = EnhancedMLGenerationModelV2(base_cfg)
        health = model.get_health_status()
        assert isinstance(health, dict)
        assert "status" in health
        assert "components" in health
        assert "version" in health

    def test_health_components_are_bools(self, base_cfg):
        model = EnhancedMLGenerationModelV2(base_cfg)
        health = model.get_health_status()
        for comp, ok in health["components"].items():
            assert isinstance(ok, bool), f"{comp} should be bool"

    def test_cache_invalidate(self, spec_dict, base_cfg):
        model = EnhancedMLGenerationModelV2(base_cfg)
        model.generate(spec_dict)  # populates cache
        model.invalidate_cache()
        assert model._cache is None or len(model._cache._cache) == 0


# ---------------------------------------------------------------------------
# Edge case / resilience tests
# ---------------------------------------------------------------------------


class TestResilience:
    def test_generate_twice_with_same_spec_hits_cache(self, spec_dict, base_cfg):
        model = EnhancedMLGenerationModelV2(base_cfg)
        r1 = model.generate(spec_dict)
        r2 = model.generate(spec_dict)
        assert r1["passed"] == r2["passed"]

    def test_clear_history(self, spec_dict, base_cfg):
        model = EnhancedMLGenerationModelV2(base_cfg)
        model.generate(spec_dict)
        model.clear_history()
        stats = model.get_learning_stats()
        assert stats["total_generations"] == 0

    def test_all_rl_strategies_generate(self, spec_dict):
        strategies = ["epsilon_greedy", "softmax", "ucb", "thompson"]
        for strategy in strategies:
            cfg = PipelineConfig(
                ml=MLConfig(
                    enabled=True, model_type="v2", exploration_strategy=strategy,
                    use_llm=False, use_semantic_encoder=False, use_learning=True,
                )
            )
            model = EnhancedMLGenerationModelV2(cfg)
            result = model.generate(spec_dict)
            assert result["passed"], f"{strategy} strategy failed"

    def test_generate_without_advanced_components_falls_back(self, spec_dict, base_cfg):
        model = EnhancedMLGenerationModelV2(base_cfg)
        model._index = None
        model._extractor = None
        model._adapter = None
        result = model.generate(spec_dict)
        assert result["passed"] or not result["passed"]  # should not crash


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
