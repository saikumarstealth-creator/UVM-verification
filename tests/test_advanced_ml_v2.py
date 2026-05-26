"""
Test script for Advanced ML V2 Model
Tests: RL strategies, experience replay, eligibility traces, pattern learning, deep validation
"""

import sys
import os
import tempfile
import yaml

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, repo_root)

from src.models.enhanced_ml_model_v2 import EnhancedMLGenerationModelV2
from src.config import PipelineConfig, MLConfig, AutoTrainConfig, GenerationConfig

TEST_SPEC = """
design_name: uart
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

protocol: uart
"""

def test_rl_strategies():
    """Test all RL exploration strategies."""
    print("\n" + "="*60)
    print("Testing RL Exploration Strategies")
    print("="*60)
    
    strategies = ["epsilon_greedy", "softmax", "ucb", "thompson"]
    results = {}
    
    for strategy in strategies:
        print(f"\n--- Testing {strategy} strategy ---")
        
        cfg = PipelineConfig(
            ml=MLConfig(
                enabled=True,
                model_type="v2",
                exploration_strategy=strategy,
                use_llm=False,
                use_semantic_encoder=False,
                use_learning=True,
                learning_storage_path=None
            )
        )
        
        model = EnhancedMLGenerationModelV2(cfg)
        
        spec_dict = yaml.safe_load(TEST_SPEC)
        
        result = model.generate(spec_dict)
        passed = result['passed']
        generated_files = result.get('generated_files', {})
        
        print(f"  Passed: {passed}")
        print(f"  Files generated: {len(generated_files)}")
        print(f"  Source: {result.get('source', 'unknown')}")
        print(f"  Strategy used: {result.get('strategy', 'unknown')}")
        
        if hasattr(model, '_rl_learner'):
            rl_stats = model._rl_learner.get_performance_stats()
            print(f"  RL episodes: {rl_stats.get('episode_count', 0)}")
            print(f"  RL total updates: {rl_stats.get('total_updates', 0)}")
        
        results[strategy] = {
            "passed": passed,
            "files_count": len(generated_files),
            "source": result.get('source', 'unknown'),
            "strategy": result.get('strategy', 'unknown')
        }
    
    print("\n--- Strategy Results Summary ---")
    for strategy, res in results.items():
        status = "✅" if res["passed"] else "❌"
        print(f"  {status} {strategy}: {res['files_count']} files, source={res['source']}, strategy={res['strategy']}")
    
    return all(r["passed"] for r in results.values())

def test_experience_replay():
    """Test experience replay buffer and eligibility traces."""
    print("\n" + "="*60)
    print("Testing Experience Replay & Eligibility Traces")
    print("="*60)
    
    cfg = PipelineConfig(
        ml=MLConfig(
            enabled=True,
            model_type="v2",
            exploration_strategy="ucb",
            use_llm=False,
            use_semantic_encoder=False,
            use_learning=True,
            learning_storage_path=None
        )
    )
    
    model = EnhancedMLGenerationModelV2(cfg)
    spec_dict = yaml.safe_load(TEST_SPEC)
    
    print("  Running multiple generations to populate replay buffer...")
    
    for i in range(5):
        result = model.generate(spec_dict)
        print(f"    Generation {i+1}: passed={result['passed']}, source={result.get('source', 'unknown')}")
        
        reward = 1.0 if result['passed'] else 0.0
        model.learn(result, reward)
    
    if hasattr(model, '_rl_learner'):
        rl = model._rl_learner
        
        print(f"\n  Experience replay buffer size: {len(rl._replay_buffer)}")
        print(f"  Episode count: {rl.get_performance_stats().get('episode_count', 0)}")
        
        if hasattr(rl, '_eligibility_traces') and rl._eligibility_traces:
            print(f"  Eligibility traces tracked: {len(rl._eligibility_traces)}")
        
        state_stats = rl.get_state_stats()
        print(f"\n  State statistics (first 3):")
        for state, stats in list(state_stats.items())[:3]:
            print(f"    '{state}': best_action='{stats.get('best_action', 'N/A')}', Q={stats.get('best_q_value', 0):.3f}, visits={stats.get('visit_count', 0)}")
        
        return len(rl._replay_buffer) > 0
    
    return False

def test_pattern_learner():
    """Test advanced pattern learning."""
    print("\n" + "="*60)
    print("Testing Advanced Pattern Learner")
    print("="*60)
    
    cfg = PipelineConfig(
        ml=MLConfig(
            enabled=True,
            model_type="v2",
            exploration_strategy="ucb",
            use_llm=False,
            use_semantic_encoder=False,
            use_learning=True,
            learning_storage_path=None
        )
    )
    
    model = EnhancedMLGenerationModelV2(cfg)
    spec_dict = yaml.safe_load(TEST_SPEC)
    
    print("  Running generations for pattern learning...")
    
    for i in range(3):
        result = model.generate(spec_dict)
        reward = 1.0 if result['passed'] else 0.0
        model.learn(result, reward)
    
    if hasattr(model, '_pattern_learner'):
        pl = model._pattern_learner
        
        stats = pl.get_statistics()
        print(f"\n  Pattern Learner Stats:")
        print(f"    Total specs seen: {stats['total_specs_seen']}")
        print(f"    Total generations: {stats['total_generations']}")
        print(f"    Average score: {stats['avg_score']:.3f}")
        print(f"    N-gram vocabulary size: {len(stats['ngram_vocab'])}")
        print(f"    Association rules: {len(stats['association_rules'])}")
        
        recs = pl.get_recommendations(spec_dict)
        print(f"\n  Recommendations for current spec:")
        for rec in recs[:5]:
            print(f"    • {rec}")
        
        common = pl.get_common_error_patterns(top_n=5)
        if common:
            print(f"\n  Common error patterns:")
            for pattern, count in common:
                print(f"    • '{pattern}': {count} occurrences")
        
        return True
    
    return False

def test_deep_validation():
    """Test deep UVM compliance validation."""
    print("\n" + "="*60)
    print("Testing Deep UVM Compliance Validation")
    print("="*60)
    
    cfg = PipelineConfig(
        ml=MLConfig(
            enabled=True,
            model_type="v2",
            exploration_strategy="ucb",
            use_llm=False,
            use_semantic_encoder=False,
            use_learning=True,
            strict_validation=True,
            learning_storage_path=None
        )
    )
    
    model = EnhancedMLGenerationModelV2(cfg)
    spec_dict = yaml.safe_load(TEST_SPEC)
    
    result = model.generate(spec_dict)
    
    print(f"\n  Generated files: {len(result.get('generated_files', {}))}")
    print(f"  Passed: {result['passed']}")
    
    val_results = result.get('validation_results', {})
    
    if val_results:
        print(f"\n  Validation Results:")
        total_checks = 0
        total_passed = 0
        
        for file_path, file_result in val_results.items():
            file_name = os.path.basename(file_path)
            checks = file_result.get('checks', [])
            
            if checks:
                print(f"\n    {file_name}:")
                for check in checks:
                    total_checks += 1
                    status = "✅" if check.get('passed', False) else "❌"
                    if check.get('passed'):
                        total_passed += 1
                    
                    msg = f"      {status} {check.get('check_name', 'unknown')}"
                    if check.get('message'):
                        msg += f": {check['message']}"
                    print(msg)
        
        if total_checks > 0:
            pass_rate = (total_passed / total_checks) * 100
            print(f"\n  Overall validation pass rate: {pass_rate:.1f}% ({total_passed}/{total_checks})")
        
        return total_checks > 0
    
    return False

def test_learning_persistence():
    """Test saving and loading learning state."""
    print("\n" + "="*60)
    print("Testing Learning State Persistence")
    print("="*60)
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        state_path = f.name
    
    try:
        cfg = PipelineConfig(
            ml=MLConfig(
                enabled=True,
                model_type="v2",
                exploration_strategy="ucb",
                use_llm=False,
                use_semantic_encoder=False,
                use_learning=True,
                learning_storage_path=state_path
            )
        )
        
        print("  Creating model and running generations...")
        model = EnhancedMLGenerationModelV2(cfg)
        spec_dict = yaml.safe_load(TEST_SPEC)
        
        for i in range(3):
            result = model.generate(spec_dict)
            reward = 1.0 if result['passed'] else 0.0
            model.learn(result, reward)
        
        if hasattr(model, '_rl_learner'):
            episodes_before = model._rl_learner.get_performance_stats().get('episode_count', 0)
            replay_size_before = len(model._rl_learner._replay_buffer)
            print(f"  Episodes before save: {episodes_before}")
            print(f"  Replay buffer size before save: {replay_size_before}")
        
        print("  Saving learning state...")
        model.save_learning_state(state_path)
        
        print("  Loading learning state into new model...")
        model2 = EnhancedMLGenerationModelV2(cfg)
        model2.load_learning_state(state_path)
        
        if hasattr(model2, '_rl_learner'):
            episodes_after = model2._rl_learner.get_performance_stats().get('episode_count', 0)
            replay_size_after = len(model2._rl_learner._replay_buffer)
            print(f"  Episodes after load: {episodes_after}")
            print(f"  Replay buffer size after load: {replay_size_after}")
            
            return episodes_after >= 3 and replay_size_after >= 3
        
        return False
    
    finally:
        if os.path.exists(state_path):
            os.unlink(state_path)

def test_learning_stats():
    """Test ML stats generation for UI."""
    print("\n" + "="*60)
    print("Testing Learning Statistics (for UI)")
    print("="*60)
    
    cfg = PipelineConfig(
        ml=MLConfig(
            enabled=True,
            model_type="v2",
            exploration_strategy="ucb",
            use_llm=False,
            use_semantic_encoder=False,
            use_learning=True,
            learning_storage_path=None
        )
    )
    
    model = EnhancedMLGenerationModelV2(cfg)
    spec_dict = yaml.safe_load(TEST_SPEC)
    
    for i in range(3):
        result = model.generate(spec_dict)
        reward = 1.0 if result['passed'] else 0.0
        model.learn(result, reward)
    
    if hasattr(model, 'get_learning_stats'):
        stats = model.get_learning_stats()
        
        print(f"\n  Learning Stats:")
        print(f"    Total generations: {stats.get('total_generations', 0)}")
        
        if 'source_distribution' in stats:
            print(f"\n    Source distribution:")
            for source, count in stats['source_distribution'].items():
                print(f"      • {source}: {count}")
        
        if 'strategy_weights' in stats:
            print(f"\n    Strategy weights:")
            for strategy, weight in stats['strategy_weights'].items():
                print(f"      • {strategy}: {weight}")
        
        if 'rl_learner' in stats:
            print(f"\n    RL Learner stats:")
            print(f"      Episode count: {stats['rl_learner'].get('episode_count', 0)}")
            print(f"      Total updates: {stats['rl_learner'].get('total_updates', 0)}")
        
        if 'pattern_learner' in stats:
            print(f"\n    Pattern Learner stats:")
            print(f"      Total specs seen: {stats['pattern_learner'].get('total_specs_seen', 0)}")
        
        return True
    
    return False

def run_all_tests():
    """Run all tests and report results."""
    print("\n" + "="*60)
    print("Advanced ML V2 Model - Complete Test Suite")
    print("="*60)
    
    tests = [
        ("RL Exploration Strategies", test_rl_strategies),
        ("Experience Replay & Eligibility Traces", test_experience_replay),
        ("Advanced Pattern Learner", test_pattern_learner),
        ("Deep UVM Validation", test_deep_validation),
        ("Learning State Persistence", test_learning_persistence),
        ("Learning Statistics (UI)", test_learning_stats),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result, None))
        except Exception as e:
            results.append((name, False, str(e)))
    
    print("\n" + "="*60)
    print("Test Results Summary")
    print("="*60)
    
    all_passed = True
    for name, result, error in results:
        if result:
            print(f"✅ {name}")
        else:
            print(f"❌ {name}")
            all_passed = False
            if error:
                print(f"   Error: {error}")
    
    print("\n" + "="*60)
    if all_passed:
        print("🎉 All tests PASSED!")
    else:
        print("⚠️ Some tests FAILED")
    print("="*60)
    
    return all_passed

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
