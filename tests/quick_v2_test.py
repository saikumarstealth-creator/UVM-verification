"""
Quick smoke test for V2 ML model - final version
"""

import sys
import os

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, repo_root)

from src.config import ConfigLoader, PipelineConfig, MLConfig, GenerationConfig, AutoTrainConfig
from src.pipeline import TBPipeline

spec_path = os.path.join(repo_root, "configs", "uart_demo.yaml")

print("="*60)
print("V2 ML Model Smoke Test")
print("="*60)

print("\n1. Creating pipeline config with V2 model (UCB strategy)...")

ml_cfg = MLConfig(
    enabled=True,
    model_type="v2",
    exploration_strategy="ucb",
    use_llm=False,
    use_semantic_encoder=False,
    use_learning=True,
    strict_validation=True
)

pipeline_cfg = PipelineConfig(
    ml=ml_cfg,
    generation=GenerationConfig(
        templates_dir=os.path.join(repo_root, "src", "generation", "templates"),
        output_dir=os.path.join(repo_root, "output"),
        overwrite=True
    ),
    auto_train=AutoTrainConfig(
        enabled=False,
        max_iterations=1
    )
)

print(f"   ML enabled: {pipeline_cfg.ml.enabled}")
print(f"   Model type: {pipeline_cfg.ml.model_type}")
print(f"   Exploration strategy: {pipeline_cfg.ml.exploration_strategy}")
print(f"   Strict validation: {pipeline_cfg.ml.strict_validation}")
print(f"   Auto-train: {pipeline_cfg.auto_train.enabled}")

print("\n2. Creating pipeline with V2 model...")
pipeline = TBPipeline(pipeline_cfg)

print(f"   Model type: {type(pipeline.model).__name__}")

print("\n3. Running generation with UART demo spec...")
result = pipeline.run(spec_path)

print(f"\n   Result passed: {result.get('passed', False)}")
print(f"   Files generated: {len(result.get('generated_files', {}))}")
print(f"   Auto-train iterations: {result.get('auto_train_iterations', 0)}")

if result.get('passed'):
    print("\n   [OK] Generation PASSED")
else:
    print("\n   [WARNING] Generation had issues")

if result.get('generated_files'):
    print("\n4. Generated files:")
    for name, path in result['generated_files'].items():
        if os.path.exists(path):
            size = os.path.getsize(path)
            print(f"   - {name}: {size} bytes")

if hasattr(pipeline.model, 'get_learning_stats'):
    print("\n5. ML Learning Stats:")
    stats = pipeline.model.get_learning_stats()
    print(f"   - Total generations: {stats.get('total_generations', 0)}")
    if 'source_distribution' in stats:
        print(f"   - Source distribution: {stats['source_distribution']}")
    if 'strategy_weights' in stats:
        print(f"   - Strategy weights: {stats['strategy_weights']}")
    if 'rl_learner' in stats:
        rl = stats['rl_learner']
        print(f"   - RL episodes: {rl.get('episode_count', 0)}")
        print(f"   - RL total updates: {rl.get('total_updates', 0)}")
        print(f"   - RL learning rate: {rl.get('learning_rate', 0.1)}")
        if 'state_stats' in rl:
            state_stats = rl['state_stats']
            if state_stats:
                print(f"   - RL state stats (first 3):")
                for state, info in list(state_stats.items())[:3]:
                    print(f"     * '{state}': best='{info.get('best_action', 'N/A')}', Q={info.get('best_q_value', 0):.3f}")

eval_metrics = result.get('evaluation', {})
print("\n6. Evaluation Metrics:")
for key, value in eval_metrics.items():
    if isinstance(value, (int, float)):
        if 0 <= value <= 1:
            print(f"   - {key}: {value*100:.1f}%")
        else:
            print(f"   - {key}: {value}")

val_results = result.get('validation_results', {})
if val_results:
    total_checks = 0
    total_passed = 0
    
    print("\n7. Validation Results (Deep UVM Compliance):")
    for file_path, file_result in val_results.items():
        file_name = os.path.basename(file_path)
        checks = file_result.get('checks', [])
        
        for check in checks:
            total_checks += 1
            if check.get('passed'):
                total_passed += 1
    
    if total_checks > 0:
        pass_rate = (total_passed / total_checks) * 100
        print(f"   - Total checks: {total_checks}")
        print(f"   - Passed: {total_passed}")
        print(f"   - Pass rate: {pass_rate:.1f}%")

print("\n" + "="*60)
if result.get('passed'):
    print("TEST PASSED - V2 ML Model working correctly!")
else:
    print("TEST COMPLETED - Review warnings above")
print("="*60)
